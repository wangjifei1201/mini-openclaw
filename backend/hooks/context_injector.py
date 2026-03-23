"""
Context Injector Hook - 上下文注入钩子

在用户提交消息时，自动注入相关上下文信息：
- AGENTS.md 内容
- 当前任务状态
- 协同快照信息
"""

from pathlib import Path
from typing import Any, Dict

from hooks.base_hook import BaseHook, HookType


class ContextInjectorHook(BaseHook):
    """
    上下文注入器

    在 UserPromptSubmit 阶段自动检测消息中的关键词，
    注入相关的上下文信息到消息中。
    """

    @property
    def hook_type(self) -> HookType:
        return HookType.USER_PROMPT_SUBMIT

    @property
    def priority(self) -> int:
        return 20

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        检测消息并注入上下文

        context 字段:
            message: 用户原始消息
            session_id: 会话 ID
            base_dir: 项目根目录 (可选)
        """
        message = context.get("message", "")
        base_dir = context.get("base_dir")

        if not base_dir:
            return context

        base_path = Path(base_dir) if isinstance(base_dir, str) else base_dir
        injections = []

        # 检测是否需要注入协同状态
        coordination_keywords = ["任务", "状态", "进度", "agent", "协同"]
        if any(kw in message.lower() for kw in coordination_keywords):
            snapshot = self._read_coordination_snapshot(base_path)
            if snapshot:
                injections.append(f"\n[当前协同状态]\n{snapshot}")

        if injections:
            context["injected_context"] = "\n".join(injections)

        return context

    def _read_coordination_snapshot(self, base_dir: Path) -> str:
        """读取协同状态快照"""
        snapshot_path = base_dir / "workspace" / "coordination" / "COORDINATION_SNAPSHOT.md"
        if snapshot_path.exists():
            try:
                content = snapshot_path.read_text(encoding="utf-8")
                # 截取关键部分
                if len(content) > 1000:
                    content = content[:1000] + "\n...[truncated]"
                return content
            except Exception:
                pass
        return ""
