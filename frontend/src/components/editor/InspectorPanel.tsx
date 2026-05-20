'use client'

import { useState, useEffect, useCallback } from 'react'
import dynamic from 'next/dynamic'
import { X, Save, FileText } from 'lucide-react'
import { useApp } from '@/lib/store'
import { readFile, saveFile, getFilesTokens, getMemories, MemoryRecord } from '@/lib/api'

// 动态导入 Monaco Editor（避免 SSR 问题）
const MonacoEditor = dynamic(
  () => import('@monaco-editor/react'),
  { ssr: false, loading: () => <div className="h-full flex items-center justify-center text-gray-400">加载编辑器...</div> }
)

const MEMORY_FILE_PATH = 'memory/memories.jsonl'
const MEMORY_STATUS_FILTERS: Array<'all' | MemoryRecord['status']> = [
  'all',
  'active',
  'deleted',
]
const MEMORY_TYPE_FILTERS: Array<'all' | MemoryRecord['type']> = [
  'all',
  'preference',
  'project',
  'feedback',
  'reference',
]

const MEMORY_STATUS_LABELS: Record<'all' | MemoryRecord['status'], string> = {
  all: '全部状态',
  active: '启用中',
  deleted: '已删除',
}

const MEMORY_TYPE_LABELS: Record<'all' | MemoryRecord['type'], string> = {
  all: '全部类型',
  preference: '用户偏好',
  project: '项目记忆',
  feedback: '反馈记录',
  reference: '参考资料',
}

const MEMORY_SOURCE_LABELS: Record<MemoryRecord['source'], string> = {
  auto: '自动生成',
  manual: '手动创建',
}

const formatJsonlForDisplay = (content: string) => {
  return content
    .split('\n')
    .filter(line => line.trim())
    .map(line => {
      try {
        return JSON.stringify(JSON.parse(line), null, 2)
      } catch {
        return line
      }
    })
    .join('\n\n')
}

