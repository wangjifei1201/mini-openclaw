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
    isMobileSidebarOpen,
    setIsMobileSidebarOpen,
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
        {/* 移动端侧边栏遮罩 */}
        {isMobileSidebarOpen && (
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden"
            onClick={() => setIsMobileSidebarOpen(false)}
          />
        )}
        
        {/* 左侧边栏 - 桌面版固定，移动版overlay */}
        <div
          className={`${
            isMobileSidebarOpen ? 'fixed left-0 top-14 z-50' : 'hidden'
          } md:block md:relative md:top-0`}
          style={{ width: sidebarWidth }}
        >
          <Sidebar />
        </div>
        
        {/* 桌面版左侧拖拽条 */}
        <div className="hidden md:block">
          <ResizeHandle onResize={handleSidebarResize} direction="right" />
        </div>
        
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
