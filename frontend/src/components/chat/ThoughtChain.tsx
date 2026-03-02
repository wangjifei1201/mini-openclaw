'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight, Terminal, Code, Globe, FileText, Search } from 'lucide-react'
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
  
  if (toolCalls.length === 0) return null
  
  return (
    <div className="mb-2">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 mb-1"
      >
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span>工具调用 ({toolCalls.length})</span>
      </button>
      
      {isExpanded && (
        <div className="thought-chain space-y-2">
          {toolCalls.map((call, idx) => (
            <div key={idx} className="bg-gray-50 rounded-lg p-3 text-sm">
              {/* 工具名称 */}
              <div className="flex items-center gap-2 text-gray-700 font-medium mb-2">
                <span className="text-klein-blue">
                  {TOOL_ICONS[call.tool] || <Terminal size={14} />}
                </span>
                {TOOL_NAMES[call.tool] || call.tool}
              </div>
              
              {/* 输入 */}
              <div className="mb-2">
                <div className="text-xs text-gray-400 mb-1">输入:</div>
                <pre className="text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                  {typeof call.input === 'string'
                    ? call.input
                    : JSON.stringify(call.input, null, 2)}
                </pre>
              </div>
              
              {/* 输出 */}
              <div>
                <div className="text-xs text-gray-400 mb-1">输出:</div>
                <pre className="text-xs bg-gray-100 p-2 rounded overflow-x-auto max-h-40">
                  {call.output}
                </pre>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
