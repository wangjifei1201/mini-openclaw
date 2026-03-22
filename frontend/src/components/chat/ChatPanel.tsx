'use client'

import { useRef, useEffect } from 'react'
import { useApp } from '@/lib/store'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'

export default function ChatPanel() {
  const { messages, currentSessionId } = useApp()
  const bottomRef = useRef<HTMLDivElement>(null)
  
  // 自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  return (
    <div className="h-full flex flex-col bg-apple-gray">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-3 md:p-4">
        {!currentSessionId ? (
          <div className="h-full flex items-center justify-center text-gray-400 dark:text-gray-500">
            <div className="text-center px-4">
              <div className="text-4xl md:text-6xl mb-4">🧠</div>
              <div className="text-lg md:text-xl font-medium mb-2">欢迎使用 Omin-OpenClaw</div>
              <div className="text-sm md:text-base">你的 24/7 智能思考助手已上线，选个话题聊聊，或开启全新对话探索</div>
            </div>
          </div>
        ) : messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-gray-400 dark:text-gray-500">
            <div className="text-center px-4">
              <div className="text-3xl md:text-4xl mb-4">💬</div>
              <div className="text-sm md:text-base">发送消息开始对话</div>
            </div>
          </div>
        ) : (
          <div className="space-y-3 md:space-y-4 max-w-4xl mx-auto">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
      
      {/* 输入框 */}
      <div className="border-t border-apple-border bg-white dark:bg-slate-800 p-3 md:p-4">
        <div className="max-w-4xl mx-auto">
          <ChatInput />
        </div>
      </div>
    </div>
  )
}
