"""
Agent 基类 - 所有Agent的基础实现
"""
import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from config import settings


class AgentType(str, Enum):
    """Agent类型枚举"""
    PRIMARY = "primary"
    COORDINATOR = "coordinator"
    DOMAIN = "domain"


class AgentStatus(str, Enum):
    """Agent状态枚举"""
    RUNNING = "running"
    IDLE = "idle"
    BUSY = "busy"
    STOPPED = "stopped"


class AgentConfig(BaseModel):
    """Agent配置"""
    name: str
    agent_type: AgentType
    description: str = ""
    skills: List[str] = []
    enabled_tools: List[str] = []
    disabled_tools: List[str] = []


class BaseAgent(ABC):
    """
    Agent基类

    所有Agent都继承此类，实现统一的接口和行为规范。
    """

    def __init__(
        self,
        config: AgentConfig,
        base_dir: Path,
        llm=None,
        tools: List = None,
    ):
        self.config = config
        self.base_dir = base_dir
        self.llm = llm
        self.tools = tools or []
        self.status = AgentStatus.IDLE
        self.current_task_id: Optional[str] = None

        # 设置工作目录
        if config.agent_type == AgentType.PRIMARY:
            self.workspace_dir = base_dir / "workspace" / "primary_agent"
        elif config.agent_type == AgentType.COORDINATOR:
            self.workspace_dir = base_dir / "workspace" / "coordinator_agent"
        else:
            self.workspace_dir = base_dir / "workspace" / "domain_agents" / config.name

        # 确保目录存在
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        (self.workspace_dir / "memory").mkdir(exist_ok=True)

    @property
    def name(self) -> str:
        """Agent名称"""
        return self.config.name

    @property
    def agent_type(self) -> AgentType:
        """Agent类型"""
        return self.config.agent_type

    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态信息"""
        return {
            "name": self.name,
            "type": self.agent_type.value,
            "status": self.status.value,
            "current_task": self.current_task_id,
            "skills": self.config.skills,
            "path": str(self.workspace_dir.relative_to(self.base_dir)),
        }

    def build_system_prompt(self) -> str:
        """
        构建System Prompt

        按照需求文档的拼接顺序：
        1. SKILLS_SNAPSHOT_LOCAL.md（Agent专属技能列表）
        2. GLOBAL_MEMORY/AGENTS_GLOBAL.md（全局行为准则）
        3. {agent_name}/SOUL.md（核心设定）
        4. {agent_name}/IDENTITY.md（自我认知）
        5. GLOBAL_MEMORY/USER.md（用户画像）
        6. {agent_name}/AGENTS_LOCAL.md（专属行为准则&记忆操作指南）
        7. {agent_name}/MEMORY.md（专属长期记忆）
        8. COORDINATION/COORDINATION_SNAPSHOT.md（实时协同状态，仅主交互/协同管理Agent加载）
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

        # 1. Agent专属技能列表
        skills_snapshot = read_file(
            self.workspace_dir / "SKILLS_SNAPSHOT_LOCAL.md",
            "Skills Snapshot"
        )
        if skills_snapshot:
            parts.append(skills_snapshot)

        # 2. 全局行为准则
        global_agents = read_file(
            self.base_dir / "workspace" / "global_memory" / "AGENTS_GLOBAL.md",
            "Global Agents Guide"
        )
        if global_agents:
            parts.append(global_agents)

        # 3. 核心设定
        soul = read_file(
            self.workspace_dir / "SOUL.md",
            "Soul"
        )
        if soul:
            parts.append(soul)

        # 4. 自我认知
        identity = read_file(
            self.workspace_dir / "IDENTITY.md",
            "Identity"
        )
        if identity:
            parts.append(identity)

        # 5. 用户画像
        user = read_file(
            self.base_dir / "workspace" / "global_memory" / "USER.md",
            "User Profile"
        )
        if user:
            parts.append(user)

        # 6. 专属行为准则
        agents_local = read_file(
            self.workspace_dir / "AGENTS_LOCAL.md",
            "Agents Local Guide"
        )
        if agents_local:
            parts.append(agents_local)

        # 7. 专属长期记忆
        memory = read_file(
            self.workspace_dir / "memory" / "MEMORY.md",
            "Long-term Memory"
        )
        if memory:
            parts.append(memory)

        # 8. 协同状态快照（仅Primary和Coordinator Agent加载）
        if self.agent_type in [AgentType.PRIMARY, AgentType.COORDINATOR]:
            coordination_snapshot = read_file(
                self.base_dir / "workspace" / "coordination" / "COORDINATION_SNAPSHOT.md",
                "Coordination Snapshot"
            )
            if coordination_snapshot:
                parts.append(coordination_snapshot)

        return "\n\n".join(parts)

    @abstractmethod
    async def execute(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行任务

        Args:
            task: 任务描述
            context: 任务上下文

        Returns:
            执行结果
        """
        pass

    @abstractmethod
    async def astream(
        self, message: str, session_id: str = None, **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式执行

        Args:
            message: 用户消息
            session_id: 会话ID

        Yields:
            事件字典
        """
        pass

    def start(self) -> None:
        """启动Agent"""
        self.status = AgentStatus.RUNNING

    def stop(self) -> None:
        """停止Agent"""
        self.status = AgentStatus.STOPPED

    def set_busy(self, task_id: str = None) -> None:
        """设置为忙碌状态"""
        self.status = AgentStatus.BUSY
        self.current_task_id = task_id

    def set_idle(self) -> None:
        """设置为空闲状态"""
        self.status = AgentStatus.IDLE
        self.current_task_id = None


class PrimaryAgent(BaseAgent):
    """
    主交互Agent

    用户唯一交互入口，接收指令、任务拆解、Agent调度、结果汇总反馈。
    """

    def __init__(self, base_dir: Path, llm=None, tools: List = None):
        config = AgentConfig(
            name="primary_agent",
            agent_type=AgentType.PRIMARY,
            description="用户交互入口，任务拆解与结果汇总",
            skills=["task_split", "agent_dispatch", "status_query"],
            enabled_tools=["terminal", "python_repl", "fetch_url", "read_file", "search_knowledge_base"],
            disabled_tools=[],
        )
        super().__init__(config, base_dir, llm, tools)

    async def execute(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行任务"""
        self.set_busy()
        try:
            # 构建Agent
            from langchain.agents import create_agent
            system_prompt = self.build_system_prompt()
            agent = create_agent(
                model=self.llm,
                tools=self.tools,
                system_prompt=system_prompt,
            )

            # 执行
            result = await agent.ainvoke({"messages": [HumanMessage(content=task)]})
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.set_idle()

    async def astream(
        self, message: str, session_id: str = None, **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行"""
        # 使用原有的agent_manager实现
        yield {"type": "error", "error": "PrimaryAgent astream not implemented, use AgentManager"}


class CoordinatorAgent(BaseAgent):
    """
    协同管理Agent

    多Agent协同"规则执行者"，负责任务状态同步、资源冲突解决、协同文件管理。
    """

    def __init__(self, base_dir: Path, llm=None, tools: List = None):
        config = AgentConfig(
            name="coordinator_agent",
            agent_type=AgentType.COORDINATOR,
            description="协同规则执行者，状态同步与冲突解决",
            skills=["status_query", "agent_dispatch"],
            enabled_tools=["read_file", "write_file", "search_knowledge_base"],
            disabled_tools=["terminal", "python_repl", "fetch_url"],
        )
        # 过滤工具，仅保留轻量化工具
        filtered_tools = [t for t in (tools or []) if t.name in config.enabled_tools]
        super().__init__(config, base_dir, llm, filtered_tools)

    async def execute(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行协同任务"""
        self.set_busy()
        try:
            # 协同管理任务的特殊处理
            task_type = context.get("task_type") if context else None

            if task_type == "sync_status":
                return await self._sync_coordination_status()
            elif task_type == "match_agent":
                return await self._match_agent(context.get("task_info", {}))
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.set_idle()

    async def astream(
        self, message: str, session_id: str = None, **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行"""
        yield {"type": "error", "error": "CoordinatorAgent does not support streaming"}

    async def _sync_coordination_status(self) -> Dict[str, Any]:
        """同步协同状态"""
        coordination_dir = self.base_dir / "workspace" / "coordination"
        tasks_dir = coordination_dir / "tasks"

        # 扫描任务目录
        tasks = []
        if tasks_dir.exists():
            for task_file in tasks_dir.glob("TASK_*.md"):
                task_info = self._parse_task_file(task_file)
                if task_info:
                    tasks.append(task_info)

        # 更新协同状态快照
        snapshot_path = coordination_dir / "COORDINATION_SNAPSHOT.md"
        await self._update_snapshot(snapshot_path, tasks)

        return {"success": True, "tasks_count": len(tasks)}

    async def _match_agent(self, task_info: Dict[str, Any]) -> Dict[str, Any]:
        """匹配Agent"""
        task_type = task_info.get("task_type", "")

        # 读取Agent注册表
        rules_path = self.base_dir / "workspace" / "global_memory" / "COORDINATION_RULES.md"
        if rules_path.exists():
            rules_content = rules_path.read_text(encoding="utf-8")
            # 简单匹配逻辑
            if "data" in task_type.lower():
                return {"success": True, "agent": "data_agent"}
            elif "doc" in task_type.lower():
                return {"success": True, "agent": "doc_agent"}

        return {"success": False, "error": "No matching agent found"}

    def _parse_task_file(self, task_file: Path) -> Optional[Dict[str, Any]]:
        """解析任务文件"""
        try:
            content = task_file.read_text(encoding="utf-8")
            # 解析frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1])
                    return {
                        "task_id": frontmatter.get("task_id"),
                        "status": frontmatter.get("status"),
                        "target_agent": frontmatter.get("target_agent"),
                        "content": parts[2].strip(),
                    }
            return None
        except Exception:
            return None

    async def _update_snapshot(self, snapshot_path: Path, tasks: List[Dict[str, Any]]) -> None:
        """更新协同状态快照"""
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""# 协同状态快照

> 此文件由Coordinator Agent自动维护，记录当前协同状态

## 更新时间

{now}

## Agent状态

| Agent | 类型 | 状态 | 当前任务 |
|-------|------|------|----------|
| primary_agent | primary | running | - |
| coordinator_agent | coordinator | running | - |
| data_agent | domain | idle | - |
| doc_agent | domain | idle | - |

## 任务队列

当前活跃任务: {len(tasks)} 条

"""
        for task in tasks:
            content += f"- {task.get('task_id', 'unknown')}: {task.get('status', 'unknown')}\n"

        snapshot_path.write_text(content, encoding="utf-8")


class DomainAgent(BaseAgent):
    """
    领域功能Agent

    承接主交互Agent拆解的单一领域原子子任务。
    """

    def __init__(
        self,
        name: str,
        base_dir: Path,
        llm=None,
        tools: List = None,
        skills: List[str] = None,
        enabled_tools: List[str] = None,
    ):
        config = AgentConfig(
            name=name,
            agent_type=AgentType.DOMAIN,
            description=f"领域Agent: {name}",
            skills=skills or [],
            enabled_tools=enabled_tools or ["python_repl", "read_file", "write_file"],
            disabled_tools=["terminal", "fetch_url"],
        )
        # 过滤工具
        filtered_tools = [t for t in (tools or []) if t.name in config.enabled_tools]
        super().__init__(config, base_dir, llm, filtered_tools)

    async def execute(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行领域任务"""
        self.set_busy(context.get("task_id") if context else None)
        try:
            # 构建Agent
            from langchain.agents import create_agent
            system_prompt = self.build_system_prompt()
            agent = create_agent(
                model=self.llm,
                tools=self.tools,
                system_prompt=system_prompt,
            )

            # 执行
            result = await agent.ainvoke({"messages": [HumanMessage(content=task)]})
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.set_idle()

    async def astream(
        self, message: str, session_id: str = None, **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行"""
        yield {"type": "error", "error": "DomainAgent does not support streaming directly"}