export default function InspectorPanel() {
  const { currentFile, setCurrentFile, fileContent, setFileContent } = useApp()
  const [isSaving, setIsSaving] = useState(false)
  const [tokenCount, setTokenCount] = useState(0)
  const [hasChanges, setHasChanges] = useState(false)
  const [originalContent, setOriginalContent] = useState('')
  const [memories, setMemories] = useState<MemoryRecord[]>([])
  const [memoryStatusFilter, setMemoryStatusFilter] = useState<'all' | MemoryRecord['status']>('all')
  const [memoryTypeFilter, setMemoryTypeFilter] = useState<'all' | MemoryRecord['type']>('all')
  const [showRawJsonl, setShowRawJsonl] = useState(false)

  const isStructuredMemoryFile = currentFile === MEMORY_FILE_PATH
  const isStructuredTableMode = isStructuredMemoryFile && !showRawJsonl
  const isStructuredRawMode = isStructuredMemoryFile && showRawJsonl
  const displayedFileContent = isStructuredRawMode ? formatJsonlForDisplay(fileContent) : fileContent
  const filteredMemories = memories.filter(memory => {
    const statusMatched = memoryStatusFilter === 'all' || memory.status === memoryStatusFilter
    const typeMatched = memoryTypeFilter === 'all' || memory.type === memoryTypeFilter
    return statusMatched && typeMatched
  })

  const loadCurrentFile = useCallback(async (preserveUnsaved = false) => {
    if (!currentFile) {
      setFileContent('')
      setOriginalContent('')
      setTokenCount(0)
      return
    }

    try {
      const data = await readFile(currentFile)
      setOriginalContent(data.content)
      if (!preserveUnsaved || !hasChanges || fileContent === data.content) {
        setFileContent(data.content)
        setHasChanges(false)
      }
    } catch (err) {
      console.error('读取文件失败:', err)
      if (!preserveUnsaved || !hasChanges) {
        setFileContent(`// 无法读取文件: ${currentFile}`)
      }
    }
  }, [currentFile, fileContent, hasChanges, setFileContent])

  const loadStructuredMemories = useCallback(async () => {
    if (currentFile !== MEMORY_FILE_PATH) return

    try {
      const data = await getMemories()
      setMemories(data.memories)
    } catch (err) {
      console.error('读取结构化记忆失败:', err)
      setMemories([])
    }
  }, [currentFile])

  // 加载文件内容：只在切换文件时加载，编辑内容时不重新拉取覆盖
  useEffect(() => {
    if (!currentFile) {
      setFileContent('')
      setOriginalContent('')
      setTokenCount(0)
      return
    }

    readFile(currentFile)
      .then(data => {
        setOriginalContent(data.content)
        setFileContent(data.content)
        setHasChanges(false)
      })
      .catch(err => {
        console.error('读取文件失败:', err)
        setFileContent(`// 无法读取文件: ${currentFile}`)
      })
  }, [currentFile, setFileContent])

  // 加载结构化记忆
  useEffect(() => {
    if (currentFile !== MEMORY_FILE_PATH) {
      setMemories([])
      setMemoryStatusFilter('all')
      setMemoryTypeFilter('all')
      setShowRawJsonl(false)
      return
    }

    setShowRawJsonl(false)
    loadStructuredMemories()
  }, [currentFile, loadStructuredMemories])

  // 自动刷新打开中的右侧信息框：只刷新只读展示内容，可编辑文件不轮询刷新
  useEffect(() => {
    if (!currentFile || !isStructuredTableMode) return

    const interval = window.setInterval(() => {
      loadCurrentFile(true)
      loadStructuredMemories()
    }, 3000)

    return () => window.clearInterval(interval)
  }, [currentFile, isStructuredTableMode, loadCurrentFile, loadStructuredMemories])

  // 计算 Token 数量
  useEffect(() => {
    if (!currentFile) return

    getFilesTokens([currentFile])
      .then(data => {
        setTokenCount(data.tokens[currentFile] || 0)
      })
      .catch(console.error)
  }, [currentFile, fileContent])

  // 检测内容变化
  useEffect(() => {
    setHasChanges(fileContent !== originalContent)
  }, [fileContent, originalContent])

  // 保存文件
  const handleSave = async () => {
    if (!currentFile || isSaving || isStructuredTableMode) return

    setIsSaving(true)
    try {
      await saveFile(currentFile, fileContent)
      setOriginalContent(fileContent)
      setHasChanges(false)
    } catch (err) {
      console.error('保存失败:', err)
      alert('保存失败，请重试')
    } finally {
      setIsSaving(false)
    }
  }

  // 快捷键保存
  const handleKeyDown = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault()
      handleSave()
    }
  }

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [currentFile, fileContent, isSaving, isStructuredTableMode])

  if (!currentFile) {
    return (
      <div className="h-full flex items-center justify-center bg-white text-gray-400">
        <div className="text-center">
          <FileText size={48} className="mx-auto mb-4 opacity-50" />
          <div className="text-sm">选择一个文件进行编辑</div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-apple-border">
        <div className="flex items-center gap-2 min-w-0">
          <FileText size={16} className="text-gray-400 flex-shrink-0" />
          <span className="text-sm text-gray-700 truncate">{currentFile}</span>
          {hasChanges && !isStructuredTableMode && (
            <span className="w-2 h-2 bg-vibrant-orange rounded-full flex-shrink-0" title="未保存的更改" />
          )}
        </div>
        <div className="flex items-center gap-2">
          {isStructuredMemoryFile && (
            <button
              onClick={() => setShowRawJsonl(value => !value)}
              className="px-3 py-1 text-sm text-klein-blue border border-klein-blue/30 rounded-lg hover:bg-klein-blue/5"
            >
              {showRawJsonl ? '结构化视图' : '查看原始 JSONL'}
            </button>
          )}
          {!isStructuredMemoryFile && (
            <button
              onClick={handleSave}
              disabled={!hasChanges || isSaving}
              className="flex items-center gap-1 px-3 py-1 text-sm text-white bg-klein-blue rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save size={14} />
              {isSaving ? '保存中...' : '保存'}
            </button>
          )}
          <button
            onClick={() => setCurrentFile(null)}
            className="p-1 text-gray-400 hover:text-gray-600"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* 编辑器 */}
      <div className="flex-1 min-h-0">
        {isStructuredTableMode ? (
          <div className="h-full flex flex-col bg-gray-50">
            <div className="px-4 py-3 border-b border-apple-border bg-white space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-gray-500">状态</span>
                {MEMORY_STATUS_FILTERS.map(filter => (
                  <button
                    key={filter}
                    onClick={() => setMemoryStatusFilter(filter)}
                    className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                      memoryStatusFilter === filter
                        ? 'border-klein-blue bg-klein-blue text-white'
                        : 'border-gray-200 text-gray-600 hover:border-klein-blue/40 hover:text-klein-blue'
                    }`}
                  >
                    {MEMORY_STATUS_LABELS[filter]}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-gray-500">类型</span>
                {MEMORY_TYPE_FILTERS.map(filter => (
                  <button
                    key={filter}
                    onClick={() => setMemoryTypeFilter(filter)}
                    className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                      memoryTypeFilter === filter
                        ? 'border-klein-blue bg-klein-blue text-white'
                        : 'border-gray-200 text-gray-600 hover:border-klein-blue/40 hover:text-klein-blue'
                    }`}
                  >
                    {MEMORY_TYPE_LABELS[filter]}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex-1 overflow-auto p-4">
              {filteredMemories.length === 0 ? (
                <div className="h-full flex items-center justify-center text-sm text-gray-400">
                  暂无结构化记忆
                </div>
              ) : (
                <div className="overflow-hidden rounded-xl border border-apple-border bg-white">
                  <table className="min-w-full divide-y divide-apple-border text-sm">
                    <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                      <tr>
                        <th className="px-4 py-3 text-left font-medium">类型</th>
                        <th className="px-4 py-3 text-left font-medium">记忆内容</th>
                        <th className="px-4 py-3 text-left font-medium">来源</th>
                        <th className="px-4 py-3 text-left font-medium">置信度</th>
                        <th className="px-4 py-3 text-left font-medium">状态</th>
                        <th className="px-4 py-3 text-left font-medium">更新时间</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-apple-border text-gray-700">
                      {filteredMemories.map(memory => (
                        <tr key={memory.id} className="align-top">
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="rounded-full bg-klein-blue/10 px-2 py-1 text-xs font-medium text-klein-blue">
                              {MEMORY_TYPE_LABELS[memory.type]}
                            </span>
                          </td>
                          <td className="px-4 py-3 min-w-[280px] max-w-xl whitespace-pre-wrap break-words">
                            {memory.content}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-gray-500">{MEMORY_SOURCE_LABELS[memory.source]}</td>
                          <td className="px-4 py-3 whitespace-nowrap text-gray-500">
                            {typeof memory.confidence === 'number' ? memory.confidence.toFixed(2) : memory.confidence}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                              memory.status === 'active'
                                ? 'bg-green-50 text-green-700'
                                : 'bg-gray-100 text-gray-500'
                            }`}
                            >
                              {MEMORY_STATUS_LABELS[memory.status]}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-gray-500">{memory.updated_at}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        ) : (
          <MonacoEditor
            height="100%"
            defaultLanguage="markdown"
            theme="vs"
            value={displayedFileContent}
            onChange={(value) => {
              if (!isStructuredRawMode) {
                setFileContent(value || '')
              }
            }}
            options={{
              readOnly: isStructuredRawMode,
              minimap: { enabled: false },
              fontSize: 14,
              lineNumbers: 'on',
              wordWrap: 'on',
              scrollBeyondLastLine: false,
              automaticLayout: true,
              padding: { top: 16 },
            }}
          />
        )}
      </div>

      {/* 底部状态栏 */}
      <div className="px-4 py-2 border-t border-apple-border flex items-center justify-between text-xs text-gray-400">
        <span>{isStructuredMemoryFile ? 'JSONL' : 'Markdown'}</span>
        {isStructuredMemoryFile && showRawJsonl ? (
          <button
            onClick={() => setShowRawJsonl(false)}
            className="text-klein-blue hover:underline"
          >
            返回结构化视图
          </button>
        ) : (
          <span>{tokenCount.toLocaleString()} tokens</span>
        )}
      </div>
    </div>
  )
}
