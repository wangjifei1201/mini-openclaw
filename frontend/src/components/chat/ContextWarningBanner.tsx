'use client'

import { AlertTriangle, X } from 'lucide-react'

interface ContextWarningBannerProps {
  status: string
  usageRatio: number
  message: string
  onDismiss: () => void
}

export default function ContextWarningBanner({ status, usageRatio, message, onDismiss }: ContextWarningBannerProps) {
  const isCritical = status === 'critical'
  const percentage = Math.round(usageRatio * 100)

  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs ${
      isCritical
        ? 'bg-red-50 border border-red-200 text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300'
        : 'bg-amber-50 border border-amber-200 text-amber-700 dark:bg-amber-900/20 dark:border-amber-800 dark:text-amber-300'
    }`}>
      <AlertTriangle size={14} className="flex-shrink-0" />
      <div className="flex-1 flex items-center gap-2">
        <span>{message}</span>
        <div className="hidden sm:flex items-center gap-1">
          <div className="w-16 h-1.5 bg-gray-200 dark:bg-slate-600 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${isCritical ? 'bg-red-500' : 'bg-amber-500'}`}
              style={{ width: `${percentage}%` }}
            />
          </div>
          <span className="text-[10px] opacity-70">{percentage}%</span>
        </div>
      </div>
      <button
        onClick={onDismiss}
        className="p-0.5 rounded hover:bg-black/10 dark:hover:bg-white/10 transition-colors flex-shrink-0"
      >
        <X size={12} />
      </button>
    </div>
  )
}
