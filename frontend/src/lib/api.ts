/**
 * API 客户端 - 后端接口封装
 */

// 动态获取 API 地址，支持本机和局域网访问
const getApiBase = () => {
  if (typeof window === 'undefined') {
    return 'http://localhost:8002'
  }
  return `http://${window.location.hostname}:8002`
}

const API_BASE = getApiBase()

// 通用请求方法
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  
  if (!response.ok) {
    const error = await response.text()
    throw new Error(error || `HTTP ${response.status}`)
  }
  
  return response.json()
}

// ============ 会话 API ============

export async function getSessions() {
  return request<{ sessions: any[] }>('/api/sessions')
}

export async function createSession() {
  return request<{ session_id: string; title: string }>('/api/sessions', {
    method: 'POST',
  })
}

export async function deleteSession(sessionId: string) {
  return request<{ success: boolean }>(`/api/sessions/${sessionId}`, {
    method: 'DELETE',
  })
}

export async function renameSession(sessionId: string, title: string) {
  return request<{ success: boolean; title: string }>(`/api/sessions/${sessionId}`, {
    method: 'PUT',
    body: JSON.stringify({ title }),
  })
}

export async function getSessionHistory(sessionId: string) {
  return request<{ messages: any[] }>(`/api/sessions/${sessionId}/history`)
}

export async function compressSession(sessionId: string) {
  return request<{ archived_count: number; remaining_count: number; summary: string }>(
    `/api/sessions/${sessionId}/compress`,
    { method: 'POST' }
  )
}

// ============ 聊天 API ============

export type StreamEventType = 
  | 'retrieval'
  | 'token'
  | 'tool_start'
  | 'tool_end'
  | 'new_response'
  | 'done'
  | 'title'
  | 'error'
  // 多Agent模式事件
  | 'strategy_decided'
  | 'task_created'
  | 'todo_update'
  | 'agent_status'
  | 'stats_update'
  | 'task_complete'
  // 并行执行事件
  | 'parallel_analysis'
  | 'parallel_start'
  | 'parallel_end'
  // 上下文窗口事件
  | 'context_warning'
  // Prometheus 规划事件
  | 'prometheus_enter'
  | 'plan_generated'
  // 技能匹配事件
  | 'skill_matched'
  // 续推进事件
  | 'continuation_enforced'

export interface StreamEvent {
  type: StreamEventType
  [key: string]: any
}

export async function streamChat(
  message: string,
  sessionId: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const url = `${API_BASE}/api/chat`
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      stream: true,
    }),
    signal,
  })
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }
  
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }
  
  const decoder = new TextDecoder()
  let buffer = ''
  
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    
    buffer += decoder.decode(value, { stream: true })
    
    // 解析 SSE 事件
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          onEvent(data)
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }
}

// ============ 文件 API ============

export async function readFile(path: string) {
  return request<{ path: string; content: string }>(`/api/files?path=${encodeURIComponent(path)}`)
}

export async function saveFile(path: string, content: string) {
  return request<{ success: boolean; path: string }>('/api/files', {
    method: 'POST',
    body: JSON.stringify({ path, content }),
  })
}

// ============ 文件上传 API ============

export interface UploadedFile {
  filename: string
  path: string
  size: number
}

export async function uploadFiles(files: File[]): Promise<{ uploaded_files: UploadedFile[] }> {
  const url = `${API_BASE}/api/files/upload`

  const formData = new FormData()
  files.forEach(file => {
    formData.append('files', file)
  })

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(error || `HTTP ${response.status}`)
  }

  return response.json()
}

export async function getSkills() {
  return request<{ skills: any[] }>('/api/skills')
}

// ============ Token API ============

export async function getSessionTokens(sessionId: string) {
  return request<{ system_tokens: number; message_tokens: number; total_tokens: number }>(
    `/api/tokens/session/${sessionId}`
  )
}

export async function getFilesTokens(paths: string[]) {
  return request<{ tokens: Record<string, number> }>('/api/tokens/files', {
    method: 'POST',
    body: JSON.stringify({ paths }),
  })
}

// ============ 配置 API ============

export async function getRAGMode() {
  return request<{ enabled: boolean }>('/api/config/rag-mode')
}

export async function setRAGMode(enabled: boolean) {
  return request<{ enabled: boolean }>('/api/config/rag-mode', {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  })
}

export async function getMultiAgentMode() {
  return request<{ enabled: boolean }>('/api/config/multi-agent-mode')
}

export async function setMultiAgentMode(enabled: boolean) {
  return request<{ enabled: boolean }>('/api/config/multi-agent-mode', {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  })
}

export async function getAllConfig() {
  return request<{ rag_mode: boolean; multi_agent_mode: boolean }>('/api/config')
}

// ============ 策略分析 API ============

export interface StrategyAnalysis {
  strategy: 'single' | 'multi'
  task_type: string | null
  target_agent: string | null
  confidence: number
  reason: string
  sub_tasks: Array<{ task_type: string; target_agent: string }> | null
}

