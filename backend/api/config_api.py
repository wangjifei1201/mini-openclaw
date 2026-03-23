"""
配置管理 API
"""
from config import (
    get_multi_agent_mode,
    get_rag_mode,
    set_multi_agent_mode,
    set_rag_mode,
)
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class RAGModeRequest(BaseModel):
    """RAG 模式设置请求"""

    enabled: bool


class MultiAgentModeRequest(BaseModel):
    """多Agent模式设置请求"""

    enabled: bool


@router.get("/config/rag-mode")
async def get_rag_mode_status():
    """获取 RAG 模式状态"""
    return {"enabled": get_rag_mode()}


@router.put("/config/rag-mode")
async def set_rag_mode_status(request: RAGModeRequest):
    """
    切换 RAG 模式

    启用后，会话中的记忆将通过语义检索动态注入，
    而不是将完整的 MEMORY.md 放入 System Prompt
    """
    set_rag_mode(request.enabled)
    return {"enabled": request.enabled}


@router.get("/config/multi-agent-mode")
async def get_multi_agent_mode_status():
    """
    获取多Agent模式状态

    开启后，复杂任务会自动分发给合适的Domain Agent执行
    """
    return {"enabled": get_multi_agent_mode()}


@router.put("/config/multi-agent-mode")
async def set_multi_agent_mode_status(request: MultiAgentModeRequest):
    """
    切换多Agent模式

    启用后，系统会自动分析任务类型：
    - 简单任务：由Primary Agent直接执行
    - 数据处理任务：分发给data_agent
    - 代码开发任务：分发给code_agent
    - 信息检索任务：分发给research_agent
    - 内容创作任务：分发给creative_agent
    """
    set_multi_agent_mode(request.enabled)
    return {"enabled": request.enabled}


@router.get("/config")
async def get_all_config():
    """获取所有配置状态"""
    return {
        "rag_mode": get_rag_mode(),
        "multi_agent_mode": get_multi_agent_mode(),
    }
