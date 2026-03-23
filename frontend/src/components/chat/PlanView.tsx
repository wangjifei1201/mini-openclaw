'use client'

import { ClipboardList, ChevronRight, Zap, CheckCircle } from 'lucide-react'

interface PlanStep {
  content: string
  agent?: string
  tools?: string[]
  acceptance_criteria?: string
}

interface PlanViewProps {
  plan: {
    title: string
    description: string
    steps: PlanStep[]
  }
}

export default function PlanView({ plan }: PlanViewProps) {
  return (
    <div className="rounded-lg border border-indigo-200 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-900/20 p-3 mb-2">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="w-6 h-6 rounded-md bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center">
          <ClipboardList size={13} className="text-indigo-600 dark:text-indigo-400" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-indigo-800 dark:text-indigo-200 truncate">{plan.title}</h4>
          {plan.description && (
            <p className="text-[11px] text-indigo-500 dark:text-indigo-400 truncate">{plan.description}</p>
          )}
        </div>
        <span className="text-[10px] text-indigo-400 dark:text-indigo-500 flex-shrink-0">
          {plan.steps.length} 步骤
        </span>
      </div>

      {/* Steps */}
      <div className="space-y-1.5">
        {plan.steps.map((step, index) => (
          <div
            key={index}
            className="flex items-start gap-2 bg-white dark:bg-slate-800 rounded-lg px-2.5 py-2 border border-indigo-100 dark:border-slate-700"
          >
            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center text-[10px] font-semibold text-indigo-600 dark:text-indigo-400 mt-0.5">
              {index + 1}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-gray-700 dark:text-gray-200 leading-relaxed">{step.content}</p>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                {step.agent && (
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-indigo-50 dark:bg-indigo-900/30 rounded text-[10px] text-indigo-600 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-800">
                    <Zap size={9} />
                    {step.agent}
                  </span>
                )}
                {step.tools && step.tools.length > 0 && (
                  <span className="text-[10px] text-gray-400 dark:text-gray-500">
                    {step.tools.join(', ')}
                  </span>
                )}
                {step.acceptance_criteria && (
                  <span className="inline-flex items-center gap-0.5 text-[10px] text-green-600 dark:text-green-400">
                    <CheckCircle size={9} />
                    {step.acceptance_criteria}
                  </span>
                )}
              </div>
            </div>
            <ChevronRight size={12} className="text-indigo-300 dark:text-indigo-600 flex-shrink-0 mt-1" />
          </div>
        ))}
      </div>
    </div>
  )
}
