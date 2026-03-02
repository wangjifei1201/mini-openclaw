"""
配置管理 API
"""
from fastapi import APIRouter
from pydantic import BaseModel

from config import get_rag_mode, set_rag_mode


router = APIRouter()


class RAGModeRequest(BaseModel):
    """RAG 模式设置请求"""
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
