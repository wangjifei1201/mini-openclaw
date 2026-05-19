'use client'

import { useState, useEffect } from 'react'
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
const MEMORY_FILTERS: Array<'all' | MemoryRecord['status'] | MemoryRecord['type']> = [
  'all',
  'active',
  'deleted',
  'preference',
  'project',
  'feedback',
  'reference',
]

const MEMORY_FILTER_LABELS: Record<'all' | MemoryRecord['status'] | MemoryRecord['type'], string> = {
  all: '全部',
  active: 'active',
  deleted: 'deleted',
  preference: 'preference',
  project: 'project',
  feedback: 'feedback',
  reference: 'reference',
}

export default function InspectorPanel() {
  const { currentFile, setCurrentFile, fileContent, setFileContent } = useApp()
  const [isSaving, setIsSaving] = useState(false)
  const [tokenCount, setTokenCount] = useState(0)
  const [hasChanges, setHasChanges] = useState(false)
  const [originalContent, setOriginalContent] = useState('')
  const [memories, setMemories] = useState<MemoryRecord[]>([])
  const [memoryFilter, setMemoryFilter] = useState<'all' | MemoryRecord['status'] | MemoryRecord['type']>('all')
  const [showRawJsonl, setShowRawJsonl] = useState(false)

  const isStructuredMemoryFile = currentFile === MEMORY_FILE_PATH
  const isStructuredTableMode = isStructuredMemoryFile && !showRawJsonl
  const filteredMemories = memories.filter(memory => {
    if (memoryFilter === 'all') return true
    return memory.status === memoryFilter || memory.type === memoryFilter
  })

  // 加载文件内容
  useEffect(() => {
    if (!currentFile) {
      setFileContent('')
      setOriginalContent('')
      setTokenCount(0)
      return
    }

    readFile(currentFile)
      .then(data => {
        setFileContent(data.content)
        setOriginalContent(data.content)
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
      setMemoryFilter('all')
      setShowRawJsonl(false)
      return
    }

    setShowRawJsonl(false)
    getMemories()
      .then(data => setMemories(data.memories))
      .catch(err => {
        console.error('读取结构化记忆失败:', err)
        setMemories([])
      })
  }, [currentFile])

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
          <button
            onClick={handleSave}
            disabled={isStructuredTableMode || !hasChanges || isSaving}
            className="flex items-center gap-1 px-3 py-1 text-sm text-white bg-klein-blue rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save size={14} />
            {isSaving ? '保存中...' : '保存'}
          </button>
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
            <div className="px-4 py-3 border-b border-apple-border bg-white">
              <div className="flex flex-wrap items-center gap-2">
                {MEMORY_FILTERS.map(filter => (
                  <button
                    key={filter}
                    onClick={() => setMemoryFilter(filter)}
                    className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                      memoryFilter === filter
                        ? 'border-klein-blue bg-klein-blue text-white'
                        : 'border-gray-200 text-gray-600 hover:border-klein-blue/40 hover:text-klein-blue'
                    }`}
                  >
                    {MEMORY_FILTER_LABELS[filter]}
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
                        <th className="px-4 py-3 text-left font-medium">type</th>
                        <th className="px-4 py-3 text-left font-medium">content</th>
                        <th className="px-4 py-3 text-left font-medium">source</th>
                        <th className="px-4 py-3 text-left font-medium">confidence</th>
                        <th className="px-4 py-3 text-left font-medium">status</th>
                        <th className="px-4 py-3 text-left font-medium">updated_at</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-apple-border text-gray-700">
                      {filteredMemories.map(memory => (
                        <tr key={memory.id} className="align-top">
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="rounded-full bg-klein-blue/10 px-2 py-1 text-xs font-medium text-klein-blue">
                              {memory.type}
                            </span>
                          </td>
                          <td className="px-4 py-3 min-w-[280px] max-w-xl whitespace-pre-wrap break-words">
                            {memory.content}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-gray-500">{memory.source}</td>
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
                              {memory.status}
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
            value={fileContent}
            onChange={(value) => setFileContent(value || '')}
            options={{
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
