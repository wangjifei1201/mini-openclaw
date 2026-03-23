"""
钩子基类 - 定义钩子接口和类型
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict


class HookType(str, Enum):
    """钩子类型"""

    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    RESPONSE_GENERATED = "response_generated"
    TODO_STATUS_CHANGE = "todo_status_change"


class BaseHook(ABC):
    """
    钩子基类

    所有钩子必须继承此类，实现 hook_type 属性和 execute 方法。
    """

    @property
    @abstractmethod
    def hook_type(self) -> HookType:
        """钩子类型"""
        pass

    @property
    def name(self) -> str:
        """钩子名称，默认使用类名"""
        return self.__class__.__name__

    @property
    def priority(self) -> int:
        """优先级，数字越小越先执行，默认 100"""
        return 100

    @property
    def enabled(self) -> bool:
        """是否启用，默认 True"""
        return True

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行钩子逻辑

        Args:
            context: 上下文数据，内容根据 hook_type 不同而变化：
                PRE_TOOL_USE: {"tool_name", "tool_input", "agent_name"}
                POST_TOOL_USE: {"tool_name", "tool_input", "tool_output", "agent_name", "elapsed_time"}
                USER_PROMPT_SUBMIT: {"message", "session_id"}
                RESPONSE_GENERATED: {"response", "agent_name", "task_id"}
                TODO_STATUS_CHANGE: {"todo_id", "old_status", "new_status", "agent", "content"}

        Returns:
            修改后的上下文字典。可以：
            - 修改数据（如修改 tool_input、response）
            - 添加标记（如 skip=True 跳过后续执行）
            - 添加注入内容（如 inject_prompt 注入提示）
        """
        pass
