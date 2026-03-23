"""
多Agent管理 API - Agent列表、状态、启停、创建、画像
"""
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from graph.coordinator import get_coordination_manager
from pydantic import BaseModel

BASE_DIR = Path(os.getenv("BASE_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

router = APIRouter()


class AgentInfo(BaseModel):
    """Agent信息"""

    agent_name: str
    agent_type: str
    status: str
    skills: List[str]
    path: str


class AgentControlRequest(BaseModel):
    """Agent控制请求"""

    agent_name: str
    action: str  # start / stop


class AgentControlResponse(BaseModel):
    """Agent控制响应"""

    success: bool
    agent_name: str
    new_status: str
    message: str


class CreateAgentRequest(BaseModel):
    """创建Agent请求"""

    agent_name: str
    agent_type: str = "domain"
    skills: List[str] = []
    identity: str = ""
    soul: str = ""


@router.get("/agents")
async def list_agents():
    """
    多Agent列表查询接口

    返回所有可用Agent的名称、类型、状态、专属技能、存储路径。
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    agents = coordinator.list_agents()

    return {"code": 200, "data": agents, "msg": "success"}


@router.get("/agents/skills/all")
async def list_all_skills():
    """返回所有 Agent 已注册的技能标签（去重排序）"""
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    agents = coordinator.list_agents()
    skills_set: set = set()
    for agent in agents:
        for skill in agent.get("skills", []):
            skills_set.add(skill)

    return {"code": 200, "data": sorted(skills_set), "msg": "success"}


@router.get("/agents/{agent_name}")
async def get_agent(agent_name: str):
    """
    获取单个Agent详情

    Args:
        agent_name: Agent名称
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    agent = coordinator.get_agent_status(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")

    return {
        "code": 200,
        "data": {
            "agent_name": agent_name,
            "agent_type": agent["type"],
            "status": agent["status"],
            "skills": agent["skills"],
            "path": f"workspace/{agent_name}/",
        },
        "msg": "success",
    }


@router.post("/agents/control")
async def control_agent(request: AgentControlRequest):
    """
    领域Agent启停接口

    手动启停指定领域Agent，降低本地资源占用。

    Args:
        request: 包含agent_name和action的请求体
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    # 检查Agent是否存在
    agent = coordinator.get_agent_status(request.agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {request.agent_name}")

    # 不允许停止Primary和Coordinator Agent
    if agent["type"] in ["primary", "coordinator"]:
        raise HTTPException(status_code=400, detail=f"Cannot control {agent['type']} agent")

    # 执行控制操作
    if request.action == "start":
        coordinator.update_agent_status(request.agent_name, "idle")
        new_status = "idle"
        message = f"Agent {request.agent_name} started"
    elif request.action == "stop":
        coordinator.update_agent_status(request.agent_name, "stopped")
        new_status = "stopped"
        message = f"Agent {request.agent_name} stopped"
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")

    return {"success": True, "agent_name": request.agent_name, "new_status": new_status, "message": message}


def _resolve_agent_dir(agent_name: str) -> Path:
    """解析 Agent 的 workspace 目录路径（支持 universal / domain / 顶层）"""
    for subdir in ("universal_agents", "domain_agents"):
        candidate = BASE_DIR / "workspace" / subdir / agent_name
        if candidate.exists():
            return candidate
    direct = BASE_DIR / "workspace" / agent_name
    return direct


@router.get("/agents/{agent_name}/profile")
async def get_agent_profile(agent_name: str):
    """
    获取 Agent 画像信息

    返回 IDENTITY.md、SOUL.md、AGENTS_LOCAL.md 的内容。
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    agent = coordinator.get_agent_status(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")

    agent_dir = _resolve_agent_dir(agent_name)

    profile = {}
    for filename, key in [
        ("IDENTITY.md", "identity"),
        ("SOUL.md", "soul"),
        ("AGENTS_LOCAL.md", "agents_local"),
    ]:
        filepath = agent_dir / filename
        if filepath.exists():
            try:
                profile[key] = filepath.read_text(encoding="utf-8")
            except Exception:
                profile[key] = ""
        else:
            profile[key] = ""

    memory_file = agent_dir / "memory" / "MEMORY.md"
    if memory_file.exists():
        try:
            profile["memory"] = memory_file.read_text(encoding="utf-8")
        except Exception:
            profile["memory"] = ""
    else:
        profile["memory"] = ""

    return {
        "code": 200,
        "data": {
            "agent_name": agent_name,
            "agent_type": agent["type"],
            "status": agent["status"],
            "skills": agent["skills"],
            "profile": profile,
        },
        "msg": "success",
    }


@router.post("/agents")
async def create_agent(request: CreateAgentRequest):
    """
    创建子 Agent
    """
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    if coordinator.get_agent_status(request.agent_name):
        raise HTTPException(status_code=409, detail=f"Agent already exists: {request.agent_name}")

    if not request.agent_name.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Agent name must be alphanumeric with underscores/hyphens only")

    coordinator.register_agent(request.agent_name, request.agent_type, request.skills)

    # 根据类型选择存储目录
    if request.agent_type == "universal":
        agent_dir = BASE_DIR / "workspace" / "universal_agents" / request.agent_name
        workspace_path = f"workspace/universal_agents/{request.agent_name}/"
    else:
        agent_dir = BASE_DIR / "workspace" / "domain_agents" / request.agent_name
        workspace_path = f"workspace/domain_agents/{request.agent_name}/"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "memory").mkdir(exist_ok=True)

    skills_lines = chr(10).join(f"- {s}" for s in request.skills) if request.skills else "- 待配置"
    identity_content = request.identity or (
        f"# {request.agent_name} - 自我认知\n\n"
        f"## 基本信息\n\n"
        f"- 名称：{request.agent_name}\n"
        f"- 类型：{request.agent_type}\n"
        f"- 标识：{request.agent_name}\n\n"
        f"## 能力清单\n\n### 核心能力\n{skills_lines}\n\n"
        f"## 工作模式\n\n- 默认状态：idle\n- 任务执行时：busy\n- 完成后自动返回：idle\n"
    )
    (agent_dir / "IDENTITY.md").write_text(identity_content, encoding="utf-8")

    soul_content = request.soul or (
        f"# {request.agent_name} - 核心设定\n\n"
        f"## 身份定位\n\n你是 {request.agent_name}，一个专业的领域 Agent。\n\n"
        f"## 核心职责\n\n1. 接收并执行分配的任务\n2. 按照规范生成结果\n\n"
        f"## 行为准则\n\n- 任务执行时保持专注\n- 输出结果格式规范\n- 遇到问题及时反馈\n"
    )
    (agent_dir / "SOUL.md").write_text(soul_content, encoding="utf-8")

    (agent_dir / "memory" / "MEMORY.md").write_text(
        f"# {request.agent_name} - 记忆\n\n（暂无记忆记录）\n",
        encoding="utf-8",
    )

    return {
        "code": 200,
        "data": {
            "agent_name": request.agent_name,
            "agent_type": request.agent_type,
            "skills": request.skills,
            "path": workspace_path,
        },
        "msg": f"Agent {request.agent_name} created successfully",
    }


@router.delete("/agents/{agent_name}")
async def delete_agent(agent_name: str):
    """删除子 Agent（仅允许删除 domain 类型）"""
    coordinator = get_coordination_manager()
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordination manager not initialized")

    agent = coordinator.get_agent_status(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")

    if agent["type"] in ["primary", "coordinator"]:
        raise HTTPException(status_code=400, detail="Cannot delete system agents")

    coordinator.unregister_agent(agent_name)

    return {"code": 200, "data": {"agent_name": agent_name}, "msg": f"Agent {agent_name} deleted"}
