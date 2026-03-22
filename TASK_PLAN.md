# 多Agent协同模式交互优化任务计划

## 需求概述

当多Agent模式开启时：
1. 输入框左下角显示"Agents协同模式"标识
2. 所有任务自动走多Agent架构（Primary Agent主交互 + Coordinator Agent协同管理）
3. 对话框右侧展示子任务拆分结果、Todo List实时状态、任务执行统计

---

## 任务清单

### 阶段一：前端交互改造

#### 1.1 输入框模式标识
- [ ] **修改 `ChatInput.tsx`**：在输入框左下角添加模式标识
  - 当 `multiAgentMode=true` 时显示"Agents协同模式"标签
  - 样式：紫色背景，Users图标，点击可切换模式

#### 1.2 右侧任务面板组件
- [ ] **创建 `TaskPanel.tsx`**：右侧任务状态面板
  - 显示当前任务的子任务列表
  - 显示Todo List实时状态
  - 显示任务执行统计（LLM调用次数、Token消耗、工具调用次数）
  - 支持展开/收起

- [ ] **创建 `TodoList.tsx`**：Todo List组件
  - 显示任务分解的子项
  - 状态：pending、in_progress、completed、failed
  - 动态更新动画效果

- [ ] **创建 `SubTaskCard.tsx`**：子任务卡片组件
  - 显示子任务名称、执行Agent、状态
  - 显示执行进度和时间

- [ ] **创建 `TaskStats.tsx`**：任务执行统计组件
  - LLM调用次数统计
  - 预估输入Token消耗量
  - 预估输出Token消耗量
  - 工具调用次数统计
  - 总耗时统计
  - 实时更新动画

#### 1.3 页面布局调整
- [ ] **修改 `page.tsx`**：添加右侧任务面板区域
  - 当多Agent模式开启且正在执行任务时显示右侧面板
  - 支持拖拽调整宽度

---

### 阶段二：后端任务管理增强

#### 2.1 任务拆分API
- [ ] **创建 `api/task_api.py`**：任务管理API
  - `POST /api/task/create` - 创建任务并自动拆分
  - `GET /api/task/{task_id}/todos` - 获取任务的Todo List
  - `PUT /api/task/{task_id}/todo/{todo_id}` - 更新Todo状态
  - `GET /api/task/{task_id}/subtasks` - 获取子任务列表
  - `GET /api/task/{task_id}/stats` - 获取任务执行统计

#### 2.2 任务执行器
- [ ] **创建 `graph/task_executor.py`**：任务执行器
  - 任务分解逻辑
  - Todo List生成
  - 执行状态管理
  - SSE事件推送（实时更新前端）
  - **统计数据收集**（LLM调用、Token消耗、工具调用）

#### 2.3 SSE事件流
- [ ] **修改 `api/chat.py`**：增加任务状态事件
  - `task_created` - 任务创建
  - `task_split` - 任务拆分完成
  - `todo_update` - Todo状态更新
  - `subtask_start` - 子任务开始执行
  - `subtask_complete` - 子任务完成
  - `task_complete` - 整体任务完成
  - `stats_update` - 统计数据更新

#### 2.4 Token统计追踪
- [ ] **创建 `utils/token_tracker.py`**：Token统计追踪器
  - 记录每次LLM调用的输入/输出Token数
  - 按Agent分类统计
  - 按任务聚合统计
  - 实时计算预估消耗

---

### 阶段三：状态同步机制

#### 3.1 前端状态管理
- [ ] **修改 `store.tsx`**：添加任务状态管理
  - `currentTask` - 当前任务信息
  - `todos` - Todo List
  - `subTasks` - 子任务列表
  - `taskStatus` - 任务执行状态
  - `taskStats` - 任务执行统计（LLM调用次数、Token消耗、工具调用次数）

#### 3.2 API接口扩展
- [ ] **修改 `api.ts`**：添加任务相关API
  - `getTaskTodos(taskId)` - 获取Todo列表
  - `updateTodoStatus(taskId, todoId, status)` - 更新Todo状态
  - `getSubTasks(taskId)` - 获取子任务列表
  - `getTaskStats(taskId)` - 获取任务执行统计

---

### 阶段四：多Agent协同执行流程

#### 4.1 Primary Agent改造
- [ ] **修改 `graph/base_agent.py`**：Primary Agent任务分发
  - 检测多Agent模式
  - 调用Coordinator进行任务拆分
  - 返回任务ID供前端订阅
  - 记录Token消耗

#### 4.2 Coordinator Agent增强
- [ ] **修改 `graph/coordinator.py`**：增强协同管理
  - 任务分解为Todo List
  - 分配子任务给Domain Agent
  - 状态更新推送
  - 统计数据汇总

#### 4.3 Domain Agent执行
- [ ] **创建 `graph/domain_executor.py`**：Domain Agent执行器
  - 接收子任务
  - 执行并更新状态
  - 返回结果
  - 上报统计数据

---

## 详细设计

### 前端组件结构

```
frontend/src/
├── components/
│   ├── chat/
│   │   ├── ChatInput.tsx      # 添加模式标识
│   │   ├── ChatPanel.tsx      # 调整布局
│   │   └── ...
│   ├── task/
│   │   ├── TaskPanel.tsx      # 右侧任务面板（主容器）
│   │   ├── TodoList.tsx       # Todo列表
│   │   ├── SubTaskCard.tsx    # 子任务卡片
│   │   ├── TaskStats.tsx      # 任务执行统计（新增）
│   │   └── ModeIndicator.tsx  # 模式指示器
│   └── ...
└── lib/
    ├── store.tsx              # 添加任务状态
    └── api.ts                 # 添加任务API
```

