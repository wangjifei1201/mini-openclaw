'use client'

import { useCallback } from 'react'
import { useApp } from '@/lib/store'
import Navbar from '@/components/layout/Navbar'
import Sidebar from '@/components/layout/Sidebar'
import ResizeHandle from '@/components/layout/ResizeHandle'
import ChatPanel from '@/components/chat/ChatPanel'
import InspectorPanel from '@/components/editor/InspectorPanel'

export default function Home() {
  const {
    sidebarWidth,
    setSidebarWidth,
    inspectorWidth,
    setInspectorWidth,
    currentFile,
  } = useApp()
  
  // 处理左侧边栏拖拽
  const handleSidebarResize = useCallback((delta: number) => {
    setSidebarWidth(Math.max(200, Math.min(400, sidebarWidth + delta)))
  }, [sidebarWidth, setSidebarWidth])
  
  // 处理右侧检查器拖拽
  const handleInspectorResize = useCallback((delta: number) => {
    setInspectorWidth(Math.max(300, Math.min(600, inspectorWidth + delta)))
  }, [inspectorWidth, setInspectorWidth])
  
  return (
    <div className="h-screen flex flex-col">
      {/* 顶部导航栏 */}
      <Navbar />
      
      {/* 主内容区 */}
      <div className="flex-1 flex pt-14 overflow-hidden">
        {/* 左侧边栏 */}
        <div style={{ width: sidebarWidth }} className="flex-shrink-0">
          <Sidebar />
        </div>
        
        {/* 左侧拖拽条 */}
        <ResizeHandle onResize={handleSidebarResize} direction="right" />
        
        {/* 中间聊天区 */}
        <div className="flex-1 min-w-0">
          <ChatPanel />
        </div>
        
        {/* 右侧检查器（有文件时显示） */}
        {currentFile && (
          <>
            <ResizeHandle onResize={handleInspectorResize} direction="left" />
            <div style={{ width: inspectorWidth }} className="flex-shrink-0">
              <InspectorPanel />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
