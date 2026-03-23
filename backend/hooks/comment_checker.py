"""
Comment Checker Hook - 注释质量检查器

检测 Agent 生成的代码中是否包含过度注释，
确保代码风格与人工编写的代码无异。

灵感来源: oh-my-opencode 的 comment-checker
"""

import re
from typing import Any, Dict

from hooks.base_hook import BaseHook, HookType

# 常见的 AI 过度注释模式
_EXCESSIVE_COMMENT_PATTERNS = [
    # 自解释代码的冗余注释
    r"#\s*(定义|创建|设置|获取|返回|初始化)\s*(变量|函数|方法|类|对象|实例|列表|字典)",
    r"#\s*(Define|Create|Set|Get|Return|Initialize|Import)\s+(the\s+)?",
    # 每行都注释的模式
    r"#\s*(这里|此处|以下|Here|This|The following)",
    # 显而易见的操作注释
    r"#\s*(打印|输出|Print|Output|Log)\s+(结果|result|output|message)",
    r"#\s*(检查|Check)\s+(if|whether|是否)",
    r"#\s*(循环|遍历|Loop|Iterate)\s+(through|over|遍历)",
]

_COMPILED_EXCESSIVE = [re.compile(p, re.IGNORECASE) for p in _EXCESSIVE_COMMENT_PATTERNS]


class CommentCheckerHook(BaseHook):
    """
    注释检查器

    在 PostToolUse 阶段检查工具输出中的代码注释质量。
    当检测到过度注释时，在上下文中标记警告。
    """

    @property
    def hook_type(self) -> HookType:
        return HookType.POST_TOOL_USE

    @property
    def priority(self) -> int:
        return 50

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查工具输出中的注释质量

        context 字段:
            tool_name: 工具名称
            tool_output: 工具输出内容
            agent_name: Agent 名称
        """
        tool_name = context.get("tool_name", "")
        tool_output = context.get("tool_output", "")

        # 只检查代码相关工具的输出
        if tool_name not in ("python_repl", "write_file", "terminal"):
            return context

        if not tool_output or not isinstance(tool_output, str):
            return context

        # 分析注释质量
        analysis = self._analyze_comments(tool_output)
        context["comment_analysis"] = analysis

        if analysis["excessive"]:
            context["comment_warning"] = (
                f"检测到过度注释: {analysis['comment_ratio']:.0%} 的行是注释 " f"(阈值 30%)，共 {analysis['excessive_count']} 处冗余注释"
            )

        return context

    def _analyze_comments(self, code: str) -> Dict[str, Any]:
        """
        分析代码中的注释质量

        Args:
            code: 代码文本

        Returns:
            分析结果字典
        """
        lines = code.split("\n")
        total_lines = 0
        comment_lines = 0
        excessive_count = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            total_lines += 1

            # 检测注释行（Python 风格）
            if stripped.startswith("#"):
                comment_lines += 1

                # 检测过度注释
                for pattern in _COMPILED_EXCESSIVE:
                    if pattern.search(stripped):
                        excessive_count += 1
                        break

        comment_ratio = comment_lines / total_lines if total_lines > 0 else 0

        return {
            "total_lines": total_lines,
            "comment_lines": comment_lines,
            "comment_ratio": comment_ratio,
            "excessive_count": excessive_count,
            "excessive": comment_ratio > 0.3 or excessive_count > 3,
        }
