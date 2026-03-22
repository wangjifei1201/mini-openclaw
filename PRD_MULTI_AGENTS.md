# Mini-OpenClaw 多Agents协同架构 PRD

## 1. 产品概述

### 1.1 产品定位
Mini-OpenClaw 是一个轻量级、全透明的 AI Agent 系统，支持单Agent和多Agents协同两种执行模式。用户通过统一的聊天界面与系统交互，系统根据任务复杂度自动选择最优执行策略，并在多Agent模式下提供全过程的实时审计追踪。

### 1.2 核心目标
1. **双模式执行**：同时支持单Agent直接执行和多Agents协同执行
2. **智能策略选择**：系统自动分析任务，决定使用单Agent还是多Agent执行
3. **实时可视化追踪**：多Agent模式下，前端可审计追踪系统执行的详细过程
4. **统一交互体验**：无论哪种模式，用户交互方式保持一致

---

## 2. 系统架构

### 2.1 Agent体系

```
┌─────────────────────────────────────────────────────┐
│                    用户界面层                         │
│    ChatInput → 模式切换 → 消息发送 → SSE流式接收       │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                  API网关层 (chat.py)                  │
│    策略分析 → 单Agent/多Agent分支 → SSE事件流          │
└────────┬─────────────────────────┬──────────────────┘
         │                         │
    单Agent分支                多Agent分支
         │                         │
┌────────▼────────┐  ┌────────────▼───────────────────┐
│  AgentManager   │  │     Multi-Agent Orchestrator    │
│  (Primary Agent)│  │                                 │
│  直接执行任务    │  │  TaskExecutor → 任务拆分/状态管理 │
│                 │  │  TaskDispatcher → Domain Agent调度│
│                 │  │  TokenTracker → 统计追踪         │
│                 │  │  CoordinationManager → 协同管理   │
└─────────────────┘  └──┬───────────────┬──────────────┘
                        │               │
              ┌─────────▼───┐   ┌───────▼─────────┐
              │  data_agent │   │   doc_agent      │
              │  数据分析    │   │   文档处理       │
              │  Python执行  │   │   PDF/Word解析   │
              │  可视化图表  │   │   内容提取       │
              └─────────────┘   └─────────────────┘
```

### 2.2 四种Agent角色

| Agent | 类型 | 职责 | 工具集 |
|-------|------|------|--------|
| Primary Agent | primary | 用户唯一交互入口，任务理解与结果汇总 | terminal, python_repl, fetch_url, read_file, search_knowledge_base |
| Coordinator Agent | coordinator | 多Agent协同管理，任务状态同步 | read_file, write_file, search_knowledge_base |
| Data Agent | domain | 数据分析专家，处理数据类任务 | python_repl, read_file, write_file |
| Doc Agent | domain | 文档处理专家，处理文档类任务 | python_repl, read_file, write_file |

### 2.3 文件协同协议

```
workspace/
├── coordination/
│   ├── tasks/TASK_*.md              # 任务描述文件
│   ├── responses/RESPONSE_*.md      # 任务执行结果
│   ├── notices/NOTICE_*.json        # 跨Agent通知
│   └── COORDINATION_SNAPSHOT.md     # 实时协同状态快照
├── global_memory/
│   ├── USER.md                      # 用户画像
│   ├── AGENTS_GLOBAL.md             # 全局行为准则
│   └── COORDINATION_RULES.md        # 协同规则
└── domain_agents/
    ├── data_agent/                  # Data Agent工作空间
    └── doc_agent/                   # Doc Agent工作空间
```

---

## 3. 执行模式详述

### 3.1 策略选择机制

StrategySelector 基于关键词匹配和任务特征分析，决定执行策略：

**MULTI_AGENT 触发条件**：
- 数据处理关键词：数据分析、统计分析、CSV、Excel、表格、可视化
- 文档处理关键词：PDF、Word、文档解析、内容提取
- 复杂任务特征：多步骤(先...再...)、批量处理、对比整合

**SINGLE_AGENT 触发条件**：
- 问候/解释类：你好、介绍一下、什么是
- 简单任务：简单、快速、只需要
- 代码生成：帮我写代码、生成

**输出结构**：
```python
TaskAnalysis(
    strategy: SINGLE | MULTI,    # 执行策略
    task_type: str,               # 任务类型
    target_agent: str,            # 目标Agent
    confidence: float,            # 置信度 0.0-1.0
    reason: str,                  # 决策原因
    sub_tasks: List[Dict],        # 子任务列表（跨领域时）
)
```

### 3.2 单Agent执行流程

```
用户消息 → AgentManager.astream()
         → LangChain astream_events(v2)
         → token/tool_start/tool_end/done 事件
         → SSE 推送到前端
```

保持完全向后兼容，与多Agent模式互不干扰。

### 3.3 多Agent执行流程

