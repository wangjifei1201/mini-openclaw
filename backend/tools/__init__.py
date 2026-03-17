"""
工具注册工厂 - 统一管理5个核心工具
"""
from pathlib import Path
from typing import List

from langchain_core.tools import BaseTool

from .fetch_url_tool import create_fetch_url_tool
from .python_repl_tool import create_python_repl_tool
from .read_file_tool import create_read_file_tool
from .search_knowledge_tool import create_search_knowledge_tool
from .terminal_tool import create_terminal_tool


def get_all_tools(base_dir: Path) -> List[BaseTool]:
    """
    获取所有核心工具

    Args:
        base_dir: 项目根目录，用于沙箱限制

    Returns:
        工具类列表
    """
    tools = [
        create_terminal_tool(base_dir),
        create_python_repl_tool(),
        create_fetch_url_tool(),
        create_read_file_tool(base_dir),
        create_search_knowledge_tool(base_dir),
    ]
    return tools


__all__ = [
    "get_all_tools",
    "create_terminal_tool",
    "create_python_repl_tool",
    "create_fetch_url_tool",
    "create_read_file_tool",
    "create_search_knowledge_tool",
]
