"""
会话管理 API
"""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from graph import agent_manager


router = APIRouter()


class RenameRequest(BaseModel):
    """重命名请求"""
    title: str


@router.get("/sessions")
async def list_sessions():
    """获取所有会话列表"""
    sessions = agent_manager.session_manager.list_sessions()
    return {"sessions": sessions}


@router.post("/sessions")
async def create_session():
    """创建新会话"""
    session_id = str(uuid.uuid4())
    # 初始化空会话
    agent_manager.session_manager.save_message(session_id, "system", "")
    # 删除 system 消息（只是为了创建文件）
    data = agent_manager.session_manager._read_file(session_id)
    data["messages"] = []
    agent_manager.session_manager._write_file(session_id, data)
    
    return {
        "session_id": session_id,
        "title": "新对话",
    }


@router.put("/sessions/{session_id}")
async def rename_session(session_id: str, request: RenameRequest):
    """重命名会话"""
    agent_manager.session_manager.update_title(session_id, request.title)
    return {"success": True, "title": request.title}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    success = agent_manager.session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    """
    获取完整消息（含 System Prompt）
    
    用于调试和检查
    """
    from graph.prompt_builder import PromptBuilder
    from config import BASE_DIR
    
    # 获取 System Prompt
    builder = PromptBuilder(BASE_DIR)
    system_prompt = builder.build_system_prompt()
    
    # 获取会话历史
    messages = agent_manager.session_manager.load_session(session_id)
    
    return {
        "system_prompt": system_prompt,
        "messages": messages,
    }


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str):
    """
    获取对话历史（不含 System Prompt，含 tool_calls）
    
    用于前端显示
    """
    messages = agent_manager.session_manager.load_session(session_id)
    return {"messages": messages}


@router.post("/sessions/{session_id}/generate-title")
async def generate_title(session_id: str):
    """AI 生成标题"""
    messages = agent_manager.session_manager.load_session(session_id)
    
    if not messages:
        raise HTTPException(status_code=400, detail="No messages in session")
    
    # 获取第一条用户消息
    first_user_msg = None
    for msg in messages:
        if msg.get("role") == "user":
            first_user_msg = msg.get("content", "")
            break
    
    if not first_user_msg:
        raise HTTPException(status_code=400, detail="No user message found")
    
    title = await agent_manager.generate_title(first_user_msg)
    agent_manager.session_manager.update_title(session_id, title)
    
    return {"title": title}