export async function analyzeStrategy(message: string) {
  return request<StrategyAnalysis>('/api/config/analyze-strategy', {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}

// ============ 多Agent API ============

export interface AgentInfo {
  agent_name: string
  agent_type: string
  status: string
  skills: string[]
  path: string
}

export async function getAgents() {
  return request<{ code: number; data: AgentInfo[]; msg: string }>('/api/agents')
}

export async function getAllSkillTags() {
  return request<{ code: number; data: string[]; msg: string }>('/api/agents/skills/all')
}

export async function getAgent(agentName: string) {
  return request<{ code: number; data: AgentInfo; msg: string }>(`/api/agents/${agentName}`)
}

export async function controlAgent(agentName: string, action: 'start' | 'stop') {
  return request<{ success: boolean; agent_name: string; new_status: string; message: string }>(
    '/api/agents/control',
    {
      method: 'POST',
      body: JSON.stringify({ agent_name: agentName, action }),
    }
  )
}

export interface AgentProfile {
  identity: string
  soul: string
  agents_local: string
  memory: string
}

export interface AgentProfileResponse {
  agent_name: string
  agent_type: string
  status: string
  skills: string[]
  profile: AgentProfile
}

export async function getAgentProfile(agentName: string) {
  return request<{ code: number; data: AgentProfileResponse; msg: string }>(`/api/agents/${agentName}/profile`)
}

export async function createAgent(data: { agent_name: string; agent_type?: string; skills?: string[]; identity?: string; soul?: string }) {
  return request<{ code: number; data: AgentInfo; msg: string }>(
    '/api/agents',
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  )
}

export async function deleteAgent(agentName: string) {
  return request<{ code: number; data: { agent_name: string }; msg: string }>(
    `/api/agents/${agentName}`,
    { method: 'DELETE' }
  )
}

// ============ 协同任务 API ============

export interface TaskInfo {
  task_id: string
  status: string
  target_agent: string
  task_type: string
  parent_task: string
  created_at: string
  updated_at: string
  content: string
}

export async function getTasks(taskId?: string) {
  const url = taskId ? `/api/coordination/tasks?task_id=${taskId}` : '/api/coordination/tasks'
  return request<{ code: number; data: TaskInfo | TaskInfo[]; msg: string }>(url)
}

export async function createTask(taskContent: string, targetAgent?: string, taskType?: string) {
  return request<{ code: number; data: { task_id: string; target_agent: string }; msg: string }>(
    '/api/coordination/tasks',
    {
      method: 'POST',
      body: JSON.stringify({
        task_content: taskContent,
        target_agent: targetAgent,
        task_type: taskType,
      }),
    }
  )
}

export async function updateTaskStatus(taskId: string, status: string) {
  return request<{ code: number; data: { task_id: string; new_status: string }; msg: string }>(
    `/api/coordination/tasks/${taskId}/status?status=${status}`,
    { method: 'PUT' }
  )
}

export async function clearAllTasks() {
  return request<{ code: number; data: { cleared_count: number }; msg: string }>(
    '/api/coordination/tasks',
    { method: 'DELETE' }
  )
}

export async function getCoordinationSnapshot() {
  return request<{ code: number; data: { content: string; updated_at: string }; msg: string }>(
    '/api/coordination/snapshot'
  )
}

export async function getNotices(targetAgent?: string) {
  const url = targetAgent 
    ? `/api/coordination/notices?target_agent=${targetAgent}` 
    : '/api/coordination/notices'
  return request<{ code: number; data: any[]; msg: string }>(url)
}

// ============ 全局记忆 API ============

export async function editGlobalMemory(fileName: string, content: string) {
  return request<{ code: number; data: { file_name: string; path: string }; msg: string }>(
    '/api/global/memory',
    {
      method: 'POST',
      body: JSON.stringify({ file_name: fileName, content }),
    }
  )
}

// ============ 任务管理 API ============

export interface TaskCreateResponse {
  task_id: string
  todos: Array<{
    id: string
    content: string
    status: string
    agent?: string
  }>
  status: string
}

export interface TaskStatsResponse {
  taskId: string
  llmCallCount: number
  inputTokens: number
  outputTokens: number
  totalTokens: number
  toolCallCount: number
  startTime: number
  elapsedTime: number
  completedSubtasks: number
  totalSubtasks: number
  llmCallsByAgent: Record<string, number>
  tokensByAgent: Record<string, { input: number; output: number }>
  toolCallsByName: Record<string, number>
  activeAgents: string[]
}

export interface TaskDetailResponse {
  task_id: string
  message: string
  status: string
  todos: Array<{
    id: string
    content: string
    status: string
    agent?: string
    start_time?: number
    end_time?: number
    result?: string
  }>
  subtasks: Array<{
    id: string
    task_type: string
    target_agent: string
    status: string
    content: string
    result?: string
    created_at: string
    updated_at: string
  }>
  stats: TaskStatsResponse | null
  agent_status: Record<string, string>
}

export async function createMultiAgentTask(message: string, sessionId?: string) {
  return request<{ code: number; data: TaskCreateResponse; msg: string }>(
    '/api/task/create',
    {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId }),
    }
  )
}

export async function getTaskDetail(taskId: string) {
  return request<{ code: number; data: TaskDetailResponse; msg: string }>(
    `/api/task/${taskId}`
  )
}

export async function getTaskTodos(taskId: string) {
  return request<{ code: number; data: any[]; msg: string }>(
    `/api/task/${taskId}/todos`
  )
}

export async function updateTodoStatus(
  taskId: string,
  todoId: string,
  status: string,
  result?: string
) {
  const url = `/api/task/${taskId}/todo/${todoId}?status=${status}${result ? `&result=${encodeURIComponent(result)}` : ''}`
  return request<{ code: number; data: any; msg: string }>(
    url,
    { method: 'PUT' }
  )
}

export async function getTaskSubtasks(taskId: string) {
  return request<{ code: number; data: any[]; msg: string }>(
    `/api/task/${taskId}/subtasks`
  )
}

export async function getTaskStats(taskId: string) {
  return request<{ code: number; data: TaskStatsResponse; msg: string }>(
    `/api/task/${taskId}/stats`
  )
}

export async function deleteTask(taskId: string) {
  return request<{ code: number; data: any; msg: string }>(
    `/api/task/${taskId}`,
    { method: 'DELETE' }
  )
}
