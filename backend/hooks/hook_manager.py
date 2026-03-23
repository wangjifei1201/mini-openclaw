"""
钩子管理器 - 注册、管理和触发钩子
"""

from typing import Any, Dict, List, Optional

from hooks.base_hook import BaseHook, HookType


class HookManager:
    """
    钩子管理器

    负责：
    1. 注册和注销钩子
    2. 按类型和优先级管理钩子
    3. 触发钩子链式执行
    4. 错误隔离（单个钩子失败不影响其他钩子）
    """

    def __init__(self):
        self._hooks: Dict[HookType, List[BaseHook]] = {ht: [] for ht in HookType}

    def register(self, hook: BaseHook) -> None:
        """
        注册钩子

        Args:
            hook: 钩子实例
        """
        hook_list = self._hooks[hook.hook_type]

        # 避免重复注册
        for existing in hook_list:
            if existing.name == hook.name:
                return

        hook_list.append(hook)
        hook_list.sort(key=lambda h: h.priority)

    def unregister(self, hook_type: HookType, hook_name: str) -> bool:
        """
        注销钩子

        Args:
            hook_type: 钩子类型
            hook_name: 钩子名称

        Returns:
            是否成功注销
        """
        hook_list = self._hooks[hook_type]
        for i, hook in enumerate(hook_list):
            if hook.name == hook_name:
                hook_list.pop(i)
                return True
        return False

    async def trigger(self, hook_type: HookType, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        触发指定类型的所有钩子

        钩子按优先级顺序链式执行，前一个钩子的输出作为下一个的输入。
        单个钩子异常不会中断整个链。

        Args:
            hook_type: 钩子类型
            context: 初始上下文

        Returns:
            经过所有钩子处理后的上下文
        """
        for hook in self._hooks[hook_type]:
            if not hook.enabled:
                continue
            try:
                context = await hook.execute(context)
                # 如果钩子标记跳过，停止后续钩子
                if context.get("skip"):
                    break
            except Exception as e:
                print(f"[HookManager] Hook '{hook.name}' failed: {e}")
                context.setdefault("hook_errors", []).append({"hook": hook.name, "error": str(e)})

        return context

    def list_hooks(self, hook_type: Optional[HookType] = None) -> List[Dict[str, Any]]:
        """
        列出已注册的钩子

        Args:
            hook_type: 过滤特定类型，None 返回全部

        Returns:
            钩子信息列表
        """
        result = []
        types = [hook_type] if hook_type else list(HookType)

        for ht in types:
            for hook in self._hooks[ht]:
                result.append(
                    {
                        "name": hook.name,
                        "type": ht.value,
                        "priority": hook.priority,
                        "enabled": hook.enabled,
                    }
                )

        return result


# 全局单例
_hook_manager: Optional[HookManager] = None


def init_hook_manager() -> HookManager:
    """初始化钩子管理器并注册内置钩子"""
    global _hook_manager
    _hook_manager = HookManager()

    # 注册内置钩子
    from hooks.comment_checker import CommentCheckerHook
    from hooks.context_injector import ContextInjectorHook
    from hooks.todo_continuation_enforcer import TodoContinuationEnforcer

    _hook_manager.register(TodoContinuationEnforcer())
    _hook_manager.register(CommentCheckerHook())
    _hook_manager.register(ContextInjectorHook())

    return _hook_manager


def get_hook_manager() -> Optional[HookManager]:
    """获取钩子管理器单例"""
    return _hook_manager
