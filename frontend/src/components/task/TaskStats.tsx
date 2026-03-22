'use client'

import { Cpu, ArrowUpCircle, ArrowDownCircle, Wrench, Clock, CheckCircle } from 'lucide-react'

export interface TaskStatsData {
  // LLM调用统计
  llmCallCount: number
  llmCallsByAgent?: Record<string, number>

  // Token统计
  inputTokens: number
  outputTokens: number
  totalTokens: number
  tokensByAgent?: Record<string, { input: number; output: number }>

  // 工具调用统计
  toolCallCount: number
  toolCallsByName?: Record<string, number>

  // 耗时统计
  startTime: number
  elapsedTime: number
  estimatedRemaining?: number

  // Agent参与统计
  activeAgents?: string[]
  completedSubTasks: number
  totalSubTasks: number
}

interface TaskStatsProps {
  stats: TaskStatsData
  compact?: boolean
}

function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = Math.floor(seconds / 60)
  const secs = (seconds % 60).toFixed(0)
  return `${minutes}m ${secs}s`
}

function formatTokens(tokens: number): string {
  if (tokens < 1000) return tokens.toString()
  if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`
  return `${(tokens / 1000000).toFixed(2)}M`
}

export default function TaskStats({ stats, compact = false }: TaskStatsProps) {
  const progress = stats.totalSubTasks > 0 
    ? Math.round((stats.completedSubTasks / stats.totalSubTasks) * 100) 
    : 0

  if (compact) {
    return (
      <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-1">
          <Cpu size={12} />
          <span>{stats.llmCallCount}</span>
        </div>
        <div className="flex items-center gap-1">
          <ArrowUpCircle size={12} />
          <span>{formatTokens(stats.inputTokens)}</span>
        </div>
        <div className="flex items-center gap-1">
          <ArrowDownCircle size={12} />
          <span>{formatTokens(stats.outputTokens)}</span>
        </div>
        <div className="flex items-center gap-1">
          <Wrench size={12} />
          <span>{stats.toolCallCount}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700 p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-200 flex items-center gap-1.5">
          <Cpu size={14} className="text-purple-500" />
          执行统计
        </h3>
        <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
          <Clock size={12} />
          <span>{formatTime(stats.elapsedTime)}</span>
        </div>
      </div>

      {/* 进度条 */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500 dark:text-gray-400">任务进度</span>
          <span className="text-gray-700 dark:text-gray-200 font-medium">{progress}%</span>
        </div>
        <div className="h-2 bg-gray-100 dark:bg-slate-700 rounded-full overflow-hidden">
          <div 
            className="h-full bg-purple-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="text-xs text-gray-400 dark:text-gray-500">
          {stats.completedSubTasks} / {stats.totalSubTasks} 子任务完成
        </div>
      </div>

      {/* 统计数据网格 */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-gray-50 dark:bg-slate-900 rounded-lg p-2">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mb-1">
            <Cpu size={12} className="text-blue-500" />
            LLM调用
          </div>
          <div className="text-lg font-semibold text-gray-800 dark:text-gray-100">{stats.llmCallCount}</div>
        </div>

        <div className="bg-gray-50 dark:bg-slate-900 rounded-lg p-2">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mb-1">
            <Wrench size={12} className="text-orange-500" />
            工具调用
          </div>
          <div className="text-lg font-semibold text-gray-800 dark:text-gray-100">{stats.toolCallCount}</div>
        </div>

        <div className="bg-gray-50 dark:bg-slate-900 rounded-lg p-2">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mb-1">
            <ArrowUpCircle size={12} className="text-green-500" />
            输入Token
          </div>
          <div className="text-lg font-semibold text-gray-800 dark:text-gray-100">{formatTokens(stats.inputTokens)}</div>
        </div>

        <div className="bg-gray-50 dark:bg-slate-900 rounded-lg p-2">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mb-1">
            <ArrowDownCircle size={12} className="text-red-500" />
            输出Token
          </div>
          <div className="text-lg font-semibold text-gray-800 dark:text-gray-100">{formatTokens(stats.outputTokens)}</div>
        </div>
      </div>

      {/* 总Token消耗 */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-slate-700">
        <span className="text-xs text-gray-500 dark:text-gray-400">总Token消耗</span>
        <span className="text-sm font-semibold text-purple-600 dark:text-purple-400">{formatTokens(stats.totalTokens)}</span>
      </div>
    </div>
  )
}
