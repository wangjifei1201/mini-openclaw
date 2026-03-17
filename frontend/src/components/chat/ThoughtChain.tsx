'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight, Terminal, Code, Globe, FileText, Search, AlertCircle, Clock } from 'lucide-react'
import { ToolCall } from '@/lib/store'

interface ThoughtChainProps {
  toolCalls: ToolCall[]
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  terminal: <Terminal size={14} />,
  python_repl: <Code size={14} />,
  fetch_url: <Globe size={14} />,
  read_file: <FileText size={14} />,
  search_knowledge_base: <Search size={14} />,
}

const TOOL_NAMES: Record<string, string> = {
  terminal: '终端',
  python_repl: 'Python',
  fetch_url: '网络请求',
  read_file: '读取文件',
  search_knowledge_base: '知识库搜索',
}

export default function ThoughtChain({ toolCalls }: ThoughtChainProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [expandedIds, setExpandedIds] = useState<Record<number, boolean>>({})
  const [showOnlyFailures, setShowOnlyFailures] = useState(false)

  if (toolCalls.length === 0) return null

  const toggleExpanded = (idx: number) => {
    setExpandedIds(prev => ({ ...prev, [idx]: !prev[idx] }))
  }

  const copyToClipboard = (text: string) => {
    if (!text) return
    navigator.clipboard.writeText(text).catch(() => {})
  }

  const failureCount = toolCalls.filter(c => c.tool_status === 'error').length
  const displayCalls = showOnlyFailures 
    ? toolCalls.filter(c => c.tool_status === 'error')
    : toolCalls

  // 失败时自动展开 tool_error
  const getAutoExpandItems = (call: ToolCall, idx: number) => {
    if (call.tool_status === 'error' && !expandedIds[idx]) {
      setExpandedIds(prev => ({ ...prev, [idx]: true }))
    }
  }

  const formatElapsedTime = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  return (
    <div className="mb-2">
      <div className="flex items-center gap-1 md:gap-2 mb-2">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
        >
          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span className="hidden sm:inline">工具调用 ({toolCalls.length})</span>
          <span className="sm:hidden">工具 ({toolCalls.length})</span>
          {failureCount > 0 && (
            <span className="text-red-500 font-medium">({failureCount} 失败)</span>
          )}
        </button>

        {isExpanded && failureCount > 0 && (
          <button
            onClick={() => setShowOnlyFailures(!showOnlyFailures)}
            className={`text-xs px-2 py-1 rounded transition ${
              showOnlyFailures
                ? 'bg-red-100 text-red-700 hover:bg-red-200'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {showOnlyFailures ? '清除过滤' : '仅显示失败'}
          </button>
        )}
      </div>

      {isExpanded && (
        <div className="thought-chain space-y-2">
          {displayCalls.map((call, displayIdx) => {
            // 计算原始索引用于展开状态管理
            const originalIdx = showOnlyFailures 
              ? toolCalls.indexOf(call)
              : displayIdx

            const status = call.tool_status ?? 'ok'
            const isError = status === 'error'
            const sourceLabel = call.source === 'llm' ? 'LLM' : '工具'

            // 失败时自动展开
            if (isError && !expandedIds[originalIdx]) {
              setTimeout(() => {
                setExpandedIds(prev => ({ ...prev, [originalIdx]: true }))
              }, 0)
            }

            return (
              <div
                key={originalIdx}
                className={`rounded-lg p-2 md:p-3 text-sm border transition ${
                  isError
                    ? 'bg-red-50 border-red-300 shadow-sm'
                    : 'bg-gray-50 border-gray-200'
                }`}
              >
                {/* 标题行 */}
                <div className="flex items-start justify-between gap-1 md:gap-2 mb-2">
                  <div className="flex items-center gap-1 md:gap-2 text-gray-700 font-medium flex-1 min-w-0">
                    <span className={isError ? 'text-red-500' : 'text-gray-400'}>
                      {isError ? (
                        <AlertCircle size={14} />
                      ) : (
                        TOOL_ICONS[call.tool] || <Terminal size={14} />
                      )}
                    </span>
                    <span className="text-xs md:text-sm truncate">{TOOL_NAMES[call.tool] || call.tool}</span>
                    <span className="text-xs text-gray-500 hidden sm:inline">({sourceLabel})</span>
                  </div>

                  <div className="flex items-center gap-1 md:gap-2 text-xs flex-shrink-0">
                    {call.elapsed_time !== undefined && (
                      <span className="inline-flex items-center gap-1 text-gray-500">
                        <Clock size={12} />
                        <span className="hidden sm:inline">{formatElapsedTime(call.elapsed_time * 1000)}</span>
                        <span className="sm:hidden">{formatElapsedTime(call.elapsed_time * 1000).slice(0, 4)}</span>
                      </span>
                    )}
                    <span
                      className={`rounded px-1 md:px-2 py-0.5 font-medium text-xs ${
                        isError
                          ? 'bg-red-100 text-red-700'
                          : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {status === 'ok' ? '成功' : '失败'}
                    </span>
                    {call.tool_call_id && (
                      <button
                        onClick={() => toggleExpanded(originalIdx)}
                        className={`${
                          expandedIds[originalIdx]
                            ? 'text-gray-600'
                            : 'text-gray-400 hover:text-gray-600'
                        }`}
                      >
                        {expandedIds[originalIdx] ? '收起' : 'ID'}
                      </button>
                    )}
                  </div>
                </div>

                {/* 工具调用 ID */}
                {expandedIds[originalIdx] && call.tool_call_id && (
                  <div className="mb-2 flex items-center justify-between text-xs text-gray-500">
                    <span className="break-all font-mono">ID: {call.tool_call_id}</span>
                    <button
                      className="text-blue-500 hover:underline"
                      onClick={() => copyToClipboard(call.tool_call_id ?? '')}
                    >
                      复制
                    </button>
                  </div>
                )}

                {/* 输入 */}
                <div className="mb-2">
                  <div className="text-xs text-gray-400 mb-1">输入:</div>
                  <pre className="text-xs bg-gray-100 p-2 rounded overflow-x-auto max-w-full">
                    {typeof (call.tool_input ?? call.input) === 'string'
                      ? call.tool_input ?? call.input
                      : JSON.stringify(call.tool_input ?? call.input, null, 2)}
                  </pre>
                </div>

                {/* 输出或错误 */}
                <div>
                  <div className={`text-xs mb-1 ${isError ? 'text-red-600 font-medium' : 'text-gray-400'}`}>
                    {isError ? '✗ 错误输出:' : '输出:'}
                  </div>
                  <pre
                    className={`text-xs p-2 rounded overflow-x-auto max-w-full max-h-32 md:max-h-40 ${
                      isError
                        ? 'bg-red-100 text-red-900 border border-red-200'
                        : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {call.tool_error ?? call.tool_output ?? call.output}
                  </pre>
                </div>
              </div>
            )
          })}

          {showOnlyFailures && displayCalls.length === 0 && (
            <div className="text-xs text-gray-500 text-center py-4">
              没有失败的工具调用
            </div>
          )}
        </div>
      )}
    </div>
  )
}
