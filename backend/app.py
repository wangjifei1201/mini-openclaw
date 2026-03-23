"""
Mini-OpenClaw 后端入口
FastAPI 应用，端口 8002
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 添加项目根目录到 Python 路径
BASE_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(BASE_DIR))

from api import (
    agents_router,
    chat_router,
    compress_router,
    config_router,
    coordination_router,
    files_router,
    sessions_router,
    skills_router,
    strategy_router,
    task_router,
    tokens_router,
)
from config import settings
from graph import agent_manager
from graph.coordinator import get_coordination_manager, init_coordination_manager
from graph.llm_task_planner import init_task_planner
from graph.prometheus import init_prometheus
from graph.task_dispatcher import init_task_dispatcher
from hooks import init_hook_manager
from skills import init_skill_manager
from tools.skills_scanner import scan_and_save_skills
from utils.context_manager import init_context_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时执行九步初始化：
    1. scan_skills() → 扫描 skills/**/SKILL.md，生成 SKILLS_SNAPSHOT.md
    2. agent_manager.initialize() → 创建 LLM 实例，注册工具
    3. memory_indexer.rebuild_index() → 构建 MEMORY.md 向量索引
    4. init_coordination_manager() → 初始化多Agent协同管理器
    5. init_task_dispatcher() → 初始化任务分发器
    6. init_task_planner() → 初始化LLM任务规划器
    7. init_hook_manager() → 初始化钩子系统
    8. init_skill_manager() → 初始化技能系统
    9. init_context_monitor() + init_prometheus() → 初始化上下文管理 & Prometheus
    """
    print("=" * 50)
    print("Mini-OpenClaw 启动中...")
    print("=" * 50)

    # 1. 扫描技能
    print("[1/9] 扫描技能目录...")
    try:
        snapshot = scan_and_save_skills(BASE_DIR)
        print(f"      已生成 SKILLS_SNAPSHOT.md")
    except Exception as e:
        print(f"      技能扫描失败: {e}")

    # 2. 初始化 Agent 管理器
    print("[2/9] 初始化 Agent 引擎...")
    try:
        agent_manager.initialize(BASE_DIR)
        print(f"      LLM: {settings.OPENAI_CHAT_MODEL}")
        print(f"      工具数: {len(agent_manager.tools)}")
    except Exception as e:
        print(f"      Agent 初始化失败: {e}")

    # 3. 构建记忆索引
    print("[3/9] 构建记忆索引...")
    try:
        if agent_manager.memory_indexer.rebuild_index():
            print("      MEMORY.md 索引已构建")
        else:
            print("      MEMORY.md 为空或不存在，跳过索引构建")
    except Exception as e:
        print(f"      索引构建失败: {e}")

    # 4. 初始化协同管理器
    print("[4/9] 初始化多Agent协同管理器...")
    try:
        init_coordination_manager(BASE_DIR)
        print("      多Agent协同系统已就绪")
    except Exception as e:
        print(f"      协同管理器初始化失败: {e}")

    # 5. 初始化任务分发器
    print("[5/9] 初始化任务分发器...")
    try:
        init_task_dispatcher(BASE_DIR, agent_manager.llm)
        print("      任务分发器已就绪")
    except Exception as e:
        print(f"      任务分发器初始化失败: {e}")

    # 6. 初始化LLM任务规划器
    print("[6/9] 初始化LLM任务规划器...")
    try:
        coordinator = get_coordination_manager()
        init_task_planner(agent_manager.llm, coordinator, BASE_DIR)
        print("      LLM任务规划器已就绪")
    except Exception as e:
        print(f"      LLM任务规划器初始化失败: {e}")

    # 7. 初始化钩子系统
    print("[7/9] 初始化钩子系统...")
    try:
        hook_mgr = init_hook_manager()
        hooks = hook_mgr.list_hooks()
        print(f"      已注册 {len(hooks)} 个钩子")
    except Exception as e:
        print(f"      钩子系统初始化失败: {e}")

    # 8. 初始化技能系统
    print("[8/9] 初始化技能系统...")
    try:
        skill_mgr = init_skill_manager(BASE_DIR)
        skills_list = skill_mgr.list_skills()
        print(f"      已加载 {len(skills_list)} 个技能")
    except Exception as e:
        print(f"      技能系统初始化失败: {e}")

    # 9. 初始化上下文管理 & Prometheus
    print("[9/9] 初始化上下文管理 & Prometheus...")
    try:
        init_context_monitor(model_limit=128000)
        init_prometheus(agent_manager.llm, coordinator, BASE_DIR)
        print("      上下文监控器 & Prometheus 已就绪")
    except Exception as e:
        print(f"      初始化失败: {e}")

    print("=" * 50)
    print(f"Mini-OpenClaw 已启动: http://localhost:8002")
    print("=" * 50)

    yield

    # 关闭时清理
    print("Mini-OpenClaw 已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="Mini-OpenClaw",
    description="轻量级、全透明的 AI Agent 系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(sessions_router, prefix="/api", tags=["Sessions"])
app.include_router(files_router, prefix="/api", tags=["Files"])
app.include_router(tokens_router, prefix="/api", tags=["Tokens"])
app.include_router(compress_router, prefix="/api", tags=["Compress"])
app.include_router(config_router, prefix="/api", tags=["Config"])
app.include_router(skills_router, prefix="/api", tags=["Skills"])
app.include_router(agents_router, prefix="/api", tags=["Agents"])
app.include_router(coordination_router, prefix="/api", tags=["Coordination"])
app.include_router(strategy_router, prefix="/api", tags=["Strategy"])
app.include_router(task_router, prefix="/api", tags=["Task"])

# 挂载静态文件目录 - outputs 文件夹可直接访问
outputs_dir = BASE_DIR / "outputs"
if outputs_dir.exists():
    app.mount("/outputs", StaticFiles(directory=str(outputs_dir)), name="outputs")
    print(f"[静态文件] outputs 目录已挂载: {outputs_dir}")


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "Mini-OpenClaw",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
    )