```
用户消息 → 策略分析(MULTI) → _multi_agent_generator()
         → TaskExecutor.create_task() → 生成Todo列表
         → 遍历Todos串行执行：
           ├─ Domain Agent任务 → TaskDispatcher.dispatch_task()
           │   └─ astream_events(v2) → token级流式输出
           └─ Primary Agent任务 → AgentManager.astream()
         → TokenTracker 统计记录
         → task_complete 事件
         → 消息保存到Session
```

---

## 4. SSE事件体系

### 4.1 基础事件（双模式通用）

| 事件类型 | 说明 | 关键字段 |
|---------|------|---------|
| `token` | LLM输出token | content, agent_name(多Agent时) |
| `tool_start` | 工具调用开始 | tool, tool_input, agent_name |
| `tool_end` | 工具调用结束 | tool, tool_output, tool_status, elapsed_time |
| `new_response` | 新响应段开始 | agent_name |
| `retrieval` | RAG检索结果 | results |
| `done` | 流结束 | content, tool_calls |
| `title` | 自动标题 | session_id, title |
| `error` | 错误 | error |

### 4.2 多Agent专属事件

| 事件类型 | 触发时机 | 关键字段 |
|---------|---------|---------|
| `strategy_decided` | 策略分析完成 | strategy, task_type, target_agent, confidence, reason |
| `task_created` | 任务创建完成 | task_id, message, todos[], agent_status{} |
| `todo_update` | Todo状态变更 | task_id, todo_id, old_status, new_status, agent, result |
| `agent_status` | Agent状态变更 | task_id, agent_name, old_status, new_status |
| `stats_update` | 统计数据变更 | task_id, llm_call_count, input_tokens, output_tokens, tool_call_count |
| `task_complete` | 任务完成 | task_id, summary, final_stats |

### 4.3 典型事件序列

```
strategy_decided → task_created → 
  todo_update(in_progress) → agent_status(busy) →
    token × N → tool_start → tool_end → token × N →
  stats_update → todo_update(completed) → agent_status(idle) →
  todo_update(in_progress) → agent_status(busy) →
    token × N →
  stats_update → todo_update(completed) → agent_status(idle) →
task_complete → done → title
```

---

## 5. 前端功能规格

### 5.1 模式切换

- **位置**：聊天输入框左下角 + 侧边栏底部
- **样式**：
  - 单Agent模式：灰色标签 `Bot 单Agent模式`
  - 多Agent模式：紫色标签 `Users Agents协同模式`
- **行为**：切换模式通过 REST API 持久化到后端配置

### 5.2 策略指示器 (StrategyIndicator)

- **位置**：助手消息头像下方
- **紧凑模式**：内联标签显示策略类型
- **完整模式**：展开卡片显示策略详情、置信度、目标Agent、子任务分配

### 5.3 任务面板 (TaskPanel)

- **位置**：页面右侧，多Agent模式且有任务时自动显示
- **宽度**：280-500px，可拖拽调整
- **三个标签页**：

#### 统计标签页 (TaskStats)
- LLM调用次数
- 预估输入/输出Token消耗
- 工具调用次数
- 执行进度条
- 已完成/总子任务数
- 执行耗时

#### Todo标签页 (TodoList)
- Todo项列表，每项显示：
  - 内容描述
  - 执行Agent名称
  - 状态图标（pending/in_progress/completed/failed）
  - 时间信息

#### Agent标签页
- 各Agent当前状态表
  - primary_agent: idle/busy
  - coordinator_agent: idle/processing
  - data_agent: idle/busy
  - doc_agent: idle/busy

### 5.4 协同面板 (CoordinationPanel)

- **位置**：侧边栏Agents标签页底部（多Agent模式开启时显示）
- **功能**：
  - 任务队列列表（支持状态筛选）
  - 协同状态快照查看
  - 10秒自动刷新

### 5.5 Agent管理面板 (AgentsPanel)

- **位置**：侧边栏Agents标签页
- **功能**：
  - Agent列表展示（名称、类型、状态）
  - Domain Agent启停控制
  - 技能列表查看
  - 5秒自动刷新状态

---

## 6. 数据流架构

### 6.1 单Agent模式数据流

```
前端 sendMessage()
  → POST /api/chat (SSE)
  → chat.py event_generator()
    → agent_manager.astream()
    → yield token/tool/done 事件
  → 前端 store.tsx onEvent 回调
    → 更新 messages 状态
    → ChatMessage 重新渲染
```

### 6.2 多Agent模式数据流

