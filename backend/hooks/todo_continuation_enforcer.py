"""
TODO Continuation Enforcer - 任务持续推进钩子

检测 Agent 是否中途放弃任务，自动生成续推进提示，
强制 Agent 继续执行直到所有 TODO 完成。

灵感来源: oh-my-opencode 的 todo-continuation-enforcer
"""

import re
from typing import Any, Dict, List

from hooks.base_hook import BaseHook, HookType

# Agent 放弃任务的常见模式
_ABANDON_PATTERNS_ZH = [
    r"我(暂时)?无法(完成|继续|处理)",
    r"需要(更多|进一步|额外)(的)?(信息|数据|说明|上下文)",
    r"(请|您)(提供|给出|补充)(更多)?",
    r"这(个|项)任务(太|过于)复杂",
    r"(建议|推荐)(人工|手动|手工)(处理|介入|操作)",
    r"(目前|暂时)(到此|先到这|就到这)",
    r"(接下来|后续)(需要|请)(你|您)(来|自行)",
    r"(超出|超过)(了)?(我的)?(能力|范围)",
]

_ABANDON_PATTERNS_EN = [
    r"i('m| am) (unable|not able) to (complete|continue|proceed)",
    r"(need|require)s? (more|additional|further) (information|context|data)",
    r"(please|could you) provide",
    r"this (task|request) is (too )?complex",
    r"(suggest|recommend) (manual|human) (intervention|review)",
    r"(beyond|outside) (my|the) (scope|capabilities)",
    r"let me (stop|pause) here",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _ABANDON_PATTERNS_ZH + _ABANDON_PATTERNS_EN]


class TodoContinuationEnforcer(BaseHook):
    """
    TODO 持续推进器

    在响应生成后检查：
    1. 是否还有未完成的 TODO
    2. Agent 是否表达了放弃意图
    3. 如果检测到放弃，注入续推进提示
    """

    @property
    def hook_type(self) -> HookType:
        return HookType.RESPONSE_GENERATED

    @property
    def priority(self) -> int:
        return 10  # 高优先级，优先检测

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查响应是否包含放弃信号，如果有且仍有未完成TODO则注入续推进提示

        context 字段:
            response: Agent 的响应文本
            pending_todos: 未完成的 TODO 列表
            task_id: 当前任务 ID
            agent_name: 当前 Agent 名称
        """
        response = context.get("response", "")
        pending_todos = context.get("pending_todos", [])

        # 没有未完成的 TODO，无需检查
        if not pending_todos:
            return context

        # 检测放弃模式
        abandon_detected = self._detect_abandon(response)

        if abandon_detected:
            continuation_prompt = self._build_continuation_prompt(
                pending_todos=pending_todos,
                agent_name=context.get("agent_name", "Agent"),
                response_snippet=response[:200],
            )
            context["needs_continuation"] = True
            context["continuation_prompt"] = continuation_prompt
            context["abandon_detected"] = True
        else:
            context["needs_continuation"] = False
            context["abandon_detected"] = False

        return context

    def _detect_abandon(self, response: str) -> bool:
        """
        检测响应中是否包含放弃信号

        Args:
            response: Agent 响应文本

        Returns:
            是否检测到放弃信号
        """
        if not response:
            return False

        for pattern in _COMPILED_PATTERNS:
            if pattern.search(response):
                return True

        return False

    def _build_continuation_prompt(
        self,
        pending_todos: List[Dict[str, Any]],
        agent_name: str,
        response_snippet: str,
    ) -> str:
        """
        构建续推进提示

        Args:
            pending_todos: 未完成的 TODO 列表
            agent_name: Agent 名称
            response_snippet: 响应片段

        Returns:
            续推进提示文本
        """
        todo_list = "\n".join([f"  - [{t.get('status', 'pending')}] {t.get('content', '')}" for t in pending_todos])

        return f"""[SYSTEM REMINDER - TODO CONTINUATION]

{agent_name} 表达了中断意图，但以下任务尚未完成：

{todo_list}

请继续执行以上未完成的任务。不要放弃或转交给用户。
如果遇到困难，请尝试换一种方法解决，而不是停止工作。

具体要求：
1. 从第一个未完成的任务开始继续执行
2. 如果某个任务确实无法用当前工具完成，标记原因并继续下一个
3. 所有任务处理完毕后再结束

请现在继续工作。"""
