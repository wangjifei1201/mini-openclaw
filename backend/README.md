# Mini-OpenClaw Backend

轻量级、全透明的 AI Agent 系统后端服务。基于 FastAPI + LangChain 构建，支持 SSE 流式输出。

## 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| Web 框架 | FastAPI + Uvicorn | FastAPI ≥0.109.0 |
| Agent 引擎 | LangChain 1.x | ≥0.3.0 |
| LLM | DeepSeek (langchain-deepseek) | - |
| RAG | LlamaIndex Core + BM25 | ≥0.11.0 |
| Embedding | OpenAI text-embedding-3-small | - |

## 项目结构

```
backend/
├── app.py                      # FastAPI 入口，端口 8002
├── config.py                   # 全局配置管理
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量示例
│
├── api/                        # API 路由层
│   ├── __init__.py
│   ├── chat.py                 # SSE 流式对话接口
│   ├── sessions.py             # 会话管理 CRUD
│   ├── files.py                # 文件读写/上传
│   ├── skills.py               # 技能列表查询
│   ├── tokens.py               # Token 计数统计
│   ├── compress.py             # 会话历史压缩
│   └── config_api.py           # RAG 模式配置
│
├── graph/                      # Agent 核心逻辑
│   ├── __init__.py
│   ├── agent.py                # AgentManager - LLM + 工具管理
│   ├── session_manager.py      # 会话历史管理
│   ├── prompt_builder.py       # System Prompt 动态拼接
│   ├── memory_indexer.py       # MEMORY.md 向量索引构建
│   └── streaming_adapter.py    # SSE 流式工具输出适配器
│
├── tools/                      # 核心工具集
│   ├── __init__.py
│   ├── terminal_tool.py        # Shell 命令执行 (沙箱化)
│   ├── python_repl_tool.py     # Python 代码执行
│   ├── fetch_url_tool.py       # 网页内容获取
│   ├── read_file_tool.py       # 项目文件读取
│   ├── search_knowledge_tool.py # RAG 语义检索
│   └── skills_scanner.py       # SKILL.md 扫描器
│
├── workspace/                  # System Prompt 组件
│   ├── SOUL.md                 # 人格、语气、边界
│   ├── IDENTITY.md             # Agent 名称、风格定义
│   ├── USER.md                 # 用户画像
│   └── AGENTS.md               # 操作指南 & 协议
│
├── memory/                     # 长期记忆
│   └── MEMORY.md               # 跨会话记忆 (RAG 索引源)
│
├── skills/                     # Agent 技能目录
│   ├── docx/                   # Word 文档处理技能
│   │   ├── SKILL.md
│   │   └── scripts/
│   └── web-artifacts-builder/  # Web 产物构建技能
│       ├── SKILL.md
│       └── scripts/
│
├── knowledge/                  # 知识库文档目录
├── sessions/                   # 会话历史存储目录
└── outputs/                   # Agent 输出文件目录
```

## 核心模块

### 1. API 路由 (`api/`)

| 文件 | 功能 |
|------|------|
| `chat.py` | `/api/chat` - SSE 流式对话，支持 tool_call 事件推送 |
| `sessions.py` | `/api/sessions` - 会话 CRUD、历史查询 |
| `files.py` | `/api/files` - 文件读取、保存、上传 |
| `skills.py` | `/api/skills` - 列出可用技能 |
| `tokens.py` | `/api/tokens/*` - Token 计数统计 |
| `compress.py` | `/api/sessions/{id}/compress` - 会话历史压缩 |
| `config_api.py` | `/api/config/rag-mode` - RAG 模式开关 |

### 2. Agent 引擎 (`graph/`)

**AgentManager** (`agent.py`):
- 初始化 LLM 实例 (DeepSeek)
- 注册 5 个核心工具
- 管理 tool_calling_agent 生命周期

**PromptBuilder** (`prompt_builder.py`):
- 动态拼接 6 部分 System Prompt:
  1. `SKILLS_SNAPSHOT.md` - 可用技能清单
  2. `workspace/SOUL.md` - 人格、语气
  3. `workspace/IDENTITY.md` - 名称、风格
  4. `workspace/USER.md` - 用户画像
  5. `workspace/AGENTS.md` - 操作指南
  6. `memory/MEMORY.md` - 长期记忆

**MemoryIndexer** (`memory_indexer.py`):
- 构建 `MEMORY.md` 的向量索引 (LlamaIndex)
- 支持 BM25 + 向量混合检索

**SessionManager** (`session_manager.py`):
- 维护会话消息历史
- 支持消息追加、摘要压缩

### 3. 工具集 (`tools/`)

