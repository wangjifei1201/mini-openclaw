"""
API 模块 - 路由注册
"""
from .agents import router as agents_router
from .chat import router as chat_router
from .compress import router as compress_router
from .config_api import router as config_router
from .coordination import router as coordination_router
from .files import router as files_router
from .sessions import router as sessions_router
from .skills import router as skills_router
from .strategy_api import router as strategy_router
from .task_api import router as task_router
from .tokens import router as tokens_router

__all__ = [
    "chat_router",
    "sessions_router",
    "files_router",
    "tokens_router",
    "compress_router",
    "config_router",
    "skills_router",
    "agents_router",
    "coordination_router",
    "strategy_router",
    "task_router",
]
