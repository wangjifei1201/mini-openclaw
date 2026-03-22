'use client'

import { CheckCircle, Circle, Loader2, XCircle, ChevronRight } from 'lucide-react'

export interface TodoItem {
  id: string
  content: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  agent?: string
  startTime?: number
  endTime?: number
  result?: string
}

interface TodoListProps {
  todos: TodoItem[]
  title?: string
}

const statusConfig = {
  pending: {
    icon: Circle,
    iconClass: 'text-gray-400',
    textClass: 'text-gray-500 dark:text-gray-400',
    bgClass: 'bg-gray-50 dark:bg-slate-800',
  },
  in_progress: {
    icon: Loader2,
    iconClass: 'text-blue-500 animate-spin',
    textClass: 'text-blue-700 dark:text-blue-300',
    bgClass: 'bg-blue-50 dark:bg-blue-900/20',
  },
  completed: {
    icon: CheckCircle,
    iconClass: 'text-green-500',
    textClass: 'text-green-700 dark:text-green-300',
    bgClass: 'bg-green-50 dark:bg-green-900/20',
  },
  failed: {
    icon: XCircle,
    iconClass: 'text-red-500',
    textClass: 'text-red-700 dark:text-red-300',
    bgClass: 'bg-red-50 dark:bg-red-900/20',
  },
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

export default function TodoList({ todos, title = 'Todo List' }: TodoListProps) {
  const completedCount = todos.filter(t => t.status === 'completed').length
  const inProgressCount = todos.filter(t => t.status === 'in_progress').length
  const failedCount = todos.filter(t => t.status === 'failed').length

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-200 flex items-center gap-1.5">
          <CheckCircle size={14} className="text-green-500" />
          {title}
        </h3>
        <div className="flex items-center gap-2 text-xs">
          {completedCount > 0 && (
            <span className="text-green-600 dark:text-green-400">{completedCount} 完成</span>
          )}
          {inProgressCount > 0 && (
            <span className="text-blue-600 dark:text-blue-400">{inProgressCount} 进行中</span>
          )}
          {failedCount > 0 && (
            <span className="text-red-600 dark:text-red-400">{failedCount} 失败</span>
          )}
        </div>
      </div>

      <div className="space-y-1.5">
        {todos.length === 0 ? (
          <div className="text-xs text-gray-400 dark:text-gray-500 py-2 text-center">
            暂无任务
          </div>
        ) : (
          todos.map((todo, index) => {
            const config = statusConfig[todo.status]
            const Icon = config.icon

            return (
              <div
                key={todo.id}
                className={`flex items-start gap-2 p-2 rounded-lg ${config.bgClass} transition-all duration-200`}
              >
                <div className="flex-shrink-0 mt-0.5">
                  <Icon size={14} className={config.iconClass} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className={`text-sm ${config.textClass}`}>
                    {todo.content}
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-xs text-gray-400 dark:text-gray-500">
                    {todo.agent && (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-white dark:bg-slate-700 rounded border border-gray-200 dark:border-slate-600">
                        {todo.agent}
                      </span>
                    )}
                    {todo.startTime && (
                      <span>{formatDuration(todo.startTime, todo.endTime)}</span>
                    )}
                  </div>
                </div>
                {todo.status === 'completed' && (
                  <ChevronRight size={14} className="text-green-400" />
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
