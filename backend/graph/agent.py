"""
Agent 引擎 - 核心单例类，管理 Agent 的生命周期
使用 LangChain 1.x 的 create_agent API (基于 Graph 运行时)
"""
import asyncio
import re
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from config import BASE_DIR, get_rag_mode, settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from tools import get_all_tools

from .memory_indexer import MemoryIndexer
from .prompt_builder import PromptBuilder
from .session_manager import SessionManager
from .streaming_adapter import StreamingToolCallAdapter

# Agent 图执行最大步数（防止无限循环）
RECURSION_LIMIT = 50

# 连续空参数工具调用阈值，超过此值判定为流式兼容性问题
_EMPTY_TOOL_CALL_THRESHOLD = 3

# 流式兼容性错误提示
_STREAMING_COMPAT_ERROR = (
    "检测到当前大模型的流式输出格式与 LangChain 工具调用解析不兼容：\n"
    "模型返回的 tool_call 流式分块无法正确聚合，导致工具参数为空。\n\n"
    "即使启用了 StreamingToolCallAdapter 适配器仍然出现此问题，\n"
    "可能是该模型的流式格式与适配器不兼容。\n\n"
    "解决方案（任选其一）：\n"
    "1. 更换支持标准 OpenAI tool_call 流式格式的模型\n"
    "2. 检查模型提供商的 API 是否有 enable_thinking / stream_options 等参数需要调整\n"
    "3. 联系开发者扩展 streaming_adapter.py 以支持该模型"
)


