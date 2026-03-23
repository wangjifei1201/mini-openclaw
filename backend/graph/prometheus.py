"""
Prometheus 规划智能体 - 采访式需求收集与工作计划生成

提供精确规划模式：
1. 通过对话采访收集用户需求
2. 生成详细的工作计划
3. 与 LLMTaskPlanner 集成，输出 ExecutionPlan

灵感来源: oh-my-opencode 的 Prometheus planner agent
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage


@dataclass
class WorkPlan:
    """工作计划"""

    plan_id: str
    title: str
    description: str
    steps: List[Dict[str, Any]]  # [{"content", "agent", "tools", "acceptance_criteria"}]
    created_at: float = field(default_factory=time.time)
    status: str = "draft"  # draft, confirmed, executing, completed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "description": self.description,
            "steps": self.steps,
            "created_at": self.created_at,
            "status": self.status,
        }


_PROMETHEUS_SYSTEM_PROMPT = """你是 Prometheus，一位经验丰富的项目规划师。你的职责是通过与用户对话，深入理解需求并生成精确的工作计划。

## 你的工作方式

1. **需求收集阶段**: 通过提问了解用户的具体需求、约束条件、期望结果
2. **方案设计阶段**: 根据收集的需求，设计实施方案
3. **计划生成阶段**: 生成结构化的工作计划

## 可用的 Agent 团队

{agent_capabilities}

## 当用户确认计划时，输出以下 JSON 格式

```json
{{
    "title": "计划标题",
    "description": "计划简述",
    "steps": [
        {{
            "content": "步骤描述",
            "agent": "执行Agent名称",
            "tools": ["所需工具"],
            "acceptance_criteria": "验收标准"
        }}
    ]
}}
```

## 交互准则

- 每次最多问 2-3 个问题，不要一次问太多
- 问题要具体、有针对性
- 在充分了解需求后，主动提出计划方案
- 如果用户说"确认"或"开始执行"，立即输出 JSON 格式计划
- 用中文交流
"""


class PrometheusPlanner:
    """
    Prometheus 规划智能体

    负责：
    1. 管理规划对话状态
    2. 生成和解析工作计划
    3. 将工作计划转换为 ExecutionPlan
    """

    def __init__(self, llm, coordinator=None, base_dir: Path = None):
        self.llm = llm
        self.coordinator = coordinator
        self.base_dir = base_dir
        self._sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> planning state
        self._plans: Dict[str, WorkPlan] = {}

    def is_plan_mode(self, session_id: str) -> bool:
        """检查会话是否处于规划模式"""
        return session_id in self._sessions

    def enter_plan_mode(self, session_id: str) -> None:
        """进入规划模式"""
        self._sessions[session_id] = {
            "messages": [],
            "phase": "collecting",  # collecting, designing, confirming
            "start_time": time.time(),
        }

    def exit_plan_mode(self, session_id: str) -> None:
        """退出规划模式"""
        self._sessions.pop(session_id, None)

    async def chat(self, message: str, session_id: str) -> Dict[str, Any]:
        """
        规划对话

        Args:
            message: 用户消息
            session_id: 会话 ID

        Returns:
            {
                "response": "Prometheus 的回复",
                "plan": WorkPlan 或 None,
                "phase": "collecting" | "designing" | "confirmed"
            }
        """
        state = self._sessions.get(session_id)
        if not state:
            self.enter_plan_mode(session_id)
            state = self._sessions[session_id]

        # 构建消息历史
        agent_capabilities = self._get_agent_capabilities()
        system_prompt = _PROMETHEUS_SYSTEM_PROMPT.format(agent_capabilities=agent_capabilities)

        messages = [SystemMessage(content=system_prompt)]
        for msg in state["messages"]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                from langchain_core.messages import AIMessage

                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=message))

        # 调用 LLM
        try:
            response = await asyncio.wait_for(self.llm.ainvoke(messages), timeout=30)
            response_text = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            return {
                "response": f"规划器调用失败: {str(e)}",
                "plan": None,
                "phase": state["phase"],
            }

        # 保存对话
        state["messages"].append({"role": "user", "content": message})
        state["messages"].append({"role": "assistant", "content": response_text})

        # 尝试从响应中解析计划
        plan = self._extract_plan(response_text, session_id)

        if plan:
            state["phase"] = "confirmed"
            self._plans[plan.plan_id] = plan
            return {
                "response": response_text,
                "plan": plan.to_dict(),
                "phase": "confirmed",
            }

        return {
            "response": response_text,
            "plan": None,
            "phase": state["phase"],
        }

    def get_plan(self, plan_id: str) -> Optional[WorkPlan]:
        """获取工作计划"""
        return self._plans.get(plan_id)

    def plan_to_execution_plan(self, plan_id: str):
        """
        将 WorkPlan 转换为 ExecutionPlan

        Args:
            plan_id: 计划 ID

        Returns:
            ExecutionPlan 实例
        """
        from graph.llm_task_planner import ExecutionPlan, PlannedTodo

        plan = self._plans.get(plan_id)
        if not plan:
            return None

        todos = [
            PlannedTodo(
                content=step["content"],
                agent_name=step.get("agent", "primary_agent"),
            )
            for step in plan.steps
        ]

        return ExecutionPlan(
            strategy="multi",
            todos=todos,
            reason=f"Prometheus 计划: {plan.title}",
            confidence=0.95,
            source="prometheus",
        )

    def _get_agent_capabilities(self) -> str:
        """获取 Agent 能力描述"""
        if self.coordinator:
            from graph.llm_task_planner import collect_agent_capabilities

            return collect_agent_capabilities(self.coordinator, self.base_dir)
        return "primary_agent: 主交互Agent\ncode_agent: 代码开发\nresearch_agent: 信息检索与文档处理\ncreative_agent: 内容创作\ndata_agent: 数据分析"

    def _extract_plan(self, response: str, session_id: str) -> Optional[WorkPlan]:
        """从响应中提取工作计划 JSON"""
        # 尝试从 markdown 代码块提取
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                return self._parse_plan_data(data, session_id)
            except (json.JSONDecodeError, ValueError):
                pass

        # 尝试直接解析 JSON
        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            try:
                data = json.loads(match.group())
                if "steps" in data:
                    return self._parse_plan_data(data, session_id)
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    def _parse_plan_data(self, data: Dict, session_id: str) -> Optional[WorkPlan]:
        """解析计划数据"""
        steps = data.get("steps", [])
        if not steps:
            return None

        plan_id = f"PLAN_{int(time.time())}_{session_id[:8]}"

        return WorkPlan(
            plan_id=plan_id,
            title=data.get("title", "未命名计划"),
            description=data.get("description", ""),
            steps=steps,
            status="confirmed",
        )


# 全局单例
_prometheus: Optional[PrometheusPlanner] = None


def init_prometheus(llm, coordinator=None, base_dir: Path = None) -> PrometheusPlanner:
    """初始化 Prometheus"""
    global _prometheus
    _prometheus = PrometheusPlanner(llm, coordinator, base_dir)
    return _prometheus


def get_prometheus() -> Optional[PrometheusPlanner]:
    """获取 Prometheus 单例"""
    return _prometheus
