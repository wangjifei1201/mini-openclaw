"""
任务管理API - 多Agent协同任务管理

功能：
1. 创建任务并自动拆分
2. 获取任务的Todo List
3. 更新Todo状态
4. 获取子任务列表
5. 获取任务执行统计
"""
from typing import List, Optional

from fastapi import APIRouter
from graph.coordinator import get_coordination_manager
from pydantic import BaseModel
from utils.token_tracker import get_token_tracker

router = APIRouter()


# ============ 请求/响应模型 ============


class CreateTaskRequest(BaseModel):
    """创建任务请求"""

    message: str
    session_id: Optional[str] = None


class TodoItem(BaseModel):
    """Todo项"""

    id: str
    content: str
    status: str = "pending"  # pending, in_progress, completed, failed
    agent: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    result: Optional[str] = None


class SubTaskInfo(BaseModel):
    """子任务信息"""

    id: str
    task_type: str
    target_agent: str
    status: str
    content: str
    result: Optional[str] = None
    created_at: str
    updated_at: str


class TaskStatsResponse(BaseModel):
    """任务统计响应"""

    task_id: str
    llm_call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tool_call_count: int = 0
    start_time: float = 0
    elapsed_time: float = 0
    completed_subtasks: int = 0
    total_subtasks: int = 0
    llm_calls_by_agent: dict = {}
    tokens_by_agent: dict = {}
    tool_calls_by_name: dict = {}
    active_agents: list = []


class TaskDetailResponse(BaseModel):
    """任务详情响应"""

    task_id: str
    message: str
    status: str
    todos: List[TodoItem] = []
    subtasks: List[SubTaskInfo] = []
    stats: Optional[TaskStatsResponse] = None
    agent_status: dict = {}


# ============ API端点 ============


@router.post("/task/create")
async def create_task(request: CreateTaskRequest):
    """
    创建任务并自动拆分

    返回任务ID和初始Todo列表
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        return {"code": 500, "msg": "协同管理器未初始化", "data": None}

    # 创建主任务
    task_id = coordinator.create_task(
        task_content=request.message,
        target_agent="coordinator_agent",
        task_type="multi_agent_task",
    )

    # 启动Token追踪
    tracker = get_token_tracker()
    tracker.start_task(task_id)

    # 根据消息生成初始Todo列表
    todos = _generate_initial_todos(request.message)

    # 返回任务信息
    return {
        "code": 0,
        "msg": "任务创建成功",
        "data": {
            "task_id": task_id,
            "todos": todos,
            "status": "pending",
        },
    }


@router.get("/task/{task_id}")
async def get_task_detail(task_id: str):
    """
    获取任务详情

    包含：任务信息、Todo列表、子任务列表、统计数据
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        return {"code": 500, "msg": "协同管理器未初始化", "data": None}

    # 获取任务信息
    task = coordinator.get_task(task_id)
    if not task:
        return {"code": 404, "msg": "任务不存在", "data": None}

    # 获取子任务
    all_tasks = coordinator.list_tasks()
    subtasks = [t for t in all_tasks if t.get("parent_task") == task_id]

    # 获取统计数据
    tracker = get_token_tracker()
    stats = tracker.get_task_stats(task_id)

    # 获取Agent状态
    agents = coordinator.list_agents()
    agent_status = {a["agent_name"]: a["status"] for a in agents}

    # 构建响应
    return {
        "code": 0,
        "msg": "获取成功",
        "data": {
            "task_id": task_id,
            "message": task.get("content", ""),
            "status": task.get("status", "pending"),
            "todos": _get_task_todos(task_id),
            "subtasks": subtasks,
            "stats": stats,
            "agent_status": agent_status,
        },
    }


@router.get("/task/{task_id}/todos")
async def get_task_todos(task_id: str):
    """获取任务的Todo列表"""
    todos = _get_task_todos(task_id)
    return {"code": 0, "msg": "获取成功", "data": todos}


