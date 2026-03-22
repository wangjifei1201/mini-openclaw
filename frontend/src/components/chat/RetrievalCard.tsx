'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight, Brain } from 'lucide-react'
import { RetrievalResult } from '@/lib/store'

interface RetrievalCardProps {
  retrievals: RetrievalResult[]
}

export default function RetrievalCard({ retrievals }: RetrievalCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  
  if (retrievals.length === 0) return null
  
  return (
    <div className="retrieval-card mb-2">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm text-purple-700 dark:text-purple-300 font-medium w-full"
      >
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Brain size={14} />
        <span>记忆检索结果 ({retrievals.length})</span>
      </button>
      
      {isExpanded && (
        <div className="mt-2 space-y-2">
          {retrievals.map((result, idx) => (
            <div key={idx} className="bg-white/50 dark:bg-slate-800/50 rounded p-2 text-sm">
              <div className="flex items-center justify-between text-xs text-purple-600 dark:text-purple-400 mb-1">
                <span>来源: {result.source}</span>
                <span>相关度: {(result.score * 100).toFixed(0)}%</span>
              </div>
              <div className="text-gray-700 dark:text-gray-300 text-xs leading-relaxed">
                {result.text}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