| 工具 | 名称 | 功能 |
|------|------|------|
| `terminal_tool` | 终端 | 执行 Shell 命令 (沙箱化, 30s 超时) |
| `python_repl_tool` | Python 解释器 | 执行 Python 代码片段 |
| `fetch_url_tool` | 网络请求 | 获取网页内容 (15s 超时) |
| `read_file_tool` | 文件读取 | 读取项目内任意 Markdown/文本文件 |
| `search_knowledge_tool` | 知识库搜索 | RAG 语义检索 + BM25 混合 |

## 启动方式

### 环境配置

```bash
cd backend
cp .env.example .env
```

编辑 `.env`:

```env
# Agent 主模型 (DeepSeek)
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 或使用其他 OpenAI 兼容接口
OPENAI_CHAT_API_KEY=sk-xxx
OPENAI_CHAT_BASE_URL=https://api.openai.com/v1
OPENAI_CHAT_MODEL=gpt-4o

# Embedding 模型
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
```

### 安装依赖

```bash
pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
```

### 启动服务

```bash
# 方式一: 直接运行
python -m uvicorn app:app --port 8002 --host 0.0.0.0 --reload

# 方式二: 使用脚本
../start-backend.sh
```

服务启动时自动执行:
1. 扫描 `skills/*/SKILL.md` → 生成 `SKILLS_SNAPSHOT.md`
2. 初始化 Agent (LLM + 工具注册)
3. 构建 `MEMORY.md` 向量索引 (若文件存在)

## 技能系统

技能以 Markdown 文件形式存在于 `skills/` 目录。Agent 通过 `read_file` 工具读取 `SKILL.md` 来学习技能。

### 添加新技能

1. 在 `skills/` 下创建目录, 如 `my-skill/`
2. 创建 `SKILL.md`:

```markdown
---
name: 技能名称
description: 技能描述
---

# 技能说明

## 使用步骤
1. 第一步...
2. 第二步...
```

3. 重启后端服务

## API 接口

| 路径 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 根路径, 返回服务信息 |
| `/health` | GET | 健康检查 |
| `/api/chat` | POST | SSE 流式对话 |
| `/api/sessions` | GET | 获取会话列表 |
| `/api/sessions` | POST | 创建新会话 |
| `/api/sessions/{id}` | GET | 获取会话历史 |
| `/api/sessions/{id}` | PUT | 重命名会话 |
| `/api/sessions/{id}` | DELETE | 删除会话 |
| `/api/sessions/{id}/compress` | POST | 压缩会话历史 |
| `/api/files` | GET | 读取文件 |
| `/api/files` | POST | 保存文件 |
| `/api/files/upload` | POST | 上传文件 |
| `/api/skills` | GET | 列出可用技能 |
| `/api/tokens/session/{id}` | GET | 会话 Token 统计 |
| `/api/config/rag-mode` | GET | 获取 RAG 模式状态 |
| `/api/config/rag-mode` | PUT | 设置 RAG 模式 |

## 配置说明

`config.py` 中的 `Settings` 类:

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `OPENAI_CHAT_MODEL` | gpt-4o | Agent 主模型 |
| `EMBEDDING_MODEL` | text-embedding-3-small | Embedding 模型 |
| `WORKSPACE_DIR` | backend/workspace | System Prompt 目录 |
| `MEMORY_DIR` | backend/memory | 记忆存储目录 |
| `SKILLS_DIR` | backend/skills | 技能目录 |
| `MAX_CONTENT_LENGTH` | 20000 | System Prompt 组件最大字符数 |
| `MAX_OUTPUT_LENGTH` | 5000 | 工具输出最大字符数 |
| `COMMAND_TIMEOUT` | 30 | Shell 命令超时(秒) |
| `FETCH_TIMEOUT` | 15 | 网络请求超时(秒) |

## 开发说明

### 添加新工具

1. 在 `tools/` 下创建 `xxx_tool.py`
2. 继承 `BaseTool` 实现 `name`, `description`, `_run()` 方法
3. 在 `agent.py` 的 `AgentManager` 中注册:

```python
from tools.xxx_tool import MyTool

self.tools.append(MyTool())
```

### 修改 System Prompt

编辑 `workspace/` 下的 Markdown 文件:
- `SOUL.md`: Agent 人格、语气
- `IDENTITY.md`: 名称、风格
- `USER.md`: 用户画像
- `AGENTS.md`: 操作指南

### RAG 模式

启用后, `MEMORY.md` 不再完整注入, 而是通过语义检索动态注入相关片段:

```bash
# 开启
curl -X PUT http://localhost:8002/api/config/rag-mode \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

---

由 [wangjifei]() 提供技术支持
