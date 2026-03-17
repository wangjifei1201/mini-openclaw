'use client'

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react'
import { streamChat, getSessions, createSession, deleteSession, getSessionHistory, compressSession, getRAGMode, setRAGMode } from './api'

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

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tool_calls?: ToolCall[]
  retrievals?: RetrievalResult[]
  isStreaming?: boolean
  attachments?: Attachment[]
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
  isMobileSidebarOpen: boolean
  
  // 编辑器状态
  currentFile: string | null
  fileContent: string
  
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
  setIsMobileSidebarOpen: (open: boolean) => void
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
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false)
  
  // 编辑器状态
  const [currentFile, setCurrentFile] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState('')
  
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
                ? { ...msg, content: currentContent }
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
                ? { ...msg, content: `错误: ${data.error}`, isStreaming: false }
                : msg
            ))
            break
        }
      })
    } catch (error) {
      console.error('发送消息失败:', error)
    } finally {
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
  
  // 初始化加载
  useEffect(() => {
    loadSessions()
    getRAGMode().then(data => setRagModeState(data.enabled)).catch(console.error)
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
    isMobileSidebarOpen,
    currentFile,
    fileContent,
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
    setIsMobileSidebarOpen,
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
