'use client'

import { Bot, Zap, Users, ChevronRight } from 'lucide-react'
import { StrategyAnalysis } from '@/lib/api'

interface StrategyIndicatorProps {
  strategy: StrategyAnalysis
  compact?: boolean
}

export default function StrategyIndicator({ strategy, compact = false }: StrategyIndicatorProps) {
  const isMultiAgent = strategy.strategy === 'multi'
  
  if (compact) {
    return (
      <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${
        isMultiAgent 
          ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300' 
          : 'bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-gray-400'
      }`}>
        {isMultiAgent ? (
          <>
            <Users size={12} />
            <span>多Agent</span>
          </>
        ) : (
          <>
            <Bot size={12} />
            <span>单Agent</span>
          </>
        )}
      </div>
    )
  }
  
  return (
    <div className={`rounded-lg border p-3 mb-2 ${
      isMultiAgent 
        ? 'bg-purple-50 border-purple-200 dark:bg-purple-900/20 dark:border-purple-800' 
        : 'bg-gray-50 border-gray-200 dark:bg-slate-800 dark:border-slate-700'
    }`}>
      {/* 策略标题 */}
      <div className="flex items-center gap-2 mb-2">
        {isMultiAgent ? (
          <div className="flex items-center gap-1.5 text-purple-600 dark:text-purple-400">
            <Users size={16} />
            <span className="font-medium text-sm">多Agent协同执行</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
            <Bot size={16} />
            <span className="font-medium text-sm">单Agent执行</span>
          </div>
        )}
        
        {/* 置信度 */}
        <div className="ml-auto text-xs text-gray-400 dark:text-gray-500">
          置信度: {Math.round(strategy.confidence * 100)}%
        </div>
      </div>
      
      {/* 原因说明 */}
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
        {strategy.reason}
      </div>
      
      {/* 目标Agent */}
      {isMultiAgent && strategy.target_agent && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-500 dark:text-gray-400">目标Agent:</span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-white dark:bg-slate-700 rounded border dark:border-slate-600">
            <Zap size={12} className="text-vibrant-orange" />
            <span className="font-medium text-gray-700 dark:text-gray-200">{strategy.target_agent}</span>
          </span>
          {strategy.task_type && (
            <span className="text-xs text-gray-400 dark:text-gray-500">
              ({strategy.task_type})
            </span>
          )}
        </div>
      )}
      
      {/* 子任务列表 */}
      {strategy.sub_tasks && strategy.sub_tasks.length > 0 && (
        <div className="mt-2 pt-2 border-t border-gray-200 dark:border-slate-700">
          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">子任务分配:</div>
          <div className="space-y-1">
            {strategy.sub_tasks.map((task, index) => (
              <div key={index} className="flex items-center gap-2 text-xs">
                <ChevronRight size={12} className="text-gray-400 dark:text-gray-500" />
                <span className="text-gray-600 dark:text-gray-300">{task.task_type}</span>
                <span className="text-gray-400 dark:text-gray-500">→</span>
                <span className="font-medium text-gray-700 dark:text-gray-200">{task.target_agent}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


interface AgentExecutionIndicatorProps {
  agentName: string
  status: 'pending' | 'processing' | 'finished' | 'failed'
  taskType?: string
}

export function AgentExecutionIndicator({ agentName, status, taskType }: AgentExecutionIndicatorProps) {
  const statusConfig = {
    pending: { color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400', icon: '⏳', text: '等待中' },
    processing: { color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400', icon: '🔄', text: '执行中' },
    finished: { color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400', icon: '✅', text: '已完成' },
    failed: { color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400', icon: '❌', text: '失败' },
  }
  
  const config = statusConfig[status]
  
  return (
    <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs ${config.color}`}>
      <span>{config.icon}</span>
      <span className="font-medium">{agentName}</span>
      {taskType && <span className="opacity-70">· {taskType}</span>}
      <span className="opacity-70">· {config.text}</span>
    </div>
  )
}
