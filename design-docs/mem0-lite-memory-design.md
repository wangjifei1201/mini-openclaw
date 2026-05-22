# Mem0-lite 结构化记忆设计方案

**日期：** 2026-05-19
**状态：** 已实现
**适用范围：** DeepClaw 记忆系统优化

## 1. 目标

将当前基于 `MEMORY.md` 的长期记忆系统升级为 Mem0 启发式的半自动结构化记忆系统，同时保留文件驱动的透明性。

本阶段不引入用户隔离和项目隔离，重点解决：

- 记忆内容结构化；
- 记忆自动抽取与更新；
- 记忆生命周期管理；
- RAG 检索 active 结构化记忆；
- 前端可查看结构化记忆内容。

## 2. 设计范围

### 2.1 包含

- 新增结构化记忆文件：`backend/memory/memories.jsonl`。
- 保留 `backend/memory/MEMORY.md`，用于兼容和人工查看。
- 新增后端 `MemoryStore`，支持 ADD / UPDATE / DELETE 生命周期。
- 在助手回复完成后，半自动执行记忆反思。
- RAG 记忆索引改为索引 active 结构化记忆。
- 新增只读 API：`GET /api/memories`。
- 前端“记忆文件”区域新增“结构化记忆”。
- Inspector 面板支持结构化表格查看 `memory/memories.jsonl`。
- 保留原始 JSONL 查看模式，作为调试和兜底方式。

### 2.2 不包含

- 用户隔离；
- 项目隔离；
- 前端编辑、删除、恢复记忆；
- 数据库迁移；
- 高级 reranking；
- 完整接入 Mem0 官方包。

## 3. 总体架构

系统新增一层结构化记忆层，仍然保持本地文件为核心数据源。

```text
Conversation
  ↓
Assistant response completes
  ↓
Memory reflection step
  ↓
Memory operations: ADD / UPDATE / DELETE / NONE
  ↓
backend/memory/memories.jsonl
  ↓
MemoryIndexer indexes active memories
  ↓
RAG retrieval injects relevant memory items
```

`MEMORY.md` 继续保留；结构化记忆检索的新数据源为 `memories.jsonl`。

## 4. 结构化记忆数据模型

`backend/memory/memories.jsonl` 每一行是一条 JSON 记录。

```json
{
  "id": "mem_20260519_ab12cd34",
  "type": "preference",
  "content": "用户偏好半自动记忆写入，只保存明显的长期偏好、事实和项目约束。",
  "status": "active",
  "source": "auto",
  "confidence": 0.85,
  "created_at": "2026-05-19T12:00:00",
  "updated_at": "2026-05-19T12:00:00"
}
```

### 4.1 type

- `preference`：用户偏好，例如助手行为、协作方式、输出风格；
- `project`：长期有效的项目事实、约束、产品决策；
- `feedback`：用户对助手行为的明确纠正或确认；
- `reference`：外部系统、文档、看板、渠道等稳定引用。

### 4.2 status

- `active`：参与 RAG 检索；
- `deleted`：保留审计记录，但不参与检索。

### 4.3 source

- `auto`：由半自动反思生成；
- `manual`：由明确用户请求或未来 UI/API 手动创建。

## 5. 后端组件

### 5.1 MemoryStore

文件：`backend/graph/memory_store.py`

职责：

- 加载 JSONL 记忆记录；
- 校验记录字段和值；
- 生成稳定记忆 ID；
- 返回所有记录；
- 返回 active 记录；
- 新增记忆；
- 更新记忆；
- 将记忆标记为 deleted；
- 使用临时文件 + replace 的方式写入，避免部分写入。

边界：

- 不负责 embedding；
- 不负责 RAG 检索；
- 不负责 LLM 抽取。

### 5.2 MemoryReflectionService

文件：`backend/graph/memory_reflection.py`

职责：

- 在助手回复完成后执行记忆反思；
- 根据本轮用户消息、助手回复、已有 active 记忆生成候选操作；
- 解析 LLM 输出中的 JSON；
- 只接受合法 action/type/status/source；
- 低于置信度阈值的记忆不写入；
- 对重复或冲突记忆优先 UPDATE，而不是重复 ADD；
- 反思失败只记录日志，不影响用户可见回复。

支持动作：

- `ADD`
- `UPDATE`
- `DELETE`
- `NONE`

反思规则：

- 只保存长期有效偏好、项目约束、明确反馈、稳定引用；
- 不保存一次性任务进度；
- 不保存命令输出、错误堆栈、临时调试信息；
- 不保存能从代码或 git 历史读取的事实；
- 低置信度不写入。

### 5.3 MemoryIndexer

文件：`backend/graph/memory_indexer.py`

职责：

- 读取 `MemoryStore.list_active()`；
- 将 active 结构化记忆转换为 LlamaIndex 文档；
- 每条文档文本包含类型提示，例如：

```text
[type: preference]
用户希望回答简洁直接。
```

- 文档 metadata 保留：

```json
{
  "id": "mem_...",
  "type": "preference",
  "source": "auto"
}
```

