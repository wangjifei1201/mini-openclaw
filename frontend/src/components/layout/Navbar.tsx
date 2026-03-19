'use client'

import { ExternalLink, Menu } from 'lucide-react'
import { useApp } from '@/lib/store'

export default function Navbar() {
  const { isMobileSidebarOpen, setIsMobileSidebarOpen } = useApp()
  
  return (
    <nav className="h-14 frosted-glass border-b border-apple-border flex items-center justify-between px-4 md:px-6 fixed top-0 left-0 right-0 z-50">
      {/* 左侧 Logo 和移动端菜单 */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setIsMobileSidebarOpen(!isMobileSidebarOpen)}
          className="md:hidden p-2 -ml-2 text-gray-600 hover:text-klein-blue transition-colors"
        >
          <Menu size={20} />
        </button>
        <div className="w-8 h-8 bg-klein-blue rounded-lg flex items-center justify-center">
          <span className="text-white font-bold text-sm">M</span>
        </div>
        <span className="font-semibold text-lg text-gray-800 hidden sm:block">mini OpenClaw</span>
        <span className="font-semibold text-base text-gray-800 sm:hidden">OpenClaw</span>
      </div>
      
      {/* 右侧链接 */}
      <a
        href="https://github.com/wangjifei1201/mini-openclaw"
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1 text-sm text-gray-600 hover:text-klein-blue transition-colors"
      >
        wangjifei
        <ExternalLink size={14} />
      </a>
    </nav>
  )
}
