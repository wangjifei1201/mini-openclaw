"""
结构化记忆 API - 只读查看 memories.jsonl
"""
from fastapi import APIRouter

from graph import agent_manager


router = APIRouter()


@router.get("/memories")
async def list_memories():
    """列出结构化记忆记录。"""
    memory_store = getattr(agent_manager, "memory_store", None)
    if not memory_store:
        return {"memories": []}
    return {"memories": memory_store.list_all()}
