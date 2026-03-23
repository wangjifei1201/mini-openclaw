"""
任务执行器 - 多Agent任务分解与执行管理

功能：
1. 任务分解为Todo List
2. 执行状态管理
3. SSE事件推送（实时更新前端）
4. 统计数据收集
"""
import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from graph.coordinator import get_coordination_manager
from utils.token_tracker import get_token_tracker


class TaskStatus(str, Enum):
    """任务状态"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TodoItem:
    """Todo项"""

    id: str
    content: str
    status: str = "pending"
    agent: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    result: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "status": self.status,
            "agent": self.agent,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "result": self.result,
        }


@dataclass
class SubTask:
    """子任务"""

    id: str
    task_type: str
    target_agent: str
    content: str
    status: str = "pending"
    result: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "task_type": self.task_type,
            "target_agent": self.target_agent,
            "content": self.content,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class TaskContext:
    """任务上下文"""

    task_id: str
    message: str
    status: TaskStatus = TaskStatus.PENDING
    todos: List[TodoItem] = field(default_factory=list)
    subtasks: List[SubTask] = field(default_factory=list)
    agent_status: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    event_callback: Optional[Callable] = None

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "message": self.message,
            "status": self.status.value,
            "todos": [t.to_dict() for t in self.todos],
            "subtasks": [s.to_dict() for s in self.subtasks],
            "agent_status": self.agent_status,
        }


class TaskExecutor:
    """
    任务执行器

    负责：
    1. 任务分解
    2. Todo List生成
    3. 执行状态管理
    4. SSE事件推送
    """

    # 任务分解规则
    TASK_TEMPLATES = {
        "data_analysis": [
            {"content": "分析数据结构和内容", "agent": "data_agent"},
            {"content": "执行数据统计分析", "agent": "data_agent"},
            {"content": "生成分析结果报告", "agent": "primary_agent"},
        ],
        "data_visualization": [
            {"content": "分析数据结构和内容", "agent": "data_agent"},
            {"content": "执行数据统计分析", "agent": "data_agent"},
            {"content": "生成数据可视化图表", "agent": "data_agent"},
            {"content": "输出分析报告", "agent": "primary_agent"},
        ],
        "code_task": [
            {"content": "分析需求和技术方案", "agent": "code_agent"},
            {"content": "编写代码并验证", "agent": "code_agent"},
            {"content": "汇总代码实现结果", "agent": "primary_agent"},
        ],
        "research_task": [
            {"content": "收集相关资料和信息", "agent": "research_agent"},
            {"content": "分析整理调研内容", "agent": "research_agent"},
            {"content": "生成调研报告", "agent": "primary_agent"},
        ],
        "creative_task": [
            {"content": "理解创作需求和风格要求", "agent": "creative_agent"},
            {"content": "撰写内容初稿", "agent": "creative_agent"},
            {"content": "审核润色并输出最终版本", "agent": "primary_agent"},
        ],
        "general": [
            {"content": "理解任务需求", "agent": "primary_agent"},
            {"content": "执行任务处理", "agent": "primary_agent"},
            {"content": "生成响应结果", "agent": "primary_agent"},
        ],
    }

    def __init__(self):
        self._tasks: Dict[str, TaskContext] = {}
        self._tracker = get_token_tracker()

    def create_task(
        self,
        message: str,
        session_id: Optional[str] = None,
        event_callback: Optional[Callable] = None,
    ) -> str:
        """
        创建任务

        Args:
            message: 用户消息
            session_id: 会话ID
            event_callback: SSE事件回调函数

        Returns:
            任务ID
        """
        task_id = f"TASK_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        # 创建任务上下文
        context = TaskContext(
            task_id=task_id,
            message=message,
            event_callback=event_callback,
        )

        # 分析任务类型并生成Todo列表
        task_type = self._analyze_task_type(message)
        context.todos = self._generate_todos(task_type, task_id)

        # 初始化Agent状态
        context.agent_status = {
            "primary_agent": "idle",
            "coordinator_agent": "idle",
            "code_agent": "idle",
            "research_agent": "idle",
            "creative_agent": "idle",
            "data_agent": "idle",
        }

        self._tasks[task_id] = context

        # 启动Token追踪
        self._tracker.start_task(task_id)

        # 发送任务创建事件
        self._emit_event(
            task_id,
            "task_created",
            {
                "task_id": task_id,
                "message": message,
                "todos": [t.to_dict() for t in context.todos],
            },
        )

        # 发送任务拆分完成事件
        self._emit_event(
            task_id,
            "task_split",
            {
                "task_id": task_id,
                "todos": [t.to_dict() for t in context.todos],
                "subtasks": [],
            },
        )

        return task_id

    def update_todo_status(
        self,
        task_id: str,
        todo_id: str,
        status: str,
        result: Optional[str] = None,
    ) -> bool:
        """
        更新Todo状态

        Args:
            task_id: 任务ID
            todo_id: Todo ID
            status: 新状态
            result: 执行结果

        Returns:
            是否更新成功
        """
        if task_id not in self._tasks:
            return False

        context = self._tasks[task_id]
        for todo in context.todos:
            if todo.id == todo_id:
                old_status = todo.status
                todo.status = status

                if status == "in_progress":
                    todo.start_time = time.time()
                elif status in ["completed", "failed"]:
                    todo.end_time = time.time()
                    todo.result = result

                # 发送更新事件
                self._emit_event(
                    task_id,
                    "todo_update",
                    {
                        "task_id": task_id,
                        "todo_id": todo_id,
                        "old_status": old_status,
                        "new_status": status,
                        "todo": todo.to_dict(),
                    },
                )

                return True

        return False

    def update_agent_status(
        self,
        task_id: str,
        agent_name: str,
        status: str,
    ) -> bool:
        """
        更新Agent状态

        Args:
            task_id: 任务ID
            agent_name: Agent名称
            status: 新状态

        Returns:
            是否更新成功
        """
        if task_id not in self._tasks:
            return False

        context = self._tasks[task_id]
        context.agent_status[agent_name] = status

        return True

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        if task_id in self._tasks:
            return self._tasks[task_id].to_dict()
        return None

    def get_task_stats(self, task_id: str) -> Optional[Dict]:
        """获取任务统计"""
        return self._tracker.get_task_stats(task_id)

    def complete_task(self, task_id: str, summary: str = "") -> None:
        """
        完成任务

        Args:
            task_id: 任务ID
            summary: 任务总结
        """
        if task_id not in self._tasks:
            return

        context = self._tasks[task_id]
        context.status = TaskStatus.COMPLETED

        # 结束Token追踪
        stats = self._tracker.end_task(task_id)

        # 发送完成事件
        self._emit_event(
            task_id,
            "task_complete",
            {
                "task_id": task_id,
                "summary": summary,
                "final_stats": stats.to_dict() if stats else None,
            },
        )

    def fail_task(self, task_id: str, error: str) -> None:
        """
        任务失败

        Args:
            task_id: 任务ID
            error: 错误信息
        """
        if task_id not in self._tasks:
            return

        context = self._tasks[task_id]
        context.status = TaskStatus.FAILED

        # 结束Token追踪
        self._tracker.end_task(task_id)

        # 发送失败事件
        self._emit_event(
            task_id,
            "task_failed",
            {
                "task_id": task_id,
                "error": error,
            },
        )

    def create_task_from_plan(
        self,
        message: str,
        plan,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Create task using LLM-generated ExecutionPlan.

        Skips internal _analyze_task_type and _generate_todos, using
        the plan's todos directly.

        Args:
            message: User message
            plan: ExecutionPlan from LLMTaskPlanner
            session_id: Session ID

        Returns:
            Task ID
        """
        task_id = f"TASK_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        context = TaskContext(
            task_id=task_id,
            message=message,
        )

        # Build todos directly from plan
        todos = []
        for i, planned_todo in enumerate(plan.todos):
            todo = TodoItem(
                id=f"{task_id}_todo_{i}",
                content=planned_todo.content,
                agent=planned_todo.agent_name,
            )
            todos.append(todo)
        context.todos = todos

        # Dynamic agent_status from plan
        involved_agents = set(t.agent_name for t in plan.todos)
        involved_agents.add("primary_agent")
        context.agent_status = {agent: "idle" for agent in involved_agents}

        self._tasks[task_id] = context
        self._tracker.start_task(task_id)

        return task_id

    def _analyze_task_type(self, message: str) -> str:
        """
        分析任务类型

        Args:
            message: 用户消息

        Returns:
            任务类型
        """
        message_lower = message.lower()

        # 数据分析任务
        if any(kw in message_lower for kw in ["分析", "统计", "csv", "excel", "表格", "数据"]):
            if any(kw in message_lower for kw in ["图表", "可视化", "plot", "图"]):
                return "data_visualization"
            return "data_analysis"

        # 代码任务
        if any(kw in message_lower for kw in ["代码", "编程", "调试", "bug", "实现", "开发", "重构", "测试", "code", "debug"]):
            return "code_task"

        # 调研任务
        if any(kw in message_lower for kw in ["调研", "搜索", "查询", "检索", "资料", "文档解析", "pdf", "word"]):
            return "research_task"

        # 创作任务
        if any(kw in message_lower for kw in ["撰写", "写作", "翻译", "文案", "文档", "报告", "方案", "内容创作", "润色"]):
            return "creative_task"

        return "general"

    def _generate_todos(self, task_type: str, task_id: str) -> List[TodoItem]:
        """
        生成Todo列表

        Args:
            task_type: 任务类型
            task_id: 任务ID

        Returns:
            Todo列表
        """
        template = self.TASK_TEMPLATES.get(task_type, self.TASK_TEMPLATES["general"])
        todos = []

        for i, item in enumerate(template):
            todo = TodoItem(
                id=f"{task_id}_todo_{i}",
                content=item["content"],
                agent=item["agent"],
            )
            todos.append(todo)

        return todos

    def _emit_event(self, task_id: str, event_type: str, data: Dict) -> None:
        """
        发送SSE事件

        Args:
            task_id: 任务ID
            event_type: 事件类型
            data: 事件数据
        """
        if task_id in self._tasks:
            context = self._tasks[task_id]
            if context.event_callback:
                try:
                    event = {"type": event_type, **data}
                    context.event_callback(event)
                except Exception as e:
                    print(f"发送事件失败: {e}")


# 全局单例
_task_executor: Optional[TaskExecutor] = None


def get_task_executor() -> TaskExecutor:
    """获取任务执行器单例"""
    global _task_executor
    if _task_executor is None:
        _task_executor = TaskExecutor()
    return _task_executor
