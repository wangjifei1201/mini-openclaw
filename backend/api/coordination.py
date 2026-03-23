"""
协同任务管理 API - 任务创建、查询、状态更新
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from graph.coordinator import get_coordination_manager
from pydantic import BaseModel

router = APIRouter()


class TaskCreateRequest(BaseModel):
    """创建任务请求"""

    task_content: str
    target_agent: Optional[str] = None
    task_type: Optional[str] = None
    parent_task_id: Optional[str] = None


class TaskInfo(BaseModel):
    """任务信息"""

    task_id: str
    status: str
    target_agent: str
    task_type: str
    parent_task: str
    created_at: str
    updated_at: str
    content: str


class TaskListResponse(BaseModel):
    """任务列表响应"""

    code: int
    data: List[TaskInfo]
    msg: str


class GlobalMemoryRequest(BaseModel):
    """全局记忆编辑请求"""

    file_name: str
    content: str


@router.get("/coordination/tasks")
async def list_tasks(task_id: Optional[str] = Query(None, description="任务ID，不传返回所有任务")):
    """
    协同任务状态查询接口

    查询协同任务状态、执行结果、关联Agent，支持按ID精准查询。

    Args:
        task_id: 可选，任务ID，不传返回所有任务
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    if task_id:
        # 查询单个任务
        task = coordinator.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        return {"code": 200, "data": task, "msg": "success"}
    else:
        # 查询所有任务
        tasks = coordinator.list_tasks()
        return {"code": 200, "data": tasks, "msg": "success"}


@router.post("/coordination/tasks")
async def create_task(request: TaskCreateRequest):
    """
    创建协同任务

    创建一个新的协同任务，可指定目标Agent或让系统自动匹配。

    Args:
        request: 任务创建请求
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    task_id = coordinator.create_task(
        task_content=request.task_content,
        target_agent=request.target_agent,
        task_type=request.task_type,
        parent_task_id=request.parent_task_id,
    )

    # 如果指定了目标Agent，创建通知
    if request.target_agent:
        coordinator.create_notice(
            notice_type="new_task",
            target_agent=request.target_agent,
            content=f"新任务已分配：{task_id}",
        )

    return {
        "code": 200,
        "data": {
            "task_id": task_id,
            "target_agent": request.target_agent or "auto",
        },
        "msg": "success",
    }


@router.delete("/coordination/tasks")
async def clear_all_tasks():
    """
    重置任务队列

    清除所有任务、响应和通知文件，重置Agent状态为idle。
    用于后端重启后清理残余的已失效任务。
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    count = coordinator.clear_tasks()
    return {"code": 200, "data": {"cleared_count": count}, "msg": f"已清除 {count} 个任务"}


@router.get("/coordination/tasks/{task_id}")
async def get_task(task_id: str):
    """
    获取任务详情

    Args:
        task_id: 任务ID
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    task = coordinator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return {"code": 200, "data": task, "msg": "success"}


@router.put("/coordination/tasks/{task_id}/status")
async def update_task_status(task_id: str, status: str = Query(..., description="新状态")):
    """
    更新任务状态

    Args:
        task_id: 任务ID
        status: 新状态 (pending/processing/finished/failed)
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    if status not in ["pending", "processing", "finished", "failed"]:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    coordinator.update_task_status(task_id, status)

    return {
        "code": 200,
        "data": {
            "task_id": task_id,
            "new_status": status,
        },
        "msg": "success",
    }


@router.get("/coordination/notices")
async def list_notices(target_agent: Optional[str] = Query(None, description="目标Agent")):
    """
    获取通知列表

    Args:
        target_agent: 可选，筛选特定Agent的通知
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    notices = coordinator.get_notices(target_agent)

    return {"code": 200, "data": notices, "msg": "success"}


@router.get("/coordination/snapshot")
async def get_coordination_snapshot():
    """
    获取协同状态快照

    返回当前的协同状态快照，包含所有Agent状态和活跃任务。
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    snapshot_file = coordinator.coordination_dir / "COORDINATION_SNAPSHOT.md"
    if not snapshot_file.exists():
        raise HTTPException(status_code=404, detail="Coordination snapshot not found")

    content = snapshot_file.read_text(encoding="utf-8")

    return {
        "code": 200,
        "data": {
            "content": content,
            "updated_at": datetime.now().isoformat(),
        },
        "msg": "success",
    }


@router.post("/global/memory")
async def edit_global_memory(request: GlobalMemoryRequest):
    """
    全局记忆编辑接口

    编辑全局公共记忆文件，保证修改一致性。

    Args:
        request: 包含file_name和content的请求体
    """
    from pathlib import Path

    from config import BASE_DIR

    # 允许编辑的文件列表
    allowed_files = ["USER.md", "AGENTS_GLOBAL.md", "COORDINATION_RULES.md"]

    if request.file_name not in allowed_files:
        raise HTTPException(status_code=400, detail=f"Invalid file name. Allowed: {allowed_files}")

    global_memory_dir = BASE_DIR / "workspace" / "global_memory"
    file_path = global_memory_dir / request.file_name

    try:
        # 确保目录存在
        global_memory_dir.mkdir(parents=True, exist_ok=True)

        # 写入文件
        file_path.write_text(request.content, encoding="utf-8")

        # 创建通知，通知所有Agent
        coordinator = get_coordination_manager()
        if coordinator:
            for agent_name in [
                "primary_agent",
                "coordinator_agent",
                "code_agent",
                "research_agent",
                "creative_agent",
                "data_agent",
            ]:
                coordinator.create_notice(
                    notice_type="memory_update",
                    target_agent=agent_name,
                    content=f"全局记忆已更新：{request.file_name}",
                )

        return {
            "code": 200,
            "data": {
                "file_name": request.file_name,
                "path": str(file_path.relative_to(BASE_DIR)),
            },
            "msg": "success",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {str(e)}")
