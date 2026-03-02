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

export interface StreamEvent {
  type: StreamEventType
  [key: string]: any
}

export async function streamChat(
  message: string,
  sessionId: string,
  onEvent: (event: StreamEvent) => void
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
