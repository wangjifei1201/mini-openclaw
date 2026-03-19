# Mini-OpenClaw

一个轻量级、全透明的 AI Agent 系统。强调文件驱动（Markdown/JSON 取代向量数据库）、指令式技能（而非 function-calling）、以及 Agent 全部操作过程的可视化。

## 特性

- **文件即记忆 (File-first Memory)**：所有记忆以人类可读的 Markdown 文件形式存在
- **技能即插件 (Skills as Plugins)**：通过 SKILL.md 文件定义技能，拖入即用
- **透明可控**：所有操作过程对开发者完全透明

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI + Uvicorn | 异步 HTTP + SSE 流式推送 |
| Agent 引擎 | LangChain 1.x | create_tool_calling_agent |
| LLM | DeepSeek | 通过 langchain-deepseek 接入 |
| RAG | LlamaIndex Core | 向量检索 + BM25 混合搜索 |
| 前端框架 | Next.js 14 | App Router + TypeScript |
| UI | Tailwind CSS | Apple 风格毛玻璃效果 |
| 代码编辑器 | Monaco Editor | 在线编辑 Memory/Skill 文件 |

## 项目结构

```
mini-openclaw/
├── backend/                # FastAPI + LangChain
│   ├── app.py              # 入口文件 (Port 8002)
│   ├── config.py           # 全局配置
│   ├── api/                # API 路由层
│   ├── graph/              # Agent 核心逻辑
│   ├── tools/              # 5 个核心工具
│   ├── workspace/          # System Prompts
│   ├── memory/             # 长期记忆
│   ├── skills/             # Agent Skills
│   ├── knowledge/          # 知识库文档
│   └── sessions/           # 会话存储
│
├── frontend/               # Next.js 14+
│   └── src/
│       ├── app/            # 页面
│       ├── components/     # UI 组件
│       └── lib/            # 状态管理 & API
│
├── start.sh                # 一键启动脚本
├── start-backend.sh        # 后端单独启动脚本
├── start-frontend.sh       # 前端单独启动脚本
└── README.md
```

## 环境配置

### 1. 克隆项目

```bash
cd mini-openclaw
```

### 2. 配置环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件，填入 API Key：

```env
# DeepSeek (Agent 主模型)
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# OpenAI (Embedding 模型)
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
```

## 快速启动

### 方式一：一键启动

```bash
chmod +x start.sh
./start.sh
```

### 方式二：分别启动（推荐调试时使用）

需要打开两个终端窗口：

**终端1 - 启动后端**
```bash
./start-backend.sh
```

**终端2 - 启动前端**
```bash
./start-frontend.sh
```

### 方式三：手动启动

**启动后端（端口 8002）**

```bash
cd backend
pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
python3 -m uvicorn app:app --port 8002 --host 0.0.0.0 --reload
```

**启动前端（端口 3000）**

```bash
cd frontend
npm install
npm run dev
```

### 访问

- 本机访问：http://localhost:3000
- 局域网访问：http://<本机IP>:3000

## 核心工具

| 工具 | 名称 | 功能 |
|------|------|------|
| terminal | 终端 | 执行 Shell 命令（沙箱化） |
| python_repl | Python 解释器 | 执行 Python 代码 |
| fetch_url | 网络请求 | 获取网页内容 |
| read_file | 文件读取 | 读取项目内文件 |
| search_knowledge_base | 知识库搜索 | RAG 语义检索 |

## 技能系统

技能以 Markdown 文件形式存在于 `backend/skills/` 目录下。Agent 通过 `read_file` 工具读取 SKILL.md 来学习技能。

### 添加新技能

1. 在 `backend/skills/` 下创建新目录
2. 创建 `SKILL.md` 文件，包含 YAML frontmatter：

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

3. 重启后端服务，技能会自动加载

## API 接口

| 路径 | 方法 | 说明 |
|------|------|------|
| /api/chat | POST | SSE 流式对话 |
| /api/sessions | GET/POST | 会话列表/创建 |
| /api/sessions/{id} | PUT/DELETE | 重命名/删除会话 |
| /api/sessions/{id}/compress | POST | 压缩对话历史 |
| /api/files | GET/POST | 读取/保存文件 |
| /api/skills | GET | 列出技能 |
| /api/tokens/session/{id} | GET | Token 统计 |
| /api/config/rag-mode | GET/PUT | RAG 模式开关 |

## 开发说明

### System Prompt 组成

System Prompt 由以下 6 部分动态拼接：

1. `SKILLS_SNAPSHOT.md` - 可用技能清单
2. `workspace/SOUL.md` - 人格、语气、边界
3. `workspace/IDENTITY.md` - 名称、风格
4. `workspace/USER.md` - 用户画像
5. `workspace/AGENTS.md` - 操作指南 & 协议
6. `memory/MEMORY.md` - 跨会话长期记忆

### RAG 模式

启用 RAG 模式后，`MEMORY.md` 不再完整注入 System Prompt，而是通过语义检索动态注入相关片段。

### 快速体验地址
[Omni-OpenClaw](http://82.157.98.72:5004/)

## 许可证

MIT License

---

由 [wangjifei](http://82.157.98.72:5004/) 提供技术支持
