'use client'

import { ExternalLink } from 'lucide-react'

export default function Navbar() {
  return (
    <nav className="h-14 frosted-glass border-b border-apple-border flex items-center justify-between px-6 fixed top-0 left-0 right-0 z-50">
      {/* 左侧 Logo */}
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 bg-klein-blue rounded-lg flex items-center justify-center">
          <span className="text-white font-bold text-sm">M</span>
        </div>
        <span className="font-semibold text-lg text-gray-800">mini OpenClaw</span>
      </div>
      
      {/* 右侧链接 */}
      <a
        href="https://fufan.ai"
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
