"""
钩子系统 - 生命周期拦截与扩展

提供可扩展的生命周期钩子机制，支持：
- PreToolUse: 工具调用前拦截
- PostToolUse: 工具调用后处理
- ResponseGenerated: 响应生成后处理
- TodoStatusChange: TODO 状态变更时触发
- UserPromptSubmit: 用户提交时注入
"""

from hooks.base_hook import BaseHook, HookType
from hooks.hook_manager import HookManager, get_hook_manager, init_hook_manager

__all__ = [
    "BaseHook",
    "HookType",
    "HookManager",
    "get_hook_manager",
    "init_hook_manager",
]
