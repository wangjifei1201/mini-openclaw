"""
聊天 API - SSE 流式对话
"""
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from graph import agent_manager


router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: str
    stream: bool = True


async def event_generator(
    message: str,
    session_id: str,
    is_first_message: bool
):
    """
    SSE 事件生成器
    
    Args:
        message: 用户消息
        session_id: 会话ID
        is_first_message: 是否为首条消息
    """
    # 记录响应段
    segments = []
    current_segment = ""
    current_tool_calls = []
    
    async for event in agent_manager.astream(message, session_id):
        event_type = event.get("type", "")
        
        # RAG 检索结果
        if event_type == "retrieval":
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        
        # Token 输出
        elif event_type == "token":
            content = event.get("content", "")
            current_segment += content
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        
        # 工具调用开始
        elif event_type == "tool_start":
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        
        # 工具调用结束
        elif event_type == "tool_end":
            current_tool_calls.append({
                "tool": event.get("tool", ""),
                "input": event.get("input", ""),
                "output": event.get("output", ""),
            })
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        
        # 新响应段开始
        elif event_type == "new_response":
            # 保存当前段
            if current_segment:
                segments.append({
                    "content": current_segment,
                    "tool_calls": current_tool_calls.copy(),
                })
            current_segment = ""
            current_tool_calls = []
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        
        # 完成
        elif event_type == "done":
            # 保存最后一段
            final_content = event.get("content", "")
            if final_content or current_segment:
                segments.append({
                    "content": final_content or current_segment,
                    "tool_calls": event.get("tool_calls", []),
                })
            
            # 保存用户消息
            agent_manager.session_manager.save_message(
                session_id, "user", message
            )
            
            # 保存每段助手消息
            for seg in segments:
                agent_manager.session_manager.save_message(
                    session_id,
                    "assistant",
                    seg["content"],
                    seg.get("tool_calls")
                )
            
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            
            # 首条消息自动生成标题
            if is_first_message:
                try:
                    title = await agent_manager.generate_title(message)
                    agent_manager.session_manager.update_title(session_id, title)
                    yield f"data: {json.dumps({'type': 'title', 'session_id': session_id, 'title': title}, ensure_ascii=False)}\n\n"
                except Exception:
                    pass
        
        # 错误
        elif event_type == "error":
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    聊天接口 - SSE 流式输出
    
    事件类型：
    - retrieval: RAG 检索结果
    - token: LLM 输出的 token
    - tool_start: 工具调用开始
    - tool_end: 工具调用结束
    - new_response: 新的响应段开始
    - done: 完成
    - title: 自动生成的标题（首条消息）
    - error: 错误
    """
    # 检查是否为首条消息
    history = agent_manager.session_manager.load_session(request.session_id)
    is_first_message = len(history) == 0
    
    if request.stream:
        return StreamingResponse(
            event_generator(request.message, request.session_id, is_first_message),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    else:
        # 非流式响应
        full_content = ""
        tool_calls = []
        
        async for event in agent_manager.astream(request.message, request.session_id):
            if event.get("type") == "token":
                full_content += event.get("content", "")
            elif event.get("type") == "done":
                tool_calls = event.get("tool_calls", [])
        
        # 保存消息
        agent_manager.session_manager.save_message(
            request.session_id, "user", request.message
        )
        agent_manager.session_manager.save_message(
            request.session_id, "assistant", full_content, tool_calls
        )
        
        return {
            "content": full_content,
            "tool_calls": tool_calls,
            "session_id": request.session_id,
        }