@router.put("/task/{task_id}/todo/{todo_id}")
async def update_todo_status(
    task_id: str,
    todo_id: str,
    status: str,
    result: Optional[str] = None,
):
    """
    更新Todo状态

    Args:
        task_id: 任务ID
        todo_id: Todo ID
        status: 新状态 (pending/in_progress/completed/failed)
        result: 执行结果（可选）
    """
    # 这里应该更新存储的Todo状态
    # 目前简化处理，直接返回成功
    return {
        "code": 0,
        "msg": "更新成功",
        "data": {
            "task_id": task_id,
            "todo_id": todo_id,
            "new_status": status,
        },
    }


@router.get("/task/{task_id}/subtasks")
async def get_task_subtasks(task_id: str):
    """获取任务的子任务列表"""
    coordinator = get_coordination_manager()
    if not coordinator:
        return {"code": 500, "msg": "协同管理器未初始化", "data": None}

    all_tasks = coordinator.list_tasks()
    subtasks = [t for t in all_tasks if t.get("parent_task") == task_id]

    return {"code": 0, "msg": "获取成功", "data": subtasks}


@router.get("/task/{task_id}/stats")
async def get_task_stats(task_id: str):
    """获取任务执行统计"""
    tracker = get_token_tracker()
    stats = tracker.get_task_stats(task_id)

    if not stats:
        return {"code": 404, "msg": "任务统计不存在", "data": None}

    return {"code": 0, "msg": "获取成功", "data": stats}


@router.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    coordinator = get_coordination_manager()
    if coordinator:
        # 更新任务状态为已取消
        coordinator.update_task_status(task_id, "cancelled")

    # 清除统计
    tracker = get_token_tracker()
    tracker.clear_task(task_id)

    return {"code": 0, "msg": "任务已删除", "data": None}


# ============ 辅助函数 ============


def _generate_initial_todos(message: str) -> List[dict]:
    """
    根据消息生成初始Todo列表

    使用简单规则分析任务，生成Todo项
    """
    todos = []
    todo_id = 0

    message_lower = message.lower()

    # 数据分析任务
    if any(kw in message_lower for kw in ["数据", "分析", "csv", "excel", "表格"]):
        todos.append(
            {
                "id": f"todo_{todo_id}",
                "content": "分析数据结构和内容",
                "status": "pending",
                "agent": "data_agent",
            }
        )
        todo_id += 1
        todos.append(
            {
                "id": f"todo_{todo_id}",
                "content": "执行数据统计分析",
                "status": "pending",
                "agent": "data_agent",
            }
        )
        todo_id += 1
        if "图表" in message_lower or "可视化" in message_lower:
            todos.append(
                {
                    "id": f"todo_{todo_id}",
                    "content": "生成数据可视化图表",
                    "status": "pending",
                    "agent": "data_agent",
                }
            )
            todo_id += 1
        todos.append(
            {
                "id": f"todo_{todo_id}",
                "content": "输出分析结果报告",
                "status": "pending",
                "agent": "primary_agent",
            }
        )

    # 文档处理任务
    elif any(kw in message_lower for kw in ["文档", "pdf", "word", "解析"]):
        todos.append(
            {
                "id": f"todo_{todo_id}",
                "content": "解析文档内容",
                "status": "pending",
                "agent": "doc_agent",
            }
        )
        todo_id += 1
        todos.append(
            {
                "id": f"todo_{todo_id}",
                "content": "提取关键信息",
                "status": "pending",
                "agent": "doc_agent",
            }
        )
        todo_id += 1
        todos.append(
            {
                "id": f"todo_{todo_id}",
                "content": "生成处理结果",
                "status": "pending",
                "agent": "primary_agent",
            }
        )

    # 通用任务
    else:
        todos.append(
            {
                "id": f"todo_{todo_id}",
                "content": "理解任务需求",
                "status": "pending",
                "agent": "primary_agent",
            }
        )
        todo_id += 1
        todos.append(
            {
                "id": f"todo_{todo_id}",
                "content": "执行任务处理",
                "status": "pending",
                "agent": "primary_agent",
            }
        )
        todo_id += 1
        todos.append(
            {
                "id": f"todo_{todo_id}",
                "content": "生成响应结果",
                "status": "pending",
                "agent": "primary_agent",
            }
        )

    return todos


def _get_task_todos(task_id: str) -> List[dict]:
    """获取任务的Todo列表（从存储读取）"""
    # 目前返回空列表，实际应从任务文件读取
    return []
