'use client'

import { useState } from 'react'
import { X, Users, Clock, Activity, CheckCircle } from 'lucide-react'
import TaskStats, { type TaskStatsData } from './TaskStats'
import TodoList, { type TodoItem } from './TodoList'
import SubTaskCard, { type SubTaskData } from './SubTaskCard'

export interface TaskPanelData {
  taskId: string
  message: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  stats: TaskStatsData
  todos: TodoItem[]
  subtasks: SubTaskData[]
  agentStatus: Record<string, 'idle' | 'processing' | 'completed' | 'failed'>
}

interface TaskPanelProps {
  task: TaskPanelData | null
  onClose?: () => void
}

const taskStatusConfig: Record<string, { label: string; class: string }> = {
  pending: { label: '等待中', class: 'bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-gray-400' },
  processing: { label: '执行中', class: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  completed: { label: '已完成', class: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  failed: { label: '失败', class: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
}

export default function TaskPanel({ task, onClose }: TaskPanelProps) {
  const [expandedSubtask, setExpandedSubtask] = useState<string | null>(null)

  if (!task) {
    return null
  }

  const toggleSubtask = (id: string) => {
    setExpandedSubtask(prev => prev === id ? null : id)
  }

  const statusInfo = taskStatusConfig[task.status] ?? taskStatusConfig.pending

  return (
    <div className="h-full flex flex-col bg-gray-50/80 dark:bg-slate-900/80 border-l border-gray-200 dark:border-slate-700">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-white dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
            <Users size={13} className="text-purple-600 dark:text-purple-400" />
          </div>
          <span className="text-sm font-medium text-gray-800 dark:text-gray-200">任务面板</span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${statusInfo.class}`}>
            {statusInfo.label}
          </span>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
          >
            <X size={14} className="text-gray-400 dark:text-gray-500" />
          </button>
        )}
      </div>

      {/* 任务描述 */}
      <div className="px-4 py-2 bg-white dark:bg-slate-800 border-b border-gray-100 dark:border-slate-700">
        <p className="text-xs text-gray-600 dark:text-gray-300 leading-relaxed line-clamp-2">
          {task.message}
        </p>
        <div className="flex items-center gap-1.5 mt-1 text-[10px] text-gray-400 dark:text-gray-500">
          <Clock size={9} />
          <span>{task.taskId.slice(0, 12)}</span>
        </div>
      </div>

      {/* 平铺内容区域 */}
      <div className="flex-1 overflow-y-auto">
        {/* Todo 列表 — 放在最上面 */}
        <div className="px-4 py-3 border-b border-gray-100 dark:border-slate-700">
          <TodoList todos={task.todos} />
        </div>

        {/* 执行统计 */}
        <div className="px-4 py-3 border-b border-gray-100 dark:border-slate-700">
          <div className="flex items-center gap-1.5 mb-2">
            <Activity size={12} className="text-gray-400 dark:text-gray-500" />
            <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">统计</span>
          </div>
          <TaskStats stats={task.stats} />
        </div>

        {/* 子任务列表 */}
        {task.subtasks.length > 0 && (
          <div className="px-4 py-3">
            <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700 p-3 space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">子任务</h3>
                <span className="text-[10px] text-gray-400 dark:text-gray-500">
                  {task.subtasks.filter(s => s.status === 'finished').length} / {task.subtasks.length}
                </span>
              </div>
              <div className="space-y-2">
                {task.subtasks.map(subtask => (
                  <SubTaskCard
                    key={subtask.id}
                    subtask={subtask}
                    isExpanded={expandedSubtask === subtask.id}
                    onToggle={() => toggleSubtask(subtask.id)}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
