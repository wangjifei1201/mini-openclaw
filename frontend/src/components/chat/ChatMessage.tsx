'use client'

import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import { User, Bot, FileText, Image as ImageIcon } from 'lucide-react'
import { Message } from '@/lib/store'
import ThoughtChain from './ThoughtChain'
import RetrievalCard from './RetrievalCard'

interface ChatMessageProps {
  message: Message
}

// 递归提取 React children 中的所有文本内容
function extractText(children: React.ReactNode): string {
  if (typeof children === 'string') return children
  if (typeof children === 'number') return String(children)
  if (!children) return ''
  if (Array.isArray(children)) {
    return children.map(extractText).join('')
  }
  if (React.isValidElement(children) && children.props?.children) {
    return extractText(children.props.children)
  }
  return ''
}

// 检测是否包含 box-drawing 字符（ASCII art）
const BOX_DRAWING_REGEX = /[┌┐└┘├┤┬┴┼─│═║╔╗╚╝╠╣╦╩╬▼▲◀▶■□▪▫●○◆◇★☆→←↑↓↔↕]/

// HTML 净化配置：允许基本 HTML 标签，阻止危险标签和属性
const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [
    ...(defaultSchema.tagNames || []),
    'a', 'b', 'i', 'em', 'strong', 'u', 's', 'del', 'ins',
    'p', 'br', 'hr',
    'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'pre', 'code',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'span', 'div', 'sub', 'sup', 'mark', 'abbr',
    'details', 'summary',
    'dl', 'dt', 'dd',
    'img',
  ],
  attributes: {
    ...defaultSchema.attributes,
    a: ['href', 'title', 'target', 'rel'],
    img: ['src', 'alt', 'title', 'width', 'height'],
    td: ['align', 'valign', 'colspan', 'rowspan'],
    th: ['align', 'valign', 'colspan', 'rowspan'],
    span: ['style'],
    code: ['className'],
    '*': ['className'],
  },
  protocols: {
    ...defaultSchema.protocols,
    href: ['http', 'https', 'mailto'],
    src: ['http', 'https'],
  },
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'
  
  return (
    <div className={`flex gap-2 md:gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* 头像 */}
      <div
        className={`w-6 h-6 md:w-8 md:h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          isUser ? 'bg-vibrant-orange' : 'bg-klein-blue'
        }`}
      >
        {isUser ? (
          <User size={14} className="md:w-4 md:h-4" />
        ) : (
          <Bot size={14} className="md:w-4 md:h-4" />
        )}
      </div>
      
      {/* 消息内容 */}
      <div className={`flex-1 max-w-[85%] md:max-w-[80%] ${isUser ? 'text-right' : ''}`}>
        {/* 检索结果 */}
        {message.retrievals && message.retrievals.length > 0 && (
          <RetrievalCard retrievals={message.retrievals} />
        )}
        
        {/* 附件列表 */}
        {message.attachments && message.attachments.length > 0 && (
          <div className={`mb-2 flex flex-wrap gap-1 md:gap-2 ${isUser ? 'justify-end' : ''}`}>
            {message.attachments.map((att, index) => (
              <div
                key={`${att.path}-${index}`}
                className={`inline-flex items-center gap-1 md:gap-2 px-2 md:px-3 py-1 md:py-1.5 rounded-lg text-xs md:text-sm ${
                  isUser ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                }`}
              >
                {att.type === 'image' ? (
                  <ImageIcon size={12} className="md:w-3.5 md:h-3.5 flex-shrink-0" />
                ) : (
                  <FileText size={12} className="md:w-3.5 md:h-3.5 flex-shrink-0" />
                )}
                <span className="truncate max-w-[120px] md:max-w-[180px]">{att.filename}</span>
                <span className="text-xs opacity-60 hidden sm:inline">
                  {att.size < 1024
                    ? `${att.size}B`
                    : att.size < 1024 * 1024
                    ? `${(att.size / 1024).toFixed(1)}KB`
                    : `${(att.size / 1024 / 1024).toFixed(1)}MB`}
                </span>
              </div>
            ))}
          </div>
        )}
        
        {/* 思维链（工具调用） */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <ThoughtChain toolCalls={message.tool_calls} />
        )}
        
        {/* 消息气泡 */}
        <div
          className={`inline-block p-2 md:p-3 rounded-2xl text-sm md:text-base ${
            isUser
              ? 'bg-klein-blue text-white rounded-tr-sm'
              : 'bg-white shadow-sm rounded-tl-sm'
          }`}
        >
          {message.isStreaming && !message.content ? (
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-pulse" />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-pulse delay-100" />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-pulse delay-200" />
            </div>
          ) : (
            <div className={`markdown-content ${isUser ? 'text-white' : 'text-gray-800'}`}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw, [rehypeSanitize, sanitizeSchema]]}
                components={{
                  // 自定义代码块渲染
                  pre({ children, ...props }) {
                    return (
                      <pre className="my-2 whitespace-pre overflow-x-auto" {...props}>
                        {children}
                      </pre>
                    )
                  },
                  code({ node, className, children, style, ...props }) {
                    const match = /language-(\w+)/.exec(className || '')
                    // 检查父节点是否为 pre，如果是则为代码块
                    const isInline = !(node as any)?.properties?.className && 
                                     !String(children).includes('\n')
                    
                    if (isInline) {
                      return (
                        <code
                          className={`${isUser ? 'bg-blue-700' : 'bg-gray-100'} px-1 rounded`}
                          {...props}
                        >
                          {children}
                        </code>
                      )
                    }
                    
                    return (
                      <code className={`${className || ''} whitespace-pre`} {...props}>
                        {children}
                      </code>
                    )
                  },
                  // 段落渲染 - 检测 ASCII art 并使用等宽字体
                  p({ children }) {
                    const text = extractText(children)
                    // 检测是否包含 box-drawing 字符
                    const hasBoxDrawing = BOX_DRAWING_REGEX.test(text)
                    
                    if (hasBoxDrawing) {
                      return (
                        <pre className="my-2 whitespace-pre overflow-x-auto bg-gray-800 text-gray-100 p-3 rounded-lg text-sm">
                          {children}
                        </pre>
                      )
                    }
                    
                    return <p>{children}</p>
                  },
                  // 链接样式
                  a({ children, ...props }) {
                    return (
                      <a
                        {...props}
                        className={`underline ${isUser ? 'text-blue-200' : 'text-klein-blue'}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {children}
                      </a>
                    )
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
        
        {/* 流式状态指示器 */}
        {message.isStreaming && message.content && (
          <span className="inline-block w-2 h-4 bg-klein-blue animate-pulse ml-1" />
        )}
      </div>
    </div>
  )
}
