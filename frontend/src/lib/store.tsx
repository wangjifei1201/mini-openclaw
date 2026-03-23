'use client'

import React, { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react'
import { 
  streamChat, getSessions, createSession, deleteSession, getSessionHistory, 
  compressSession, getRAGMode, setRAGMode, getMultiAgentMode, setMultiAgentMode,
} from './api'
import type { StrategyAnalysis } from './api'
import { type TaskPanelData } from '@/components/task/TaskPanel'
import { type TodoItem } from '@/components/task/TodoList'
import { type SubTaskData } from '@/components/task/SubTaskCard'
import { type TaskStatsData } from '@/components/task/TaskStats'

// 类型定义
export interface ToolCall {
  tool: string
  source?: 'tool' | 'llm'
  tool_call_id?: string
  tool_status?: 'ok' | 'error'
  tool_error?: string
  start_time?: number
  elapsed_time?: number
  input?: any
  output?: string
  tool_input?: any
  tool_output?: string
}

export interface RetrievalResult {
  text: string
  score: number
  source: string
}

export interface Attachment {
  filename: string
  path: string
  size: number
  type: 'image' | 'document'
}

export interface AgentExecution {
  agent_name: string
  task_type: string
  status: 'pending' | 'processing' | 'finished' | 'failed'
  start_time?: number
  end_time?: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tool_calls?: ToolCall[]
  retrievals?: RetrievalResult[]
  isStreaming?: boolean
  attachments?: Attachment[]
  strategy?: StrategyAnalysis
  agentExecutions?: AgentExecution[]
  activeAgent?: string
  matchedSkill?: { name: string; description: string }
  plan?: { title: string; description: string; steps: any[] }
}

export interface Session {
  id: string
  title: string
  created_at: number
  updated_at: number
  message_count: number
}

// Context 类型
interface AppContextType {
  // 会话状态
  sessions: Session[]
  currentSessionId: string | null
  messages: Message[]
  
  // UI 状态
  sidebarWidth: number
  inspectorWidth: number
  isStreaming: boolean
  isCompressing: boolean
  ragMode: boolean
  multiAgentMode: boolean
  isMobileSidebarOpen: boolean
  taskPanelWidth: number
  
  // 主题状态
  theme: 'light' | 'dark'
  
  // 编辑器状态
  currentFile: string | null
  fileContent: string
  
  // 任务状态
  currentTask: TaskPanelData | null
  
  // 上下文告警状态
  contextWarning: { status: string; usage_ratio: number; message: string } | null
  
  // 操作方法
  loadSessions: () => Promise<void>
  selectSession: (id: string) => Promise<void>
  newSession: () => Promise<void>
  removeSession: (id: string) => Promise<void>
  sendMessage: (content: string, attachments?: Attachment[]) => Promise<void>
  setSidebarWidth: (width: number) => void
  setInspectorWidth: (width: number) => void
  setCurrentFile: (path: string | null) => void
  setFileContent: (content: string) => void
  compress: () => Promise<void>
  toggleRAGMode: () => Promise<void>
  toggleMultiAgentMode: () => Promise<void>
  setIsMobileSidebarOpen: (open: boolean) => void
  setTaskPanelWidth: (width: number) => void
  clearCurrentTask: () => void
  toggleTheme: () => void
  stopStreaming: () => void
  dismissContextWarning: () => void
}

const AppContext = createContext<AppContextType | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  // 会话状态
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  
  // UI 状态
  const [sidebarWidth, setSidebarWidth] = useState(280)
  const [inspectorWidth, setInspectorWidth] = useState(400)
  const [isStreaming, setIsStreaming] = useState(false)
  const [isCompressing, setIsCompressing] = useState(false)
  const [ragMode, setRagModeState] = useState(false)
  const [multiAgentMode, setMultiAgentModeState] = useState(true)
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false)
  
  // 主题状态
  const [theme, setThemeState] = useState<'light' | 'dark'>('light')
  
  // 编辑器状态
  const [currentFile, setCurrentFile] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState('')
  
  // 任务状态
  const [currentTask, setCurrentTask] = useState<TaskPanelData | null>(null)
  const [taskPanelWidth, setTaskPanelWidth] = useState(320)
  
  // 上下文告警状态
  const [contextWarning, setContextWarning] = useState<{ status: string; usage_ratio: number; message: string } | null>(null)
  
  // AbortController ref for stopping streaming
  const abortControllerRef = useRef<AbortController | null>(null)
  
  // 清除当前任务
  const clearCurrentTask = useCallback(() => {
    setCurrentTask(null)
  }, [])
  
  // 关闭上下文告警
  const dismissContextWarning = useCallback(() => {
    setContextWarning(null)
  }, [])
  
  // 切换主题
  const toggleTheme = useCallback(() => {
    setThemeState(prev => {
      const newTheme = prev === 'light' ? 'dark' : 'light'
      if (typeof window !== 'undefined') {
        localStorage.setItem('theme', newTheme)
        document.documentElement.classList.toggle('dark', newTheme === 'dark')
      }
      return newTheme
    })
  }, [])
  
  // 停止流式生成
  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
  }, [])
  
  // 加载会话列表
  const loadSessions = useCallback(async () => {
    try {
      const data = await getSessions()
      setSessions(data.sessions || [])
    } catch (error) {
      console.error('加载会话列表失败:', error)
    }
  }, [])
  
  // 选择会话
  const selectSession = useCallback(async (id: string) => {
    setCurrentSessionId(id)
    try {
      const data = await getSessionHistory(id)
      const msgs: Message[] = (data.messages || []).map((msg: any, idx: number) => ({
        id: `${id}-${idx}`,
        role: msg.role,
        content: msg.content,
        tool_calls: msg.tool_calls,
      }))
      setMessages(msgs)
    } catch (error) {
      console.error('加载会话历史失败:', error)
      setMessages([])
    }
  }, [])
  
  // 创建新会话
  const newSession = useCallback(async () => {
    try {
      const data = await createSession()
      await loadSessions()
      setCurrentSessionId(data.session_id)
      setMessages([])
    } catch (error) {
      console.error('创建会话失败:', error)
    }
  }, [loadSessions])
  
  // 删除会话
  const removeSession = useCallback(async (id: string) => {
    try {
      await deleteSession(id)
      await loadSessions()
      if (currentSessionId === id) {
        setCurrentSessionId(null)
        setMessages([])
      }
    } catch (error) {
      console.error('删除会话失败:', error)
    }
  }, [currentSessionId, loadSessions])
  
  // 发送消息
  const sendMessage = useCallback(async (content: string, attachments?: Attachment[]) => {
    if (!currentSessionId || isStreaming) return

    // 添加用户消息
    const userMsgId = `${currentSessionId}-${Date.now()}-user`
    const userMessage: Message = {
      id: userMsgId,
      role: 'user',
      content,
      attachments,
    }

    // 添加助手消息占位
    const assistantMsgId = `${currentSessionId}-${Date.now()}-assistant`
    const assistantMessage: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    }

    setMessages(prev => [...prev, userMessage, assistantMessage])
    setIsStreaming(true)
    
    // 创建 AbortController
    const controller = new AbortController()
    abortControllerRef.current = controller
    
    try {
      let currentContent = ''
      let currentToolCalls: ToolCall[] = []
      let currentRetrievals: RetrievalResult[] = []
      
      // 构建完整消息内容（包含附件路径信息）
      let fullMessage = content
      if (attachments && attachments.length > 0) {
        const attachmentInfo = attachments
          .map(att => `${att.filename} (${att.path})`)
          .join(', ')
        fullMessage = `${content}\n\n[用户上传了以下文件: ${attachmentInfo}]`
      }
      
      await streamChat(fullMessage, currentSessionId, (event) => {
        const { type, ...data } = event
        
        switch (type) {
          // ============ 多Agent专属事件 ============

          case 'strategy_decided':
            // 从SSE事件更新消息的策略信息
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, strategy: data as StrategyAnalysis }
                : msg
            ))
            break

          case 'task_created':
            // 从SSE事件构建 TaskPanelData
            setCurrentTask({
              taskId: data.task_id,
              message: data.message || content,
              status: 'processing',
              stats: {
                llmCallCount: 0,
                inputTokens: 0,
                outputTokens: 0,
                totalTokens: 0,
                toolCallCount: 0,
                startTime: Date.now(),
                elapsedTime: 0,
                completedSubTasks: 0,
                totalSubTasks: (data.todos || []).length,
              },
              todos: (data.todos || []).map((t: any) => ({
                id: t.id,
                content: t.content,
                status: t.status as 'pending' | 'in_progress' | 'completed' | 'failed',
                agent: t.agent,
              })),
              subtasks: [],
              agentStatus: data.agent_status || {
                primary_agent: 'idle',
                coordinator_agent: 'processing',
                code_agent: 'idle',
                research_agent: 'idle',
                creative_agent: 'idle',
                data_agent: 'idle',
              },
            })
            break

          case 'todo_update':
            setCurrentTask(prev => {
              if (!prev) return null
              const completedCount = prev.todos.filter(t => 
                t.id === data.todo_id 
                  ? data.new_status === 'completed'
                  : t.status === 'completed'
              ).length
              return {
                ...prev,
                todos: prev.todos.map(t =>
                  t.id === data.todo_id
                    ? { ...t, status: data.new_status, result: data.result }
                    : t
                ),
                stats: {
                  ...prev.stats,
                  completedSubTasks: completedCount,
                },
              }
            })
            break

          case 'agent_status':
            setCurrentTask(prev => prev ? {
              ...prev,
              agentStatus: { ...prev.agentStatus, [data.agent_name]: data.new_status },
            } : null)
            break

          case 'stats_update':
            setCurrentTask(prev => prev ? {
              ...prev,
              stats: {
                ...prev.stats,
                llmCallCount: data.llmCallCount ?? data.llm_call_count ?? prev.stats.llmCallCount,
                inputTokens: data.inputTokens ?? data.input_tokens ?? prev.stats.inputTokens,
                outputTokens: data.outputTokens ?? data.output_tokens ?? prev.stats.outputTokens,
                totalTokens: (data.inputTokens ?? data.input_tokens ?? prev.stats.inputTokens) + (data.outputTokens ?? data.output_tokens ?? prev.stats.outputTokens),
                toolCallCount: data.toolCallCount ?? data.tool_call_count ?? prev.stats.toolCallCount,
                elapsedTime: data.elapsedTime ?? data.elapsed_time ?? prev.stats.elapsedTime,
              },
            } : null)
            break

          case 'task_complete':
            setCurrentTask(prev => {
              if (!prev) return null
              const finalStats = data.final_stats
              // 重置所有 agent 状态为 idle
              const resetAgentStatus: Record<string, 'idle' | 'processing' | 'completed' | 'failed'> = {}
              if (prev.agentStatus) {
                for (const key of Object.keys(prev.agentStatus)) {
                  resetAgentStatus[key] = 'idle'
                }
              }
              return {
                ...prev,
                status: 'completed',
                agentStatus: resetAgentStatus,
                stats: finalStats ? {
                  ...prev.stats,
                  llmCallCount: finalStats.llmCallCount ?? finalStats.llm_call_count ?? prev.stats.llmCallCount,
                  inputTokens: finalStats.inputTokens ?? finalStats.input_tokens ?? prev.stats.inputTokens,
                  outputTokens: finalStats.outputTokens ?? finalStats.output_tokens ?? prev.stats.outputTokens,
                  totalTokens: (finalStats.inputTokens ?? finalStats.input_tokens ?? prev.stats.inputTokens) + (finalStats.outputTokens ?? finalStats.output_tokens ?? prev.stats.outputTokens),
                  toolCallCount: finalStats.toolCallCount ?? finalStats.tool_call_count ?? prev.stats.toolCallCount,
                  elapsedTime: finalStats.elapsedTime ?? finalStats.elapsed_time ?? prev.stats.elapsedTime,
                } : prev.stats,
              }
            })
            break

          // ============ 并行执行 + 优化事件 ============

          case 'parallel_analysis':
            setCurrentTask(prev => prev ? {
              ...prev,
              parallelGroups: (data.groups || []).map((g: any) => ({
                indices: g.indices,
                type: g.type,
                agents: g.agents,
              })),
            } : null)
            break

          case 'parallel_start':
            setCurrentTask(prev => prev ? {
              ...prev,
              activeParallelGroup: data.group_indices,
            } : null)
            break

          case 'parallel_end':
            setCurrentTask(prev => prev ? {
              ...prev,
              activeParallelGroup: undefined,
            } : null)
            break

          case 'context_warning':
            setContextWarning({
              status: data.status,
              usage_ratio: data.usage_ratio,
              message: data.message,
            })
            break

          case 'prometheus_enter':
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, content: data.message || '' }
                : msg
            ))
            break

          case 'plan_generated':
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, plan: data.plan }
                : msg
            ))
            break

          case 'skill_matched':
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, matchedSkill: { name: data.skill, description: data.description } }
                : msg
            ))
            break

          case 'continuation_enforced':
            setCurrentTask(prev => {
              if (!prev) return null
              return {
                ...prev,
                continuationEvents: [
                  ...(prev.continuationEvents || []),
                  { todoId: data.todo_id, agent: data.agent, message: data.message, timestamp: Date.now() },
                ],
              }
            })
            break

          // ============ 原有事件（增强兼容多Agent） ============

          case 'retrieval':
            currentRetrievals = data.results || []
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMsgId
                ? { ...msg, retrievals: currentRetrievals }
                : msg
            ))
            break
            
          case 'token':
            currentContent += data.content || ''
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, content: currentContent, activeAgent: data.agent_name || undefined }
                : msg
            ))
            break
            
          case 'tool_start': {
            const toolInput = data.tool_input ?? data.input
            currentToolCalls.push({
              source: data.source ?? 'tool',
              tool: data.tool,
              tool_call_id: data.tool_call_id,
              input: data.input,
              tool_input: toolInput,
              start_time: data.start_time,
              output: '执行中...',
            })
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, tool_calls: [...currentToolCalls] }
                : msg
            ))
            break
          }

          case 'tool_end': {
            const lastIdx = currentToolCalls.length - 1
            if (lastIdx >= 0) {
              const toolOutput = data.tool_output ?? data.output ?? ''
              currentToolCalls[lastIdx] = {
                ...currentToolCalls[lastIdx],
                tool_call_id: data.tool_call_id ?? currentToolCalls[lastIdx].tool_call_id,
                output: toolOutput,
                tool_output: toolOutput,
                tool_status: data.tool_status,
                tool_error: data.tool_error,
                elapsed_time: data.elapsed_time,
              }
              setMessages(prev => prev.map(msg =>
                msg.id === assistantMsgId
                  ? { ...msg, tool_calls: [...currentToolCalls] }
                  : msg
              ))
            }
            break
          }
            
          case 'new_response':
            // 创建新的助手消息段
            break
            
          case 'done':
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, isStreaming: false }
                : msg
            ))
            break
            
          case 'title':
            // 更新会话标题
            loadSessions()
            break
            
          case 'error':
            console.error('流式响应错误:', data.error)
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, content: currentContent + `\n\n错误: ${data.error}`, isStreaming: false }
                : msg
            ))
            break
        }
      }, controller.signal)
    } catch (error) {
      // 用户主动停止生成 - 优雅处理
      if (error instanceof DOMException && error.name === 'AbortError') {
        setMessages(prev => prev.map(msg =>
          msg.id === assistantMsgId
            ? { ...msg, isStreaming: false }
            : msg
        ))
      } else {
        console.error('发送消息失败:', error)
      }
    } finally {
      abortControllerRef.current = null
      setIsStreaming(false)
    }
  }, [currentSessionId, isStreaming, loadSessions])
  
  // 压缩对话
  const compress = useCallback(async () => {
    if (!currentSessionId || isCompressing) return
    
    setIsCompressing(true)
    try {
      await compressSession(currentSessionId)
      await selectSession(currentSessionId)
    } catch (error) {
      console.error('压缩对话失败:', error)
    } finally {
      setIsCompressing(false)
    }
  }, [currentSessionId, isCompressing, selectSession])
  
  // 切换 RAG 模式
  const toggleRAGMode = useCallback(async () => {
    try {
      const newMode = !ragMode
      await setRAGMode(newMode)
      setRagModeState(newMode)
    } catch (error) {
      console.error('切换 RAG 模式失败:', error)
    }
  }, [ragMode])
  
  // 切换多Agent模式
  const toggleMultiAgentMode = useCallback(async () => {
    try {
      const newMode = !multiAgentMode
      await setMultiAgentMode(newMode)
      setMultiAgentModeState(newMode)
    } catch (error) {
      console.error('切换多Agent模式失败:', error)
    }
  }, [multiAgentMode])
  
  // 初始化加载
  useEffect(() => {
    loadSessions()
    getRAGMode().then(data => setRagModeState(data.enabled)).catch(console.error)
    getMultiAgentMode().then(data => setMultiAgentModeState(data.enabled)).catch(console.error)
    
    // 初始化主题
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('theme') as 'light' | 'dark' | null
      const initial = saved || 'light'
      setThemeState(initial)
      document.documentElement.classList.toggle('dark', initial === 'dark')
    }
  }, [loadSessions])
  
  const value: AppContextType = {
    sessions,
    currentSessionId,
    messages,
    sidebarWidth,
    inspectorWidth,
    isStreaming,
    isCompressing,
    ragMode,
    multiAgentMode,
    isMobileSidebarOpen,
    taskPanelWidth,
    theme,
    currentFile,
    fileContent,
    currentTask,
    loadSessions,
    selectSession,
    newSession,
    removeSession,
    sendMessage,
    setSidebarWidth,
    setInspectorWidth,
    setCurrentFile,
    setFileContent,
    compress,
    toggleRAGMode,
    toggleMultiAgentMode,
    setIsMobileSidebarOpen,
    setTaskPanelWidth,
    clearCurrentTask,
    toggleTheme,
    stopStreaming,
    contextWarning,
    dismissContextWarning,
  }
  
  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useApp must be used within AppProvider')
  }
  return context
}
