# Mini-OpenClaw Frontend

轻量级、全透明的 AI Agent 系统前端。基于 Next.js 14 构建, 提供类 Claude/ChatGPT 的交互体验。

## 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| 框架 | Next.js | 14.2.0 |
| 语言 | TypeScript | 5.3.0 |
| UI | React | 18.2.0 |
| 样式 | Tailwind CSS | 3.4.1 |
| 代码编辑 | Monaco Editor | 4.6.0 |
| Markdown | react-markdown + remark-gfm | 9.0.1 |

## 项目结构

```
frontend/
├── package.json                # 依赖配置
├── tsconfig.json               # TypeScript 配置
├── tailwind.config.ts          # Tailwind 配置
├── postcss.config.js           # PostCSS 配置
├── next-env.d.ts               # Next.js 类型
│
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # 根布局
│   │   ├── page.tsx            # 主页面
│   │   └── globals.css         # 全局样式
│   │
│   ├── components/             # React 组件
│   │   ├── chat/               # 聊天相关组件
│   │   │   ├── ChatPanel.tsx       # 聊天主面板
│   │   │   ├── ChatMessage.tsx     # 单条消息
│   │   │   ├── ChatInput.tsx       # 消息输入框
│   │   │   ├── ThoughtChain.tsx    # 思考链展示
│   │   │   └── RetrievalCard.tsx   # RAG 检索卡片
│   │   │
│   │   ├── layout/             # 布局组件
│   │   │   ├── Navbar.tsx          # 顶部导航栏
│   │   │   ├── Sidebar.tsx         # 侧边栏 (会话列表)
│   │   │   └── ResizeHandle.tsx    # 可调整分隔条
│   │   │
│   │   └── editor/             # 编辑器组件
│   │       └── InspectorPanel.tsx  # 文件检查面板
│   │
│   └── lib/                    # 工具库
│       ├── api.ts              # API 客户端 (SSE 流式)
│       └── store.tsx           # Zustand 状态管理
│
└── .next/                      # Next.js 构建输出
```

## 核心组件

### 1. 聊天模块 (`components/chat/`)

| 组件 | 功能 |
|------|------|
| `ChatPanel.tsx` | 聊天主面板, 消息列表 + 输入框 |
| `ChatMessage.tsx` | 渲染单条消息 (用户/AI/系统) |
| `ChatInput.tsx` | 消息输入框, 支持 Enter 发送 |
| `ThoughtChain.tsx` | 展示 Agent 思考过程 |
| `RetrievalCard.tsx` | 展示 RAG 检索结果 |

### 2. 布局模块 (`components/layout/`)

| 组件 | 功能 |
|------|------|
| `Navbar.tsx` | 顶部导航, 显示当前会话/技能切换 |
| `Sidebar.tsx` | 侧边栏, 会话列表管理 |
| `ResizeHandle.tsx` | 拖拽分隔条, 调整侧边栏宽度 |

### 3. 编辑器模块 (`components/editor/`)

| 组件 | 功能 |
|------|------|
| `InspectorPanel.tsx` | Monaco Editor 面板, 展示/编辑文件内容 |

## 状态管理 (`lib/store.tsx`)

使用类似 Zustand 的模式管理全局状态:

- `sessions`: 会话列表
- `currentSessionId`: 当前会话 ID
- `messages`: 消息列表
- `isLoading`: AI 响应中状态
- `ragMode`: RAG 模式开关
- Actions: `createSession`, `deleteSession`, `addMessage` 等

## API 客户端 (`lib/api.ts`)

封装后端 SSE 流式接口:

### 核心方法

```typescript
// 流式对话
streamChat(
  message: string,
  sessionId: string,
  onEvent: (event: StreamEvent) => void
): Promise<void>

// 会话管理
getSessions(): Promise<{ sessions: any[] }>
createSession(): Promise<{ session_id: string; title: string }>
deleteSession(sessionId: string): Promise<{ success: boolean }>
renameSession(sessionId: string, title: string): Promise<...>

// 文件操作
readFile(path: string): Promise<{ path: string; content: string }>
saveFile(path: string, content: string): Promise<...>
uploadFiles(files: File[]): Promise<...>

// 配置
getRAGMode(): Promise<{ enabled: boolean }>
setRAGMode(enabled: boolean): Promise<...>
```

### SSE 事件类型

| 事件类型 | 说明 |
|----------|------|
| `retrieval` | RAG 检索结果 |
| `token` | AI 响应 token |
| `tool_start` | 工具开始执行 |
| `tool_end` | 工具执行结束 |
| `new_response` | AI 新响应片段 |
| `title` | 会话标题生成 |
| `done` | 响应完成 |
| `error` | 错误发生 |

## 启动方式

### 安装依赖

```bash
cd frontend
npm install
```

### 启动开发服务器

```bash
# 默认端口 3001
npm run dev

# 或使用脚本
../start-frontend.sh
```

访问: http://localhost:3001

### 构建生产版本

```bash
npm run build
npm start -p 3001
```

## 样式说明

### Tailwind 配置 (`tailwind.config.ts`)

- 使用 Apple 风格毛玻璃效果
- 自定义颜色: `glass-bg`, `glass-border`
- 支持暗色主题

### 全局样式 (`app/globals.css`)

- CSS 变量定义主题色
- 毛玻璃效果实现: `backdrop-filter: blur()`
- 平滑过渡动画

## 与后端通信

前端默认连接 `http://localhost:8002`:

```typescript
// 动态获取 API 地址, 支持局域网访问
const getApiBase = () => {
  if (typeof window === 'undefined') {
    return 'http://localhost:8002'
  }
  return `http://${window.location.hostname}:8002`
}
```

## 开发说明

### 添加新组件

1. 在 `components/` 下创建目录
2. 实现 React 组件
3. 在 `page.tsx` 或其他位置引入使用

### 修改主题

- 颜色: `tailwind.config.ts` → `theme.extend.colors`
- 样式: `app/globals.css`
- 组件内部: 使用 `clsx` + `tailwind-merge` 组合类名

### 调试技巧

- 打开浏览器开发者工具 → Network → 过滤 `localhost:8002` 查看 API 请求
- 后端控制台查看 SSE 事件流
- 前端 `lib/store.tsx` 添加 console.log 查看状态变化

---

由 [wangjifei]() 提供技术支持
