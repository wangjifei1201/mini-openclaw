"""
对话压缩 API
"""
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from graph import agent_manager


router = APIRouter()


@router.post("/sessions/{session_id}/compress")
async def compress_session(session_id: str):
    """
    压缩对话历史
    
    流程：
    1. 检查消息数量 ≥ 4
    2. 取前 50% 消息（最少 4 条）
    3. 调用 DeepSeek 生成中文摘要（≤ 500 字）
    4. 归档 + 写入摘要
    
    Returns:
        archived_count: 归档的消息数
        remaining_count: 剩余的消息数
    """
    # 获取消息
    messages = agent_manager.session_manager.load_session(session_id)
    
    if len(messages) < 4:
        raise HTTPException(
            status_code=400,
            detail="消息数量不足，至少需要 4 条消息才能压缩"
        )
    
    # 计算要压缩的消息数（前 50%，最少 4 条）
    n = max(4, len(messages) // 2)
    
    # 提取要压缩的消息内容
    to_compress = messages[:n]
    conversation_text = ""
    for msg in to_compress:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if role == "user":
            conversation_text += f"用户：{content}\n"
        elif role == "assistant":
            conversation_text += f"助手：{content}\n"
    
    # 调用 LLM 生成摘要
    try:
        from langchain_openai import ChatOpenAI
        from config import settings
        
        llm = ChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL,
            api_key=settings.OPENAI_CHAT_API_KEY,
            base_url=settings.OPENAI_CHAT_BASE_URL,
            temperature=0.3,
        )
        
        prompt = f"""请将以下对话内容压缩成一段简洁的中文摘要，不超过 500 字。
重点保留关键信息、用户偏好和重要结论，忽略寒暄和无关紧要的细节。

对话内容：
{conversation_text}

请直接输出摘要，不要添加任何前缀或解释："""
        
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        summary = response.content.strip()
        
        # 限制摘要长度
        if len(summary) > 500:
            summary = summary[:500] + "..."
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成摘要失败: {str(e)}")
    
    # 压缩历史
    archived_count = agent_manager.session_manager.compress_history(
        session_id, summary, n
    )
    
    # 获取剩余消息数
    remaining_messages = agent_manager.session_manager.load_session(session_id)
    remaining_count = len(remaining_messages)
    
    return {
        "archived_count": archived_count,
        "remaining_count": remaining_count,
        "summary": summary,
    }
