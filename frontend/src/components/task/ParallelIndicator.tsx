'use client'

import { GitBranch, ArrowRight } from 'lucide-react'

interface ParallelGroup {
  indices: number[]
  type: string  // "parallel" | "sequential"
  agents: string[]
}

interface ParallelIndicatorProps {
  groups: ParallelGroup[]
  activeGroup?: number[]
  totalTodos: number
}

export default function ParallelIndicator({ groups, activeGroup, totalTodos }: ParallelIndicatorProps) {
  const parallelCount = groups.filter(g => g.type === 'parallel').length

  if (groups.length === 0) return null

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide flex items-center gap-1.5">
          <GitBranch size={12} className="text-cyan-500" />
          执行分组
        </h3>
        <span className="text-[10px] text-gray-400 dark:text-gray-500">
          {parallelCount > 0 ? `${parallelCount} 组可并行` : '全部串行'}
        </span>
      </div>

      <div className="flex items-center gap-1 flex-wrap">
        {groups.map((group, gIdx) => {
          const isActive = activeGroup && group.indices.some(i => activeGroup.includes(i))
          const isParallel = group.type === 'parallel'

          return (
            <div key={gIdx} className="flex items-center gap-1">
              {gIdx > 0 && (
                <ArrowRight size={10} className="text-gray-300 dark:text-gray-600 flex-shrink-0" />
              )}
              <div
                className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium border transition-all ${
                  isActive
                    ? 'bg-cyan-50 border-cyan-300 text-cyan-700 dark:bg-cyan-900/30 dark:border-cyan-700 dark:text-cyan-300 ring-1 ring-cyan-200 dark:ring-cyan-800'
                    : isParallel
                    ? 'bg-cyan-50 border-cyan-200 text-cyan-600 dark:bg-cyan-900/20 dark:border-cyan-800 dark:text-cyan-400'
                    : 'bg-gray-50 border-gray-200 text-gray-500 dark:bg-slate-800 dark:border-slate-600 dark:text-gray-400'
                }`}
              >
                {isParallel && <GitBranch size={9} />}
                <span>
                  {group.indices.map(i => `T${i + 1}`).join(isParallel ? ' || ' : ' -> ')}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
