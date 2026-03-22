'use client'

import { ExternalLink, Menu, Sun, Moon } from 'lucide-react'
import { useApp } from '@/lib/store'

export default function Navbar() {
  const { isMobileSidebarOpen, setIsMobileSidebarOpen, theme, toggleTheme } = useApp()
  
  return (
    <nav className="h-14 frosted-glass border-b border-apple-border flex items-center justify-between px-4 md:px-6 fixed top-0 left-0 right-0 z-50">
      {/* 左侧 Logo 和移动端菜单 */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setIsMobileSidebarOpen(!isMobileSidebarOpen)}
          className="md:hidden p-2 -ml-2 text-gray-600 dark:text-gray-300 hover:text-klein-blue transition-colors"
        >
          <Menu size={20} />
        </button>
        <div className="w-8 h-8 bg-klein-blue rounded-lg flex items-center justify-center">
          <span className="text-white font-bold text-sm">O</span>
        </div>
        <span className="font-semibold text-lg text-gray-800 dark:text-gray-100 hidden sm:block">Omin OpenClaw</span>
        <span className="font-semibold text-base text-gray-800 dark:text-gray-100 sm:hidden">OpenClaw</span>
      </div>
      
      {/* 右侧主题切换 + 链接 */}
      <div className="flex items-center gap-3">
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:text-klein-blue dark:hover:text-blue-400 hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
          title={theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'}
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <a
          href="https://github.com/wangjifei1201/mini-openclaw"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-sm text-gray-600 dark:text-gray-400 hover:text-klein-blue dark:hover:text-blue-400 transition-colors"
        >
          wangjifei
          <ExternalLink size={14} />
        </a>
      </div>
    </nav>
  )
}