- RAG 检索结果返回结构化片段，而不是任意 Markdown chunk；
- deleted 记忆不参与索引；
- 缺失 `memories.jsonl` 时视为空记忆；
- 使用结构化索引 marker 防止旧的 `MEMORY.md` 索引被误加载。

### 5.4 Agent 集成

文件：`backend/graph/agent.py`、`backend/api/chat.py`

流程：

1. 用户发送消息；
2. Agent 正常流式生成回复；
3. 用户消息和助手消息保存到 session；
4. 后台非阻塞触发记忆反思；
5. 如有记忆变更，重建结构化记忆索引。

关键约束：

- 记忆反思不能阻塞最终 SSE `done` 事件；
- 非流式响应也不能等待记忆反思完成；
- 反思失败不能影响聊天响应。

### 5.5 API

新增：

```http
GET /api/memories
```

响应：

```json
{
  "memories": [
    {
      "id": "mem_20260519_ab12cd34",
      "type": "preference",
      "content": "...",
      "status": "active",
      "source": "auto",
      "confidence": 0.85,
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

首版只读，用于前端展示。

## 6. 前端设计

### 6.1 Sidebar

文件：`frontend/src/components/layout/Sidebar.tsx`

“记忆文件”区域保留：

```tsx
<FileItem path="memory/MEMORY.md" label="长期记忆" />
```

新增：

```tsx
<FileItem path="memory/memories.jsonl" label="结构化记忆" />
```

### 6.2 API Client

文件：`frontend/src/lib/api.ts`

新增类型：

```ts
export interface MemoryRecord {
  id: string
  type: 'preference' | 'project' | 'feedback' | 'reference'
  content: string
  status: 'active' | 'deleted'
  source: 'auto' | 'manual'
  confidence: number
  created_at: string
  updated_at: string
}
```

新增方法：

```ts
export async function getMemories() {
  return request<{ memories: MemoryRecord[] }>('/api/memories')
}
```

### 6.3 InspectorPanel

文件：`frontend/src/components/editor/InspectorPanel.tsx`

当 `currentFile === 'memory/memories.jsonl'` 时，默认展示结构化记忆查看器，而不是 Monaco 文本编辑器。

查看器能力：

- 表格展示记忆；
- 展示字段：type、content、source、confidence、status、updated_at；
- 支持过滤：
  - all
  - active
  - deleted
  - preference
  - project
  - feedback
  - reference
- 支持“查看原始 JSONL”；
- 原始 JSONL 模式使用现有 Monaco；
- 首版只读，不提供编辑、删除、恢复按钮。

## 7. 数据流

### 7.1 聊天写入路径

```text
User sends message
  ↓
Agent streams response
  ↓
Response completes
  ↓
Save user/assistant messages
  ↓
Schedule memory reflection in background
  ↓
MemoryStore applies accepted operations
  ↓
MemoryIndexer rebuilds index if memory changed
```

### 7.2 RAG 检索路径

```text
User sends message
  ↓
RAG mode enabled?
  ↓ yes
MemoryIndexer retrieves top 3 active structured memories
  ↓
Formatted memory snippets are appended to transient history
  ↓
Agent receives message with relevant memory context
```

### 7.3 前端查看路径

```text
User clicks 结构化记忆
  ↓
InspectorPanel detects memory/memories.jsonl
  ↓
GET /api/memories
  ↓
Render structured viewer
  ↓
Optional raw JSONL toggle uses existing readFile path
```

## 8. 错误处理

- 缺失 `memories.jsonl`：视为空记忆列表；
- JSONL 中单行无效：跳过该行并记录日志；
- 文件读取异常：不静默覆盖旧文件，避免数据丢失；
- 反思失败：记录日志，不影响聊天响应；
- 记忆写入失败：不进入紧密重试；
- embedding / index rebuild 失败：RAG 返回空记忆上下文，系统继续运行；
- 前端无记录时显示友好空状态。

## 9. 迁移策略

无需破坏性迁移。

初始行为：

- 如果 `memories.jsonl` 不存在，系统按空结构化记忆运行；
- 现有 `MEMORY.md` 保持不变；
- 后续新结构化记忆写入 `memories.jsonl`。

可选后续增强：

- 增加一次性迁移工具，将 `MEMORY.md` 中选定条目转为结构化记忆。

## 10. 验收标准

- 只有 `MEMORY.md` 存在时应用仍可运行；
- 半自动反思只把长期有效信息写入 `memory/memories.jsonl`；
- RAG 模式检索 active 结构化记忆；
- deleted 记忆不参与检索；
- 前端“记忆文件”包含“结构化记忆”；
- 点击“结构化记忆”展示可读表格/列表；
- 查看器支持过滤和原始 JSONL 回退；
- 没有引入用户隔离和项目隔离。

## 11. 后续设计文档约定

项目根目录下统一使用 `design-docs/` 存放模块设计文档。后续新增模块、能力或较大功能设计时，设计文档都应放在该目录下。
