'use client'

import { useState, useRef, KeyboardEvent, ChangeEvent } from 'react'
import { Send, Paperclip, X, FileText, Image as ImageIcon } from 'lucide-react'
import { useApp, type Attachment } from '@/lib/store'
import { uploadFiles } from '@/lib/api'

const IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'])

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

export default function ChatInput() {
  const [input, setInput] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { sendMessage, isStreaming, currentSessionId } = useApp()
  
  const handleSubmit = async () => {
    const content = input.trim()
    if ((!content && selectedFiles.length === 0) || isStreaming || !currentSessionId || isUploading) return
    
    setIsUploading(true)
    
    try {
      let attachments: Attachment[] | undefined
      if (selectedFiles.length > 0) {
        const result = await uploadFiles(selectedFiles)
        attachments = result.uploaded_files.map(file => ({
          filename: file.filename,
          path: file.path,
          size: file.size,
          type: IMAGE_TYPES.has(
            selectedFiles.find(f => f.name === file.filename)?.type || ''
          ) ? 'image' as const : 'document' as const
        }))
      }
      
      sendMessage(content || '请帮我查看这些文件', attachments)
      
      setInput('')
      setSelectedFiles([])
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    } catch (error) {
      console.error('发送失败:', error)
      alert(`发送失败: ${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setIsUploading(false)
    }
  }
  
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }
  
  const handleInput = () => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
    }
  }
  
  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return
    
    const newFiles = files.filter(
      newFile => !selectedFiles.some(
        existing => existing.name === newFile.name && existing.size === newFile.size
      )
    )
    setSelectedFiles(prev => [...prev, ...newFiles])
    
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }
  
  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index))
  }
  
  const isDisabled = !currentSessionId || isStreaming || isUploading
  
  return (
    <div className="space-y-2">
      {/* 文件预览区 */}
      {selectedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selectedFiles.map((file, index) => {
            const isImage = IMAGE_TYPES.has(file.type)
            return (
              <div
                key={`${file.name}-${index}`}
                className="relative group flex items-center gap-2 bg-gray-100 rounded-lg px-2 md:px-3 py-2 pr-6 md:pr-8 max-w-xs"
              >
                {isImage ? (
                  <ImageIcon size={14} className="text-vibrant-orange flex-shrink-0" />
                ) : (
                  <FileText size={14} className="text-klein-blue flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="text-xs md:text-sm text-gray-800 truncate">{file.name}</div>
                  <div className="text-xs text-gray-500">{formatFileSize(file.size)}</div>
                </div>
                <button
                  onClick={() => removeFile(index)}
                  className="absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-gray-200 transition-colors"
                >
                  <X size={12} className="text-gray-500" />
                </button>
              </div>
            )
          })}
        </div>
      )}
      
      {/* 输入区 */}
      <div className="flex items-end gap-2">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder={
              !currentSessionId
                ? '请先选择或创建一个会话'
                : isStreaming
                ? '等待回复中...'
                : isUploading
                ? '上传文件中...'
                : '输入消息，Enter 发送，Shift+Enter 换行'
            }
            disabled={isDisabled}
            rows={1}
            className="w-full resize-none rounded-2xl border border-apple-border px-3 md:px-4 py-2 md:py-3 pr-16 md:pr-20 text-gray-800 placeholder-gray-400 focus:border-klein-blue focus:ring-0 disabled:bg-gray-50 disabled:cursor-not-allowed text-sm md:text-base"
            style={{ maxHeight: '200px' }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isDisabled}
            className="absolute right-10 md:right-12 bottom-1.5 md:bottom-2 p-1.5 md:p-2 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="添加附件"
          >
            <Paperclip size={16} className="md:w-5 md:h-5" />
          </button>
          <button
            onClick={handleSubmit}
            disabled={isDisabled || (!input.trim() && selectedFiles.length === 0)}
            className="absolute right-1.5 md:right-2 bottom-1.5 md:bottom-2 p-1.5 md:p-2 rounded-full bg-klein-blue text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
          >
            <Send size={16} className="md:w-5 md:h-5" />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".jpg,.jpeg,.png,.gif,.webp,.svg,.bmp,.txt,.md,.pdf,.csv,.json,.xml,.yaml,.yml,.py,.js,.ts,.tsx,.jsx,.html,.css,.log,.sql,.sh"
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>
      </div>
    </div>
  )
}
