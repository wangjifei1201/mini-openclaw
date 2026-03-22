'use client'

import { useState, useEffect } from 'react'
import { 
  GitBranch, 
  RefreshCw,
  Trash2,
  ChevronRight,
  ChevronDown,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle
} from 'lucide-react'
import { getTasks, getCoordinationSnapshot, clearAllTasks, TaskInfo } from '@/lib/api'

export default function CoordinationPanel() {
  const [tasks, setTasks] = useState<TaskInfo[]>([])
  const [snapshot, setSnapshot] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [expandedTask, setExpandedTask] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'tasks' | 'snapshot'>('tasks')

  // 加载任务列表
  const loadData = async () => {
    setLoading(true)
    try {
      const [tasksRes, snapshotRes] = await Promise.all([
        getTasks(),
        getCoordinationSnapshot()
      ])
      setTasks(Array.isArray(tasksRes.data) ? tasksRes.data : [])
      setSnapshot(snapshotRes.data?.content || '')
    } catch (error) {
      console.error('加载协同数据失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    // 定时刷新
    const interval = setInterval(loadData, 10000)
    return () => clearInterval(interval)
  }, [])

  // 重置任务队列
  const handleClearTasks = async () => {
    if (!confirm('确定要清除所有任务吗？此操作不可恢复。')) return
    setClearing(true)
    try {
      await clearAllTasks()
      setTasks([])
      setExpandedTask(null)
      await loadData()
    } catch (error) {
      console.error('清除任务失败:', error)
    } finally {
      setClearing(false)
    }
  }

  // 状态图标
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock size={14} className="text-yellow-500" />
      case 'processing':
        return <Loader2 size={14} className="text-blue-500 animate-spin" />
      case 'finished':
        return <CheckCircle size={14} className="text-green-500" />
      case 'failed':
        return <XCircle size={14} className="text-red-500" />
      default:
        return <AlertCircle size={14} className="text-gray-400" />
    }
  }

  // 状态颜色
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'text-yellow-600 bg-yellow-50 dark:text-yellow-400 dark:bg-yellow-900/20'
      case 'processing':
        return 'text-blue-600 bg-blue-50 dark:text-blue-400 dark:bg-blue-900/20'
      case 'finished':
        return 'text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-900/20'
      case 'failed':
        return 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-900/20'
      default:
        return 'text-gray-600 bg-gray-50 dark:text-gray-400 dark:bg-slate-700'
    }
  }

  return (
    <div className="h-full flex flex-col bg-white dark:bg-slate-800">
      {/* 标题栏 */}
      <div className="flex items-center justify-between p-3 border-b border-apple-border">
        <div className="flex items-center gap-2">
          <GitBranch size={16} className="text-klein-blue" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-200">协同管理</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleClearTasks}
            disabled={clearing || tasks.length === 0}
            className="p-1 text-gray-400 dark:text-gray-500 hover:text-red-500 disabled:opacity-30 disabled:hover:text-gray-400 transition-colors"
            title="重置任务队列"
          >
            <Trash2 size={14} className={clearing ? 'animate-pulse' : ''} />
          </button>
          <button
            onClick={loadData}
            disabled={loading}
            className="p-1 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            title="刷新"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* 标签切换 */}
      <div className="flex border-b border-apple-border">
        <button
          onClick={() => setActiveTab('tasks')}
          className={`flex-1 py-2 text-sm font-medium transition-colors ${
            activeTab === 'tasks'
              ? 'text-klein-blue border-b-2 border-klein-blue'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          任务队列
        </button>
        <button
          onClick={() => setActiveTab('snapshot')}
          className={`flex-1 py-2 text-sm font-medium transition-colors ${
            activeTab === 'snapshot'
              ? 'text-klein-blue border-b-2 border-klein-blue'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          状态快照
        </button>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'tasks' && (
          <div className="p-2">
            {loading && tasks.length === 0 ? (
              <div className="text-center text-gray-400 dark:text-gray-500 py-8 text-sm">
                加载中...
              </div>
            ) : (
              <div className="space-y-2">
                {tasks.map((task) => (
                  <div
                    key={task.task_id}
                    className="rounded-lg border border-gray-100 dark:border-slate-700 hover:border-gray-200 dark:hover:border-slate-600 transition-colors"
                  >
                    {/* 任务头部 */}
                    <div
                      className="flex items-center justify-between p-2 cursor-pointer"
                      onClick={() => setExpandedTask(
                        expandedTask === task.task_id ? null : task.task_id
                      )}
                    >
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        {getStatusIcon(task.status)}
                        <span className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate">
                          {task.task_id}
                        </span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${getStatusColor(task.status)}`}>
                          {task.status}
                        </span>
                      </div>
                      <ChevronRight 
                        size={14} 
                        className={`text-gray-400 dark:text-gray-500 transition-transform ${
                          expandedTask === task.task_id ? 'rotate-90' : ''
                        }`} 
                      />
                    </div>
                    
                    {/* 展开详情 */}
                    {expandedTask === task.task_id && (
                      <div className="px-2 pb-2 pt-0 border-t border-gray-50 dark:border-slate-700 text-xs">
                        <div className="py-1.5 text-gray-500 dark:text-gray-400">
                          目标Agent: <span className="text-gray-700 dark:text-gray-200">{task.target_agent}</span>
                        </div>
                        <div className="py-1.5 text-gray-500 dark:text-gray-400">
                          任务类型: <span className="text-gray-700 dark:text-gray-200">{task.task_type}</span>
                        </div>
                        <div className="py-1.5 text-gray-500 dark:text-gray-400">
                          创建时间: <span className="text-gray-700 dark:text-gray-200">{task.created_at}</span>
                        </div>
                        <div className="py-1.5">
                          <div className="text-gray-500 dark:text-gray-400 mb-1">任务内容:</div>
                          <div className="text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-slate-900 p-2 rounded text-sm whitespace-pre-wrap">
                            {task.content || '无内容'}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                
                {tasks.length === 0 && (
                  <div className="text-center text-gray-400 dark:text-gray-500 py-8 text-sm">
                    暂无活跃任务
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'snapshot' && (
          <div className="p-2">
            {snapshot ? (
              <pre className="text-xs text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-slate-900 p-3 rounded-lg whitespace-pre-wrap overflow-x-auto">
                {snapshot}
              </pre>
            ) : (
              <div className="text-center text-gray-400 dark:text-gray-500 py-8 text-sm">
                暂无状态快照
              </div>
            )}
          </div>
        )}
      </div>

      {/* 底部统计 */}
      <div className="p-2 border-t border-apple-border text-xs text-gray-400 dark:text-gray-500">
        {activeTab === 'tasks' ? (
          <>
            共 {tasks.length} 个任务 | 
            <span className="text-yellow-500 ml-1">{tasks.filter(t => t.status === 'pending').length} 待处理</span>
            <span className="text-blue-500 ml-1">{tasks.filter(t => t.status === 'processing').length} 执行中</span>
          </>
        ) : (
          '协同状态快照'
        )}
      </div>
    </div>
  )
}
