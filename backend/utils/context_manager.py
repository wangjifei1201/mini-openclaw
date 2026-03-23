"""
上下文窗口管理器 - 监控和优化上下文 Token 使用

功能：
1. 实时监控 Token 使用量
2. 接近限制时触发警告
3. 超过阈值时自动压缩历史消息
4. 支持会话恢复

灵感来源: oh-my-opencode 的 context-window-monitor + session-recovery
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from utils.token_tracker import estimate_tokens


@dataclass
class ContextWindowState:
    """上下文窗口状态"""

    session_id: str
    used_tokens: int = 0
    model_limit: int = 128000
    last_check_time: float = field(default_factory=time.time)

    @property
    def usage_ratio(self) -> float:
        return self.used_tokens / self.model_limit if self.model_limit > 0 else 0

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.model_limit - self.used_tokens)


class ContextWindowMonitor:
    """
    上下文窗口监控器

    负责：
    1. 跟踪会话的 Token 使用量
    2. 根据使用率返回状态和建议
    3. 在超过阈值时触发消息压缩
    4. 保存和恢复会话状态
    """

    WARNING_THRESHOLD = 0.75  # 75% 触发警告
    CRITICAL_THRESHOLD = 0.85  # 85% 触发压缩
    COMPRESS_KEEP_RECENT = 10  # 压缩时保留最近 N 条消息

    def __init__(self, model_limit: int = 128000):
        self._default_limit = model_limit
        self._sessions: Dict[str, ContextWindowState] = {}

    def check(self, session_id: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        检查上下文窗口状态

        Args:
            session_id: 会话 ID
            messages: 当前会话消息列表

        Returns:
            状态字典：
            - status: "ok" | "warning" | "critical"
            - usage_ratio: Token 使用率
            - used_tokens: 已使用 Token 数
            - remaining_tokens: 剩余 Token 数
            - action: "none" | "warn" | "compress"
            - message: 提示信息
        """
        # 估算当前 Token 使用量
        total_tokens = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_tokens += estimate_tokens(content)

        # 更新状态
        state = self._sessions.get(session_id)
        if not state:
            state = ContextWindowState(
                session_id=session_id,
                model_limit=self._default_limit,
            )
            self._sessions[session_id] = state

        state.used_tokens = total_tokens
        state.last_check_time = time.time()

        usage = state.usage_ratio

        if usage >= self.CRITICAL_THRESHOLD:
            return {
                "status": "critical",
                "usage_ratio": usage,
                "used_tokens": total_tokens,
                "remaining_tokens": state.remaining_tokens,
                "action": "compress",
                "message": f"上下文使用率 {usage:.0%}，即将自动压缩历史消息",
            }
        elif usage >= self.WARNING_THRESHOLD:
            return {
                "status": "warning",
                "usage_ratio": usage,
                "used_tokens": total_tokens,
                "remaining_tokens": state.remaining_tokens,
                "action": "warn",
                "message": f"上下文使用率 {usage:.0%}，请注意控制消息长度",
            }
        else:
            return {
                "status": "ok",
                "usage_ratio": usage,
                "used_tokens": total_tokens,
                "remaining_tokens": state.remaining_tokens,
                "action": "none",
                "message": "",
            }

    def compress_messages(
        self,
        messages: List[Dict[str, Any]],
        llm_summary: str = None,
    ) -> List[Dict[str, Any]]:
        """
        压缩消息历史

        策略：
        1. 保留 system prompt 消息
        2. 对早期消息生成摘要
        3. 保留最近 N 条消息

        Args:
            messages: 原始消息列表
            llm_summary: LLM 生成的摘要（可选）

        Returns:
            压缩后的消息列表
        """
        if len(messages) <= self.COMPRESS_KEEP_RECENT:
            return messages

        # 分离 system 消息和对话消息
        system_messages = [m for m in messages if m.get("role") == "system"]
        chat_messages = [m for m in messages if m.get("role") != "system"]

        # 需要压缩的早期消息
        early_messages = chat_messages[: -self.COMPRESS_KEEP_RECENT]
        recent_messages = chat_messages[-self.COMPRESS_KEEP_RECENT :]

        # 生成摘要
        if llm_summary:
            summary_text = llm_summary
        else:
            summary_text = self._simple_summarize(early_messages)

        # 构建压缩后的消息列表
        compressed = list(system_messages)

        if summary_text:
            compressed.append(
                {
                    "role": "system",
                    "content": f"[会话历史摘要]\n{summary_text}",
                }
            )

        compressed.extend(recent_messages)
        return compressed

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        state = self._sessions.get(session_id)
        if not state:
            return None
        return {
            "session_id": state.session_id,
            "used_tokens": state.used_tokens,
            "model_limit": state.model_limit,
            "usage_ratio": state.usage_ratio,
            "remaining_tokens": state.remaining_tokens,
            "last_check_time": state.last_check_time,
        }

    def clear_session(self, session_id: str) -> None:
        """清除会话状态"""
        self._sessions.pop(session_id, None)

    def _simple_summarize(self, messages: List[Dict[str, Any]]) -> str:
        """
        简单摘要（不依赖 LLM）

        提取每条消息的前 100 字符，组成时间线摘要。
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                snippet = content[:100].replace("\n", " ")
                if len(content) > 100:
                    snippet += "..."
                lines.append(f"- [{role}] {snippet}")

        if not lines:
            return ""

        return f"以下是之前 {len(lines)} 条消息的摘要:\n" + "\n".join(lines)


# 全局单例
_context_monitor: Optional[ContextWindowMonitor] = None


def init_context_monitor(model_limit: int = 128000) -> ContextWindowMonitor:
    """初始化上下文监控器"""
    global _context_monitor
    _context_monitor = ContextWindowMonitor(model_limit)
    return _context_monitor


def get_context_monitor() -> Optional[ContextWindowMonitor]:
    """获取上下文监控器单例"""
    return _context_monitor
