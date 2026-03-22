'use client'

import { Bot, Clock, CheckCircle, XCircle, Loader2, Zap } from 'lucide-react'

export interface SubTaskData {
  id: string
  taskType: string
  targetAgent: string
  status: 'pending' | 'processing' | 'finished' | 'failed'
  content: string
  result?: string
  createdAt: string
  updatedAt: string
  startTime?: number
  endTime?: number
}

interface SubTaskCardProps {
  subtask: SubTaskData
  isExpanded?: boolean
  onToggle?: () => void
}

const statusConfig = {
  pending: {
    icon: Bot,
    iconClass: 'text-gray-400',
    label: '待执行',
    labelClass: 'bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-gray-400',
    borderClass: 'border-gray-200 dark:border-slate-700',
  },
  processing: {
    icon: Loader2,
    iconClass: 'text-blue-500 animate-spin',
    label: '执行中',
    labelClass: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    borderClass: 'border-blue-300 dark:border-blue-800',
  },
  finished: {
    icon: CheckCircle,
    iconClass: 'text-green-500',
    label: '已完成',
    labelClass: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    borderClass: 'border-green-300 dark:border-green-800',
  },
  failed: {
    icon: XCircle,
    iconClass: 'text-red-500',
    label: '失败',
    labelClass: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    borderClass: 'border-red-300 dark:border-red-800',
  },
}

const agentColors: Record<string, string> = {
  primary_agent: 'bg-blue-500',
  coordinator_agent: 'bg-purple-500',
  data_agent: 'bg-orange-500',
  doc_agent: 'bg-green-500',
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDuration(startTime?: number, endTime?: number): string {
  if (!startTime) return ''
  const end = endTime || Date.now()
  const seconds = Math.floor((end - startTime) / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}m ${secs}s`
}

export default function SubTaskCard({ subtask, isExpanded = false, onToggle }: SubTaskCardProps) {
  const config = statusConfig[subtask.status]
  const Icon = config.icon
  const agentColor = agentColors[subtask.targetAgent] || 'bg-gray-500'

  return (
    <div
      className={`rounded-lg border ${config.borderClass} bg-white dark:bg-slate-800 overflow-hidden transition-all duration-200`}
    >
      <div
        className="p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-slate-700"
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          {/* Agent图标 */}
          <div className={`w-8 h-8 rounded-full ${agentColor} flex items-center justify-center flex-shrink-0`}>
            <Bot size={14} className="text-white" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                {subtask.content}
              </span>
              <span className={`px-1.5 py-0.5 rounded text-xs ${config.labelClass}`}>
                {config.label}
              </span>
            </div>
            <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 dark:text-gray-400">
              <span className="flex items-center gap-1">
                <Zap size={10} />
                {subtask.targetAgent}
              </span>
              <span className="flex items-center gap-1">
                <Clock size={10} />
                {formatTime(subtask.createdAt)}
              </span>
              {subtask.startTime && (
                <span>{formatDuration(subtask.startTime, subtask.endTime)}</span>
              )}
            </div>
          </div>

          <Icon size={16} className={config.iconClass} />
        </div>
      </div>

      {/* 展开内容 */}
      {isExpanded && subtask.result && (
        <div className="px-3 pb-3 pt-0">
          <div className="bg-gray-50 dark:bg-slate-900 rounded-lg p-2 text-xs text-gray-600 dark:text-gray-300 whitespace-pre-wrap">
            {subtask.result}
          </div>
        </div>
      )}
    </div>
  )
}
