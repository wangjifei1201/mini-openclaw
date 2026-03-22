"""
任务分发执行器 - 让 Primary Agent 调度 Domain Agent 执行任务

使用 astream_events 获取 token 级别的细粒度流式输出。
"""
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from config import get_rag_mode, settings
from graph.coordinator import get_coordination_manager
from langchain_core.messages import HumanMessage, ToolMessage
from tools import get_all_tools
from utils.token_tracker import estimate_tokens, get_token_tracker

# Agent 图执行最大步数
RECURSION_LIMIT = 50


class TaskDispatcher:
    """
    任务分发执行器

    集成到 Primary Agent 中，负责：
    1. 判断任务是否需要分发
    2. 选择合适的 Domain Agent
    3. 使用专用 System Prompt 执行任务
    4. 返回执行结果（token 级别流式输出）
    """

    # 任务类型关键词映射
    TASK_KEYWORDS = {
        "data_processing": ["数据", "分析", "统计", "计算", "表格", "csv", "excel", "可视化", "图表"],
        "document_analysis": ["文档", "pdf", "word", "解析", "提取", "摘要", "格式转换"],
    }

    # Domain Agent 配置
    DOMAIN_AGENTS = {
        "data_agent": {
            "task_types": ["data_processing", "data_analysis", "table_processing", "visualization"],
            "enabled_tools": ["python_repl", "read_file", "write_file"],
            "workspace": "workspace/domain_agents/data_agent/",
        },
        "doc_agent": {
            "task_types": ["document_analysis", "document_parsing", "content_extraction", "format_conversion"],
            "enabled_tools": ["python_repl", "read_file", "write_file"],
            "workspace": "workspace/domain_agents/doc_agent/",
        },
    }

    def __init__(self, base_dir: Path, llm=None):
        self.base_dir = base_dir
        self.llm = llm
        self.all_tools = {t.name: t for t in get_all_tools(base_dir)}

    def analyze_task(self, message: str) -> Dict[str, Any]:
        """
        分析任务类型

        Args:
            message: 用户消息

        Returns:
            分析结果：是否需要分发、任务类型、目标Agent
        """
        message_lower = message.lower()

        # 检查是否包含任务分发关键词
        for task_type, keywords in self.TASK_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message_lower:
                    # 找到匹配的Agent
                    for agent_name, config in self.DOMAIN_AGENTS.items():
                        if task_type.replace("_", "") in [t.replace("_", "") for t in config["task_types"]]:
                            return {
                                "need_dispatch": True,
                                "task_type": task_type,
                                "target_agent": agent_name,
                                "confidence": 0.8,
                            }

        return {
            "need_dispatch": False,
            "task_type": None,
            "target_agent": None,
            "confidence": 0,
        }

    def build_domain_agent_prompt(self, agent_name: str) -> str:
        """
        构建 Domain Agent 的 System Prompt

        Args:
            agent_name: Agent名称

        Returns:
            System Prompt
        """
        parts = []
        max_length = settings.MAX_CONTENT_LENGTH

        def read_file(path: Path, label: str) -> str:
            if not path.exists():
                return ""
            try:
                content = path.read_text(encoding="utf-8")
                if len(content) > max_length:
                    content = content[:max_length] + "\n...[truncated]"
                return f"<!-- {label} -->\n{content}"
            except Exception:
                return ""

        # Agent 工作目录
        agent_workspace = self.base_dir / "workspace" / "domain_agents" / agent_name

        # 1. 全局行为准则
        global_agents = read_file(
            self.base_dir / "workspace" / "global_memory" / "AGENTS_GLOBAL.md", "Global Agents Guide"
        )
        if global_agents:
            parts.append(global_agents)

        # 2. 核心设定
        soul = read_file(agent_workspace / "SOUL.md", "Soul")
        if soul:
            parts.append(soul)

        # 3. 自我认知
        identity = read_file(agent_workspace / "IDENTITY.md", "Identity")
        if identity:
            parts.append(identity)

        # 4. 用户画像
        user = read_file(self.base_dir / "workspace" / "global_memory" / "USER.md", "User Profile")
        if user:
            parts.append(user)

        # 5. 专属行为准则
        agents_local = read_file(agent_workspace / "AGENTS_LOCAL.md", "Agents Local Guide")
        if agents_local:
            parts.append(agents_local)

        # 6. 专属记忆
        memory = read_file(agent_workspace / "memory" / "MEMORY.md", "Long-term Memory")
        if memory:
            parts.append(memory)

        return "\n\n".join(parts)

    def _resolve_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """
        Dynamically resolve agent config from coordinator + workspace.

        Falls back to DOMAIN_AGENTS hardcoded config if agent not found.
        """
        # Check hardcoded config first
        if agent_name in self.DOMAIN_AGENTS:
            return self.DOMAIN_AGENTS[agent_name]

        # Dynamic resolution for newly created agents
        coordinator = get_coordination_manager()
        agent_info = coordinator.get_agent_status(agent_name) if coordinator else None

        if agent_info:
            return {
                "enabled_tools": ["python_repl", "read_file", "write_file"],
                "workspace": f"workspace/domain_agents/{agent_name}/",
            }

        # Ultimate fallback
        return {
            "enabled_tools": ["python_repl", "read_file", "write_file"],
            "workspace": f"workspace/domain_agents/{agent_name}/",
        }

    def get_domain_agent_tools(self, agent_name: str) -> List:
        """
        获取 Domain Agent 可用的工具

        Args:
            agent_name: Agent名称

        Returns:
            工具列表
        """
        config = self._resolve_agent_config(agent_name)
        enabled_tools = config.get("enabled_tools", [])

        tools = []
        for tool_name in enabled_tools:
            if tool_name in self.all_tools:
                tools.append(self.all_tools[tool_name])

        return tools

    async def dispatch_task(
        self,
        task_content: str,
        target_agent: str,
        task_id: str = None,
        session_id: str = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        分发任务给 Domain Agent 执行（细粒度流式输出）

        使用 astream_events 获取 token 级别的流式输出，
        与 agent_manager.astream() 的事件处理逻辑对齐。

        Args:
            task_content: 任务内容
            target_agent: 目标Agent
            task_id: 外部任务ID（可选，用于 token 追踪）
            session_id: 会话ID

        Yields:
            执行事件（附加 agent_name 字段）
        """
        coordinator = get_coordination_manager()
        tracker = get_token_tracker()

        # 创建协同任务记录
        coord_task_id = coordinator.create_task(
            task_content=task_content,
            target_agent=target_agent,
        )

        # 更新任务状态
        coordinator.update_task_status(coord_task_id, "processing")
        coordinator.update_agent_status(target_agent, "busy", coord_task_id)

        try:
            # 构建 Domain Agent
            system_prompt = self.build_domain_agent_prompt(target_agent)
            tools = self.get_domain_agent_tools(target_agent)

            from langchain.agents import create_agent

            agent = create_agent(
                model=self.llm,
                tools=tools,
                system_prompt=system_prompt,
            )

            # 估算输入 token
            input_text = system_prompt + task_content
            estimated_input_tokens = estimate_tokens(input_text)

            # 流式执行
            result_content = ""
            tool_calls = []
            tool_start_times = {}
            accumulated_output_chars = 0

            async for event in agent.astream_events(
                {"messages": [HumanMessage(content=task_content)]},
                version="v2",
                config={"recursion_limit": RECURSION_LIMIT},
            ):
                kind = event.get("event", "")

                # LLM 输出 token
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token_text = chunk.content
                        # 过滤 <think> 标签
                        token_text = re.sub(r"<think>.*?</think>", "", token_text, flags=re.DOTALL)
                        if "<think>" in token_text:
                            token_text = token_text[: token_text.index("<think>")]
                        if "</think>" in token_text:
                            token_text = token_text[token_text.index("</think>") + len("</think>") :]
                        if token_text:
                            result_content += token_text
                            accumulated_output_chars += len(token_text)
                            yield {
                                "type": "token",
                                "source": "llm",
                                "content": token_text,
                                "agent_name": target_agent,
                                "task_id": task_id,
                            }

                # 工具调用开始
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    tool_start_times[len(tool_calls)] = time.time()

                    # 记录工具调用
                    if task_id:
                        tracker.record_tool_call(tool_name, task_id, target_agent)

                    yield {
                        "type": "tool_start",
                        "source": "tool",
                        "tool": tool_name,
                        "tool_input": tool_input,
                        "input": tool_input,
                        "agent_name": target_agent,
                        "task_id": task_id,
                        "start_time": tool_start_times[len(tool_calls)],
                    }

                # 工具调用结束
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output", "")

                    tool_idx = len(tool_calls)
                    start_time = tool_start_times.get(tool_idx, time.time())
                    elapsed_time = time.time() - start_time

                    # 处理 ToolMessage
                    tool_call_id = None
                    output_content = tool_output
                    if isinstance(tool_output, ToolMessage):
                        tool_call_id = getattr(tool_output, "tool_call_id", None)
                        output_content = getattr(tool_output, "content", "")

                    if not isinstance(output_content, str):
                        output_content = str(output_content)

                    # 错误检测
                    tool_status = "ok"
                    tool_error = None
                    if isinstance(output_content, str) and (
                        "Traceback" in output_content or "Exception" in output_content or "Error:" in output_content
                    ):
                        tool_status = "error"
                        tool_error = output_content

                    tool_calls.append(
                        {
                            "tool": tool_name,
                            "input": event.get("data", {}).get("input", {}),
                            "output": output_content,
                            "tool_call_id": tool_call_id,
                            "tool_status": tool_status,
                            "elapsed_time": elapsed_time,
                        }
                    )

                    yield {
                        "type": "tool_end",
                        "source": "tool",
                        "tool": tool_name,
                        "tool_input": event.get("data", {}).get("input", {}),
                        "tool_output": output_content,
                        "output": output_content,
                        "tool_call_id": tool_call_id,
                        "tool_status": tool_status,
                        "tool_error": tool_error,
                        "elapsed_time": elapsed_time,
                        "agent_name": target_agent,
                        "task_id": task_id,
                    }

                    # 工具执行后新一轮文本生成
                    yield {"type": "new_response", "agent_name": target_agent}
                    result_content = ""

            # 记录 LLM 调用统计
            estimated_output_tokens = (
                estimate_tokens(result_content) if result_content else max(1, accumulated_output_chars * 2 // 3)
            )
            if task_id:
                tracker.record_llm_call(
                    agent=target_agent,
                    input_tokens=estimated_input_tokens,
                    output_tokens=estimated_output_tokens,
                    task_id=task_id,
                )

            # 更新协同状态
            coordinator.update_task_status(coord_task_id, "finished", result_content)
            coordinator.update_agent_status(target_agent, "idle")
            coordinator.create_response(
                task_id=coord_task_id,
                result=result_content,
                agent_name=target_agent,
            )

            # 完成事件
            yield {
                "type": "dispatch_end",
                "task_id": task_id,
                "coord_task_id": coord_task_id,
                "target_agent": target_agent,
                "result": result_content,
                "tool_calls": tool_calls,
            }

        except Exception as e:
            coordinator.update_task_status(coord_task_id, "failed", str(e))
            coordinator.update_agent_status(target_agent, "idle")

            yield {
                "type": "dispatch_error",
                "task_id": task_id,
                "coord_task_id": coord_task_id,
                "target_agent": target_agent,
                "error": str(e),
                "agent_name": target_agent,
            }

    def get_dispatch_summary(self) -> Dict[str, Any]:
        """获取分发状态摘要"""
        coordinator = get_coordination_manager()

        return {
            "agents": coordinator.list_agents(),
            "pending_tasks": coordinator.list_tasks(status="pending"),
            "processing_tasks": coordinator.list_tasks(status="processing"),
        }


# ============ 全局单例 ============

_task_dispatcher: Optional[TaskDispatcher] = None


def init_task_dispatcher(base_dir: Path, llm=None) -> TaskDispatcher:
    """初始化任务分发器"""
    global _task_dispatcher
    _task_dispatcher = TaskDispatcher(base_dir, llm)
    return _task_dispatcher


def get_task_dispatcher() -> Optional[TaskDispatcher]:
    """获取任务分发器单例"""
    return _task_dispatcher


# 工具函数：判断是否需要分发
def should_dispatch_to_domain_agent(message: str) -> Dict[str, Any]:
    """
    判断消息是否需要分发给 Domain Agent

    Args:
        message: 用户消息

    Returns:
        分析结果
    """
    dispatcher = TaskDispatcher(Path("."))
    return dispatcher.analyze_task(message)
