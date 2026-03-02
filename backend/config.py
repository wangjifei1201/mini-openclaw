"""
全局配置管理 - 持久化到 config.json
"""
import json
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).parent.absolute()

# 配置文件路径
CONFIG_FILE = BASE_DIR / "config.json"

# 默认配置
DEFAULT_CONFIG = {
    "rag_mode": False,
}


def load_config() -> dict:
    """加载配置文件"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 合并默认配置
                return {**DEFAULT_CONFIG, **config}
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """保存配置文件"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_rag_mode() -> bool:
    """获取 RAG 模式状态"""
    config = load_config()
    return config.get("rag_mode", False)


def set_rag_mode(enabled: bool) -> None:
    """设置 RAG 模式状态"""
    config = load_config()
    config["rag_mode"] = enabled
    save_config(config)


# 环境变量配置
class Settings:
    """应用设置"""
    
    # Agent 主模型配置（兼容所有 OpenAI 接口风格的大模型）
    OPENAI_CHAT_API_KEY: str = os.getenv("OPENAI_CHAT_API_KEY", "")
    OPENAI_CHAT_BASE_URL: str = os.getenv("OPENAI_CHAT_BASE_URL", "https://api.openai.com/v1")
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
    
    # Embedding 模型配置
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    # 路径配置
    WORKSPACE_DIR: Path = BASE_DIR / "workspace"
    MEMORY_DIR: Path = BASE_DIR / "memory"
    SESSIONS_DIR: Path = BASE_DIR / "sessions"
    SKILLS_DIR: Path = BASE_DIR / "skills"
    KNOWLEDGE_DIR: Path = BASE_DIR / "knowledge"
    STORAGE_DIR: Path = BASE_DIR / "storage"
    
    # 限制配置
    MAX_CONTENT_LENGTH: int = 20000  # System Prompt 组件最大字符数
    MAX_OUTPUT_LENGTH: int = 5000    # 工具输出最大字符数
    COMMAND_TIMEOUT: int = 30        # 命令执行超时时间(秒)
    FETCH_TIMEOUT: int = 15          # 网络请求超时时间(秒)


settings = Settings()
