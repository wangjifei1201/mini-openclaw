"""
Token 统计 API
"""
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import tiktoken

from config import BASE_DIR
from graph import agent_manager
from graph.prompt_builder import PromptBuilder
from api.files import is_path_allowed


router = APIRouter()

# 使用 cl100k_base 编码器（与 GPT-4 系列一致）
encoding = tiktoken.get_encoding("cl100k_base")


class FilesTokenRequest(BaseModel):
    """文件 Token 统计请求"""
    paths: List[str]


def count_tokens(text: str) -> int:
    """计算文本的 Token 数量"""
    return len(encoding.encode(text))


@router.get("/tokens/session/{session_id}")
async def get_session_tokens(session_id: str):
    """
    获取会话 Token 统计
    
    Returns:
        system_tokens: System Prompt Token 数
        message_tokens: 消息 Token 数
        total_tokens: 总 Token 数
    """
    # 获取 System Prompt Token 数
    builder = PromptBuilder(BASE_DIR)
    system_prompt = builder.build_system_prompt()
    system_tokens = count_tokens(system_prompt)
    
    # 获取消息 Token 数
    messages = agent_manager.session_manager.load_session(session_id)
    message_text = ""
    for msg in messages:
        message_text += msg.get("content", "") + "\n"
    message_tokens = count_tokens(message_text)
    
    return {
        "system_tokens": system_tokens,
        "message_tokens": message_tokens,
        "total_tokens": system_tokens + message_tokens,
    }


@router.post("/tokens/files")
async def get_files_tokens(request: FilesTokenRequest):
    """
    批量统计文件 Token 数
    
    Request:
        paths: 文件路径列表
        
    Returns:
        文件 Token 统计结果
    """
    results = {}
    
    for path in request.paths:
        # 路径安全检查
        if not is_path_allowed(path):
            results[path] = 0
            continue
        
        file_path = BASE_DIR / path
        if file_path.exists() and file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8")
                results[path] = count_tokens(content)
            except Exception:
                results[path] = 0
        else:
            results[path] = 0
    
    return {"tokens": results}