```
前端 sendMessage()
  → POST /api/chat (SSE)
  → chat.py event_generator()
    → 策略分析 → MULTI
    → _multi_agent_generator()
      → yield strategy_decided
      → TaskExecutor.create_task() → yield task_created
      → for each todo:
          → yield todo_update(in_progress)
          → TaskDispatcher.dispatch_task() / agent_manager.astream()
          → yield token/tool 事件 (附加 agent_name)
          → TokenTracker.record_*()
          → yield todo_update(completed)
          → yield stats_update
      → yield task_complete
      → yield done
  → 前端 store.tsx onEvent 回调
    → strategy_decided → 更新消息策略信息
    → task_created → 创建 TaskPanelData → TaskPanel显示
    → todo_update → 更新 todos 状态
    → agent_status → 更新 agent 状态
    → stats_update → 更新统计数据
    → task_complete → 标记任务完成
    → token → 更新消息内容 + activeAgent
    → done → 标记流结束
```

---

## 7. Token统计机制

### 7.1 估算方法

由于LangChain streaming不提供精确token计数，采用字符数近似估算：

```python
def estimate_tokens(text: str) -> int:
    """中文约1.5 token/字符"""
    return max(1, len(text) * 2 // 3)
```

### 7.2 统计维度

| 维度 | 说明 |
|------|------|
| 按Agent | 每个Agent的LLM调用次数和Token消耗 |
| 按任务 | 整个任务的累计统计 |
| 工具调用 | 按工具名称统计调用次数 |

### 7.3 统计触发点

- **LLM调用记录**：每个todo执行完成后，调用 `record_llm_call(agent, input_tokens, output_tokens, task_id)`
- **工具调用记录**：每次 on_tool_start/end 时，调用 `record_tool_call(tool_name, task_id, agent)`
- **统计推送**：每个todo完成后强制推送 `stats_update` 事件

---

## 8. API端点清单

### 8.1 核心API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 聊天接口（SSE流式） |
| `/api/sessions` | GET/POST | 会话管理 |
| `/api/sessions/{id}` | GET/PUT/DELETE | 单个会话操作 |
| `/api/config/multi-agent-mode` | GET/PUT | 多Agent模式开关 |
| `/api/config/analyze-strategy` | POST | 策略分析（独立调用） |

### 8.2 Agent管理API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/agents` | GET | 获取Agent列表 |
| `/api/agents/{name}` | GET | 获取Agent详情 |
| `/api/agents/control` | POST | 启停Agent |

### 8.3 协同管理API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/coordination/tasks` | GET/POST | 任务管理 |
| `/api/coordination/tasks/{id}/status` | PUT | 更新任务状态 |
| `/api/coordination/snapshot` | GET | 获取协同快照 |
| `/api/coordination/notices` | GET | 获取通知 |

### 8.4 任务统计API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/task/create` | POST | 创建任务 |
| `/api/task/{id}` | GET | 获取任务详情 |
| `/api/task/{id}/stats` | GET | 获取统计数据 |
| `/api/task/{id}/todos` | GET | 获取Todo列表 |

---

## 9. 技术栈

### 9.1 后端
- **框架**：FastAPI + Uvicorn
- **LLM集成**：LangChain + OpenAI-compatible API
- **流式通信**：SSE (Server-Sent Events)
- **Agent执行**：LangChain create_agent + astream_events(v2)
- **配置管理**：JSON文件持久化
- **协同协议**：文件锁 + Markdown/JSON文件

### 9.2 前端
- **框架**：Next.js 14 + React 18
- **状态管理**：React Context + useState/useCallback
- **样式**：Tailwind CSS
- **图标**：Lucide React
- **Markdown渲染**：react-markdown + remark-gfm + rehype

---

## 10. 关键设计决策

### 10.1 SSE驱动而非轮询
任务状态更新完全通过SSE事件推送，不使用定时轮询REST API。减少网络请求，保证实时性。

### 10.2 服务端任务创建
任务创建在后端chat.py中完成（而非前端REST调用），确保任务生命周期与SSE流完全同步。

### 10.3 串行Todo执行
当前Todo按顺序串行执行，保证数据依赖关系正确。后续可扩展为并行执行无依赖的Todo。

### 10.4 单Agent路径零修改
多Agent功能通过条件分支添加，单Agent执行路径代码完全不变，确保向后兼容。

### 10.5 Token估算而非精确计数
使用字符数近似估算Token，避免额外API调用延迟。提供的是参考值而非精确值。

---

## 11. 修改文件清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `backend/api/chat.py` | 重构 | 添加策略分支 + _multi_agent_generator() |
| `backend/graph/task_dispatcher.py` | 重构 | 升级为astream_events + 全局单例 |
| `backend/utils/token_tracker.py` | 增强 | 添加estimate_tokens()函数 |
| `backend/app.py` | 增强 | 初始化TaskDispatcher（第5步） |
| `frontend/src/lib/api.ts` | 增强 | 扩展StreamEventType（6种新事件） |
| `frontend/src/lib/store.tsx` | 重构 | 重写sendMessage()，SSE驱动任务面板 |
| `frontend/src/components/layout/Sidebar.tsx` | 增强 | 集成CoordinationPanel |
