'use client'

import { useState } from 'react'
import { MessageSquare, ListChecks } from 'lucide-react'
import { useApp } from '@/lib/store'
import type { InteractiveCard as InteractiveCardType } from '@/lib/api'

interface InteractiveCardProps {
  card: InteractiveCardType
  disabled?: boolean
}

export default function InteractiveCard({ card, disabled = false }: InteractiveCardProps) {
  const { sendMessage, isStreaming, currentSessionId } = useApp()
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const isChoice = card.type === 'choice'
  const isDisabled = disabled || isSubmitting || isStreaming || !currentSessionId || selectedOptionId !== null

  const handleClick = async (optionId: string, prompt: string) => {
    if (isDisabled || !prompt.trim()) return
    setSelectedOptionId(optionId)
    setIsSubmitting(true)
    try {
      await sendMessage(prompt)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mt-3 rounded-xl border border-apple-border bg-gray-50 p-3">
      <div className="flex items-start gap-2">
        <div className="mt-0.5 text-klein-blue">
          {isChoice ? <ListChecks size={16} /> : <MessageSquare size={16} />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-gray-800">{card.title}</div>
          {card.description && (
            <div className="mt-1 text-xs text-gray-500">{card.description}</div>
          )}
          <div className={isChoice ? 'mt-3 space-y-2' : 'mt-3 flex flex-wrap gap-2'}>
            {card.options.map(option => {
              const selected = selectedOptionId === option.id
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => handleClick(option.id, option.prompt)}
                  disabled={isDisabled}
                  className={
                    isChoice
                      ? `block w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                          selected
                            ? 'border-klein-blue bg-klein-blue/10 text-klein-blue'
                            : 'border-gray-200 bg-white text-gray-700 hover:border-klein-blue/50 hover:text-klein-blue'
                        }`
                      : `rounded-full border px-3 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                          selected
                            ? 'border-klein-blue bg-klein-blue text-white'
                            : 'border-gray-200 bg-white text-gray-700 hover:border-klein-blue/50 hover:text-klein-blue'
                        }`
                  }
                >
                  {option.label}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