class AgentManager:
    """
    Agent 管理器

    核心单例类，管理 Agent 的生命周期。
    使用 create_agent (from langchain.agents) 构建基于 Graph 运行时的 Agent。
    """

    _instance: Optional["AgentManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.base_dir: Optional[Path] = None
        self.llm: Optional[StreamingToolCallAdapter] = None
        self.tools: List = []
        self.session_manager: Optional[SessionManager] = None
        self.prompt_builder: Optional[PromptBuilder] = None
        self.memory_indexer: Optional[MemoryIndexer] = None
        self._initialized = False

    def initialize(self, base_dir: Path) -> None:
        """
        初始化 Agent 管理器

        Args:
            base_dir: 项目根目录（backend/）
        """
        self.base_dir = base_dir

        # 创建 LLM 实例
        # 使用 StreamingToolCallAdapter 修复阿里云 DashScope 等平台的流式 tool_call 聚合问题
        self.llm = StreamingToolCallAdapter(
            model=settings.OPENAI_CHAT_MODEL,
            api_key=settings.OPENAI_CHAT_API_KEY,
            base_url=settings.OPENAI_CHAT_BASE_URL,
            temperature=0.7,
            streaming=True,
        )

        # 加载工具
        self.tools = get_all_tools(base_dir)

        # 初始化会话管理器
        self.session_manager = SessionManager(base_dir / "sessions")

        # 初始化 Prompt 构建器
        self.prompt_builder = PromptBuilder(base_dir)

        # 初始化记忆索引器
        self.memory_indexer = MemoryIndexer(base_dir)

        self._initialized = True

    def _build_agent(self):
        """
        构建 Agent 实例

        每次调用都重建，确保读取最新的 System Prompt 和 RAG 配置。
        使用 create_agent API 构建基于 Graph 运行时的 Agent。
        """
        from langchain.agents import create_agent

        # 获取 System Prompt
        system_prompt = self.prompt_builder.build_system_prompt()

        # 使用 create_agent 创建基于 Graph 运行时的 Agent
        agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=system_prompt,
        )

        return agent

    def _build_messages(self, history: List[Dict[str, Any]]) -> List:
        """
        将会话历史转换为 LangChain 消息格式

        Args:
            history: 会话历史（dict 列表）

        Returns:
            LangChain 消息列表
        """
        messages = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        return messages

    async def astream(
        self, message: str, session_id: str, history: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式执行 Agent

        使用 astream_events 获取 token 级别的流式输出。
        内置流式 tool_call 兼容性检测：若连续多次出现空参数的工具调用，
        则判定当前模型的流式格式与 LangChain 不兼容，给出明确错误提示并中止任务。

        Args:
            message: 用户消息
            session_id: 会话ID
            history: 会话历史（可选，默认从文件加载）

        Yields:
            事件字典:
            - retrieval: RAG 检索结果
            - token: LLM 输出的文本
            - tool_start: 工具调用开始
            - tool_end: 工具调用结束
            - new_response: 新的响应段开始
            - done: 完成
            - error: 错误
        """
        try:
            # 加载历史
            if history is None:
                history = self.session_manager.load_session_for_agent(session_id)

            # RAG 检索
            rag_mode = get_rag_mode()
            if rag_mode:
                results = self.memory_indexer.retrieve(message, top_k=3)
                if results:
                    yield {
                        "type": "retrieval",
                        "query": message,
                        "results": results,
                    }

                    # 将检索结果追加到历史（不持久化）
                    context = self.memory_indexer.format_retrieval_context(results)
                    history.append(
                        {
                            "role": "assistant",
                            "content": context,
                        }
                    )

            # 构建 Agent (每次重建确保最新 System Prompt)
            agent = self._build_agent()

            # 转换历史消息并追加当前用户消息
            chat_history = self._build_messages(history)
            chat_history.append(HumanMessage(content=message))

            # create_agent 返回 CompiledStateGraph，输入为 {"messages": [...]}
            input_state = {"messages": chat_history}

            # 流式执行
            current_content = ""
            tool_calls = []
            consecutive_empty_tool_calls = 0  # 连续空参数工具调用计数器

            async for event in agent.astream_events(
                input_state,
                version="v2",
                config={"recursion_limit": RECURSION_LIMIT},
            ):
                kind = event.get("event", "")

                # LLM 输出 token
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token_text = chunk.content
                        # 过滤 <think>...</think> 思考标签内容
                        token_text = re.sub(
                            r"<think>.*?</think>",
                            "",
                            token_text,
                            flags=re.DOTALL,
                        )
                        # 过滤未闭合的 <think> 开始标签（流式中间态）
                        if "<think>" in token_text:
                            token_text = token_text[: token_text.index("<think>")]
                        # 过滤未闭合的 </think> 结束标签（流式中间态）
                        if "</think>" in token_text:
                            token_text = token_text[token_text.index("</think>") + len("</think>") :]
                        if token_text:
                            current_content += token_text
                            yield {
                                "type": "token",
                                "content": token_text,
                            }

                # 工具调用开始
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})

                    # 检测流式 tool_call 兼容性问题：空参数
                    if not tool_input:
                        consecutive_empty_tool_calls += 1
                        if consecutive_empty_tool_calls >= _EMPTY_TOOL_CALL_THRESHOLD:
                            yield {
                                "type": "error",
                                "error": _STREAMING_COMPAT_ERROR,
                            }
                            return  # 中止任务
                    else:
                        consecutive_empty_tool_calls = 0  # 重置计数器

                    yield {
                        "type": "tool_start",
                        "tool": tool_name,
                        "input": tool_input,
                    }

                # 工具调用结束
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output", "")

                    # ToolMessage 会包含 content/name/tool_call_id 等字段，
                    # 这里只取出真正的内容让前端显示。
                    tool_call_id = None
                    output_content = tool_output
                    if isinstance(tool_output, ToolMessage):
                        tool_call_id = getattr(tool_output, "tool_call_id", None)
                        output_content = getattr(tool_output, "content", "")

                    # 确保输出为字符串
                    if not isinstance(output_content, str):
                        output_content = str(output_content)

                    tool_calls.append(
                        {
                            "tool": tool_name,
                            "input": event.get("data", {}).get("input", {}),
                            "output": output_content,
                            "tool_call_id": tool_call_id,
                        }
                    )

                    yield {
                        "type": "tool_end",
                        "tool": tool_name,
                        "output": output_content,
                        "tool_call_id": tool_call_id,
                    }

                    # 工具执行完毕后，Agent 开始新一轮文本生成
                    yield {"type": "new_response"}
                    current_content = ""

            # 完成
            yield {
                "type": "done",
                "content": current_content,
                "session_id": session_id,
                "tool_calls": tool_calls,
            }

        except Exception as e:
            error_msg = str(e)
            # 将递归超限错误转为更友好的提示
            if "recursion limit" in error_msg.lower():
                error_msg = f"Agent 执行步数超过上限 ({RECURSION_LIMIT})，任务已中止。\n" "可能原因：工具调用陷入循环，或模型流式输出格式不兼容导致工具参数丢失。"
            yield {
                "type": "error",
                "error": error_msg,
            }

    async def generate_title(self, message: str) -> str:
        """
        生成会话标题

        Args:
            message: 首条用户消息

        Returns:
            生成的标题（≤10字中文）
        """
        try:
            prompt = f"""请为以下对话生成一个简短的中文标题，不超过10个字，直接输出标题，不要任何解释：

用户消息：{message}"""

            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            title = response.content.strip()

            # 过滤思考标签
            title = re.sub(r"<think>.*?</think>", "", title, flags=re.DOTALL).strip()

            # 限制长度
            if len(title) > 10:
                title = title[:10]

            return title

        except Exception:
            return "新对话"


# 全局单例
agent_manager = AgentManager()