### 后端API结构

```
backend/
├── api/
│   ├── task_api.py            # 任务管理API
│   └── chat.py                # 添加任务事件
├── graph/
│   ├── task_executor.py       # 任务执行器
│   ├── coordinator.py         # 协同管理器增强
│   └── domain_executor.py     # Domain Agent执行器
├── utils/
│   └── token_tracker.py       # Token统计追踪器（新增）
└── ...
```

### 数据结构

#### Todo Item
```typescript
interface TodoItem {
  id: string
  content: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  agent?: string
  startTime?: number
  endTime?: number
  result?: string
}
```

#### SubTask
```typescript
interface SubTask {
  id: string
  taskType: string
  targetAgent: string
  status: 'pending' | 'processing' | 'finished' | 'failed'
  content: string
  result?: string
  createdAt: string
  updatedAt: string
}
```

#### TaskStats（新增）
```typescript
interface TaskStats {
  taskId: string

  // LLM调用统计
  llmCallCount: number           // LLM调用总次数
  llmCallsByAgent: {             // 按Agent分类
    [agentName: string]: number
  }

  // Token统计
  inputTokens: number            // 输入Token总量
  outputTokens: number           // 输出Token总量
  totalTokens: number            // Token总量
  tokensByAgent: {               // 按Agent分类
    [agentName: string]: {
      input: number
      output: number
    }
  }

  // 工具调用统计
  toolCallCount: number          // 工具调用总次数
  toolCallsByName: {             // 按工具名分类
    [toolName: string]: number
  }

  // 耗时统计
  startTime: number              // 任务开始时间
  elapsedTime: number            // 已耗时（秒）
  estimatedRemaining?: number    // 预估剩余时间

  // Agent参与统计
  activeAgents: string[]         // 参与的Agent列表
  completedSubTasks: number      // 已完成子任务数
  totalSubTasks: number          // 总子任务数
}
```

### SSE事件格式

```typescript
// 任务创建
{ type: 'task_created', task_id: string, message: string }

// 任务拆分
{ type: 'task_split', task_id: string, todos: TodoItem[], subtasks: SubTask[] }

// Todo更新
{ type: 'todo_update', task_id: string, todo_id: string, status: string, result?: string }

// 子任务开始
{ type: 'subtask_start', task_id: string, subtask_id: string, agent: string }

// 子任务完成
{ type: 'subtask_complete', task_id: string, subtask_id: string, result: string }

// 统计数据更新（新增）
{
  type: 'stats_update',
  task_id: string,
  stats: {
    llmCallCount: number,
    inputTokens: number,
    outputTokens: number,
    toolCallCount: number,
    elapsedTime: number
  }
}

// 任务完成
{
  type: 'task_complete',
  task_id: string,
  summary: string,
  finalStats: TaskStats  // 最终统计数据
}
```

### 右侧面板布局设计

```
┌─────────────────────────────────────┐
│ 📊 任务执行面板                      │
├─────────────────────────────────────┤
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ 📈 执行统计                      │ │
│ │ ├─ LLM调用: 12 次               │ │
│ │ ├─ 输入Token: 15,234            │ │
│ │ ├─ 输出Token: 8,456             │ │
│ │ ├─ 工具调用: 6 次                │ │
│ │ ├─ 耗时: 45.2s                  │ │
│ │ └─ 进度: 3/5 子任务完成          │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ ✅ Todo List                     │ │
│ │ ├─ ✅ 分析数据结构               │ │
│ │ ├─ ✅ 读取CSV文件                │ │
│ │ ├─ 🔄 计算统计指标   [data_agent]│ │
│ │ ├─ ⏳ 生成可视化图表             │ │
│ │ └─ ⏳ 输出分析报告               │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ 🤖 Agent执行状态                 │ │
│ │ ├─ primary_agent: 完成          │ │
│ │ ├─ coordinator_agent: 监控中    │ │
│ │ ├─ data_agent: 执行中...        │ │
│ │ └─ doc_agent: 待命              │ │
│ └─────────────────────────────────┘ │
│                                     │
└─────────────────────────────────────┘
```

---

## 执行顺序

1. **前端交互改造**（阶段一）
   - 先修改输入框显示模式标识
   - 创建右侧面板组件（TaskPanel、TodoList、SubTaskCard、TaskStats）
   - 调整页面布局

2. **后端任务管理**（阶段二）
   - 创建Token统计追踪器
   - 创建任务API
   - 实现任务执行器
   - 添加SSE事件（包含stats_update）

3. **状态同步**（阶段三）
   - 前端状态管理（包含taskStats）
   - API接口扩展

4. **多Agent协同**（阶段四）
   - Primary Agent改造
   - Coordinator增强
   - Domain Agent执行

---

## 预期效果

1. 用户开启多Agent模式后，输入框左下角显示"Agents协同模式"
2. 发送任务后，右侧面板自动展开，显示：
   - **任务执行统计**：LLM调用次数、Token消耗、工具调用次数、耗时
   - **任务拆分结果**：子任务列表
   - **Todo List列表**：实时更新状态
   - **当前执行的Agent**：各Agent状态
3. 任务执行过程中：
   - 统计数据实时更新（每秒刷新）
   - Todo状态从 pending → in_progress → completed 动态变化
   - Token消耗实时累加显示
4. 所有子任务完成后，显示：
   - 任务完成总结
   - 最终统计数据汇总