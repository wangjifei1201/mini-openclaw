'use client'

import { useCallback } from 'react'
import { useApp } from '@/lib/store'
import Navbar from '@/components/layout/Navbar'
import Sidebar from '@/components/layout/Sidebar'
import ResizeHandle from '@/components/layout/ResizeHandle'
import ChatPanel from '@/components/chat/ChatPanel'
import InspectorPanel from '@/components/editor/InspectorPanel'
import TaskPanel from '@/components/task/TaskPanel'

export default function Home() {
  const {
    sidebarWidth,
    setSidebarWidth,
    inspectorWidth,
    setInspectorWidth,
    taskPanelWidth,
    setTaskPanelWidth,
    currentFile,
    isMobileSidebarOpen,
    setIsMobileSidebarOpen,
    multiAgentMode,
    currentTask,
    clearCurrentTask,
  } = useApp()
  
  // 处理左侧边栏拖拽 - 最小200px，最大半屏
  const handleSidebarResize = useCallback((delta: number) => {
    const maxWidth = typeof window !== 'undefined' ? Math.floor(window.innerWidth / 2) : 600
    setSidebarWidth(Math.max(200, Math.min(maxWidth, sidebarWidth + delta)))
  }, [sidebarWidth, setSidebarWidth])
  
  // 处理右侧检查器拖拽
  const handleInspectorResize = useCallback((delta: number) => {
    setInspectorWidth(Math.max(300, Math.min(600, inspectorWidth + delta)))
  }, [inspectorWidth, setInspectorWidth])
  
  // 处理任务面板拖拽
  const handleTaskPanelResize = useCallback((delta: number) => {
    setTaskPanelWidth(Math.max(280, Math.min(500, taskPanelWidth + delta)))
  }, [taskPanelWidth, setTaskPanelWidth])
  
  // 是否显示任务面板：多Agent模式开启且有任务
  const showTaskPanel = multiAgentMode && currentTask
  
  return (
    <div className="h-screen flex flex-col">
      {/* 顶部导航栏 */}
      <Navbar />
      
      {/* 主内容区 */}
      <div className="flex-1 flex pt-14 overflow-hidden">
        {/* 移动端侧边栏遮罩 */}
        {isMobileSidebarOpen && (
          <div
            className="fixed inset-0 bg-black/50 z-40 md:hidden"
            onClick={() => setIsMobileSidebarOpen(false)}
          />
        )}
        
        {/* 左侧边栏 - 桌面版固定，移动版overlay */}
        <div
          className={`${
            isMobileSidebarOpen ? 'fixed left-0 top-14 bottom-0 z-50' : 'hidden'
          } md:block md:relative md:top-0 h-full flex-shrink-0`}
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
        
        {/* 右侧任务面板（多Agent模式） */}
        {showTaskPanel && (
          <>
            <ResizeHandle onResize={handleTaskPanelResize} direction="left" />
            <div style={{ width: taskPanelWidth }} className="flex-shrink-0">
              <TaskPanel task={currentTask} onClose={clearCurrentTask} />
            </div>
          </>
        )}
        
        {/* 右侧检查器（有文件时显示） */}
        {currentFile && !showTaskPanel && (
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
