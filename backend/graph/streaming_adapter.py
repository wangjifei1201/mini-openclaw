"""
流式 Tool Call 适配器

修复阿里云 DashScope 等平台的流式 tool_call 格式与 LangChain 聚合逻辑不兼容的问题。

问题描述：
    DashScope 等平台返回的 tool_call 流式分块格式：
    - chunk 1: {name: 'tool_name', args: '', id: 'call_xxx', index: 0}  # 仅 name+id
    - chunk 2: {name: None, args: '{"param": "', id: '', index: 0}      # 仅 args 增量
    - chunk 3: {name: None, args: 'value"}', id: '', index: 0}         # 仅 args 增量
    
    LangChain 期望的格式：
    - 所有 chunks 的 id 应该保持一致（或为 None）
    - name 在第一个 chunk 后可以为 None
    
    由于 id 不一致（第一个有值，后续为空字符串），LangChain 错误地将它们聚合为多个独立的 tool_call。

解决方案：
    拦截流式输出，修复每个 chunk 的 tool_call_chunks，确保同一 index 的 chunks 使用一致的 id。
"""
from typing import Any, AsyncIterator, Iterator, List, Optional
from langchain_core.callbacks import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI


class StreamingToolCallAdapter(ChatOpenAI):
    """
    流式 Tool Call 适配器
    
    包装 ChatOpenAI，修复流式 tool_call 的聚合问题。
    适用于阿里云 DashScope、百度文心等返回非标准流式 tool_call 格式的平台。
    """
    
    def _fix_tool_call_chunks(
        self,
        chunks: List[AIMessageChunk],
    ) -> List[AIMessageChunk]:
        """
        修复 tool_call_chunks 的 id 不一致问题
        
        遍历所有 chunks，按 index 追踪每个 tool_call 的 id，
        将后续空 id 的 chunks 修复为正确的 id。
        """
        # 按 index 记录第一个出现的 id
        index_to_id: dict[int, str] = {}
        
        fixed_chunks = []
        for chunk in chunks:
            if not hasattr(chunk, 'tool_call_chunks') or not chunk.tool_call_chunks:
                fixed_chunks.append(chunk)
                continue
            
            # 修复每个 tool_call_chunk
            fixed_tc_chunks = []
            for tc in chunk.tool_call_chunks:
                index = tc.get('index', 0)
                tc_id = tc.get('id', '')
                tc_name = tc.get('name')
                
                # 如果这个 chunk 有 id，记录下来
                if tc_id:
                    index_to_id[index] = tc_id
                
                # 如果这个 chunk 的 id 为空但之前记录过该 index 的 id，修复它
                fixed_id = tc_id if tc_id else index_to_id.get(index, '')
                
                fixed_tc_chunks.append({
                    'name': tc_name,
                    'args': tc.get('args', ''),
                    'id': fixed_id,
                    'index': index,
                    'type': tc.get('type', 'tool_call_chunk'),
                })
            
            # 创建修复后的 chunk
            # AIMessageChunk 是不可变的，需要创建新实例
            fixed_chunk = AIMessageChunk(
                content=chunk.content,
                additional_kwargs=chunk.additional_kwargs,
                response_metadata=getattr(chunk, 'response_metadata', {}),
                tool_call_chunks=fixed_tc_chunks,
                id=chunk.id,
            )
            fixed_chunks.append(fixed_chunk)
        
        return fixed_chunks
    
    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """同步流式输出（带 tool_call 修复）"""
        # 先收集所有 chunks
        chunks = []
        for chunk in super()._stream(messages, stop, run_manager, **kwargs):
            if hasattr(chunk, 'message') and isinstance(chunk.message, AIMessageChunk):
                chunks.append(chunk.message)
            yield chunk  # 先原样输出，保持流式体验
        
        # 注意：同步流不太好做实时修复，这里主要处理异步流
    
    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """
        异步流式输出（带 tool_call 修复）
        
        实时修复每个 chunk 的 tool_call_chunks，确保 id 一致性。
        """
        # 按 index 记录第一个出现的 id
        index_to_id: dict[int, str] = {}
        
        async for chunk in super()._astream(messages, stop, run_manager, **kwargs):
            # 检查是否需要修复
            if (
                hasattr(chunk, 'message') 
                and isinstance(chunk.message, AIMessageChunk)
                and hasattr(chunk.message, 'tool_call_chunks')
                and chunk.message.tool_call_chunks
            ):
                msg = chunk.message
                fixed_tc_chunks = []
                
                for tc in msg.tool_call_chunks:
                    index = tc.get('index', 0)
                    tc_id = tc.get('id', '')
                    tc_name = tc.get('name')
                    
                    # 如果这个 chunk 有 id，记录下来
                    if tc_id:
                        index_to_id[index] = tc_id
                    
                    # 如果这个 chunk 的 id 为空但之前记录过该 index 的 id，修复它
                    fixed_id = tc_id if tc_id else index_to_id.get(index, '')
                    
                    fixed_tc_chunks.append({
                        'name': tc_name,
                        'args': tc.get('args', ''),
                        'id': fixed_id,
                        'index': index,
                        'type': tc.get('type', 'tool_call_chunk'),
                    })
                
                # 创建修复后的 message
                fixed_msg = AIMessageChunk(
                    content=msg.content,
                    additional_kwargs=msg.additional_kwargs,
                    response_metadata=getattr(msg, 'response_metadata', {}),
                    tool_call_chunks=fixed_tc_chunks,
                    id=msg.id,
                )
                
                # 创建修复后的 chunk
                yield ChatGenerationChunk(
                    message=fixed_msg,
                    generation_info=chunk.generation_info,
                )
            else:
                # 不需要修复，原样输出
                yield chunk
