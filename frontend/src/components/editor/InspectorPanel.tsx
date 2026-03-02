'use client'

import { useState, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { X, Save, FileText } from 'lucide-react'
import { useApp } from '@/lib/store'
import { readFile, saveFile, getFilesTokens } from '@/lib/api'

// 动态导入 Monaco Editor（避免 SSR 问题）
const MonacoEditor = dynamic(
  () => import('@monaco-editor/react'),
  { ssr: false, loading: () => <div className="h-full flex items-center justify-center text-gray-400">加载编辑器...</div> }
)

export default function InspectorPanel() {
  const { currentFile, setCurrentFile, fileContent, setFileContent } = useApp()
  const [isSaving, setIsSaving] = useState(false)
  const [tokenCount, setTokenCount] = useState(0)
  const [hasChanges, setHasChanges] = useState(false)
  const [originalContent, setOriginalContent] = useState('')
  
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
    if (!currentFile || isSaving) return
    
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
  }, [currentFile, fileContent, isSaving])
  
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
          {hasChanges && (
            <span className="w-2 h-2 bg-vibrant-orange rounded-full flex-shrink-0" title="未保存的更改" />
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
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
      <div className="flex-1">
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
      </div>
      
      {/* 底部状态栏 */}
      <div className="px-4 py-2 border-t border-apple-border flex items-center justify-between text-xs text-gray-400">
        <span>Markdown</span>
        <span>{tokenCount.toLocaleString()} tokens</span>
      </div>
    </div>
  )
}
