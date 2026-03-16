"""
Mini-OpenClaw 后端入口
FastAPI 应用，端口 8002
"""
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 添加项目根目录到 Python 路径
BASE_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(BASE_DIR))

from config import settings
from tools.skills_scanner import scan_and_save_skills
from graph import agent_manager
from api import (
    chat_router,
    sessions_router,
    files_router,
    tokens_router,
    compress_router,
    config_router,
    skills_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    启动时执行三步初始化：
    1. scan_skills() → 扫描 skills/**/SKILL.md，生成 SKILLS_SNAPSHOT.md
    2. agent_manager.initialize() → 创建 LLM 实例，注册工具
    3. memory_indexer.rebuild_index() → 构建 MEMORY.md 向量索引
    """
    print("=" * 50)
    print("Mini-OpenClaw 启动中...")
    print("=" * 50)
    
    # 1. 扫描技能
    print("[1/3] 扫描技能目录...")
    try:
        snapshot = scan_and_save_skills(BASE_DIR)
        print(f"      已生成 SKILLS_SNAPSHOT.md")
    except Exception as e:
        print(f"      技能扫描失败: {e}")
    
    # 2. 初始化 Agent 管理器
    print("[2/3] 初始化 Agent 引擎...")
    try:
        agent_manager.initialize(BASE_DIR)
        print(f"      LLM: {settings.OPENAI_CHAT_MODEL}")
        print(f"      工具数: {len(agent_manager.tools)}")
    except Exception as e:
        print(f"      Agent 初始化失败: {e}")
    
    # 3. 构建记忆索引
    print("[3/3] 构建记忆索引...")
    try:
        if agent_manager.memory_indexer.rebuild_index():
            print("      MEMORY.md 索引已构建")
        else:
            print("      MEMORY.md 为空或不存在，跳过索引构建")
    except Exception as e:
        print(f"      索引构建失败: {e}")
    
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
