'use client'

import Image from 'next/image'
import { Menu } from 'lucide-react'
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
        <Image
          src="/deepclaw-logo-text.png"
          alt="DeepClaw"
          width={174}
          height={40}
          priority
          className="h-7 w-auto md:h-8"
        />
      </div>
    </nav>
  )
}
