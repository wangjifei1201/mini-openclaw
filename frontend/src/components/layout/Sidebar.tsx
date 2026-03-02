'use client'

import { useState, useEffect } from 'react'
import { 
  MessageSquare, 
  Brain, 
  Sparkles, 
  Plus, 
  Trash2, 
  Wrench,
  Database,
  FileText,
  Settings,
  User,
  BookOpen,
  Shield
} from 'lucide-react'
import { useApp } from '@/lib/store'
import { getSessionTokens, getSkills } from '@/lib/api'

type TabType = 'chat' | 'memory' | 'skills'

interface Skill {
  name: string
  description: string
  location: string
}

export default function Sidebar() {
  const {
    sessions,
    currentSessionId,
    selectSession,
    newSession,
    removeSession,
    isCompressing,
    ragMode,
    compress,
    toggleRAGMode,
  } = useApp()
  
  const [activeTab, setActiveTab] = useState<TabType>('chat')
  const [tokenInfo, setTokenInfo] = useState({ system: 0, message: 0, total: 0 })
  const [skills, setSkills] = useState<Skill[]>([])
  const [skillsLoading, setSkillsLoading] = useState(false)
  
  // 加载 Token 信息
  useEffect(() => {
    if (currentSessionId) {
      getSessionTokens(currentSessionId)
        .then(data => {
          setTokenInfo({
            system: data.system_tokens,
            message: data.message_tokens,
            total: data.total_tokens,
          })
        })
        .catch(console.error)
    }
  }, [currentSessionId])
  
  // 切换到技能标签时加载技能列表
  useEffect(() => {
    if (activeTab === 'skills' && skills.length === 0) {
      setSkillsLoading(true)
      getSkills()
        .then(data => {
          setSkills(data.skills || [])
        })
        .catch(console.error)
        .finally(() => setSkillsLoading(false))
    }
  }, [activeTab])
  
  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    if (confirm('确定要删除这个会话吗？')) {
      removeSession(id)
    }
  }
  
  const handleCompress = () => {
    if (confirm('确定要压缩对话历史吗？这将归档前50%的消息。')) {
      compress()
    }
  }
  
  return (
    <div className="h-full flex flex-col bg-white border-r border-apple-border">
      {/* 导航标签 */}
      <div className="flex border-b border-apple-border">
        <button
          onClick={() => setActiveTab('chat')}
          className={`flex-1 py-3 text-sm font-medium transition-colors ${
            activeTab === 'chat'
              ? 'text-klein-blue border-b-2 border-klein-blue'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <MessageSquare size={16} className="inline mr-1" />
          对话
        </button>
        <button
          onClick={() => setActiveTab('memory')}
          className={`flex-1 py-3 text-sm font-medium transition-colors ${
            activeTab === 'memory'
              ? 'text-klein-blue border-b-2 border-klein-blue'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <Brain size={16} className="inline mr-1" />
          记忆
        </button>
        <button
          onClick={() => setActiveTab('skills')}
          className={`flex-1 py-3 text-sm font-medium transition-colors ${
            activeTab === 'skills'
              ? 'text-klein-blue border-b-2 border-klein-blue'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <Sparkles size={16} className="inline mr-1" />
          技能
        </button>
      </div>
      
      {/* 内容区域 */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'chat' && (
          <div className="p-3">
            {/* 新建会话按钮 */}
            <button
              onClick={newSession}
              className="w-full flex items-center justify-center gap-2 py-2 px-4 bg-klein-blue text-white rounded-lg hover:opacity-90 transition-opacity mb-3"
            >
              <Plus size={18} />
              新对话
            </button>
            
            {/* 会话列表 */}
            <div className="space-y-1">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => selectSession(session.id)}
                  className={`group flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                    currentSessionId === session.id
                      ? 'bg-blue-50 border border-blue-200'
                      : 'hover:bg-gray-50'
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-800 truncate">
                      {session.title}
                    </div>
                    <div className="text-xs text-gray-400">
                      {session.message_count} 条消息
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, session.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-all"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              
              {sessions.length === 0 && (
                <div className="text-center text-gray-400 py-8 text-sm">
                  暂无会话，点击上方按钮开始
                </div>
              )}
            </div>
          </div>
        )}
        
        {activeTab === 'memory' && (
          <div className="p-3">
            {/* System Prompt 区域 */}
            <div className="text-sm text-gray-500 mb-2 flex items-center gap-1">
              <Settings size={13} />
              System Prompt
            </div>
            <div className="space-y-1 mb-4">
              <PromptFileItem 
                path="workspace/SOUL.md" 
                label="核心设定" 
                desc="Agent 的灵魂与行为风格"
                icon={<BookOpen size={14} className="text-purple-500" />}
              />
              <PromptFileItem 
                path="workspace/IDENTITY.md" 
                label="自我认知" 
                desc="Agent 的名称与身份设定"
                icon={<Shield size={14} className="text-blue-500" />}
              />
              <PromptFileItem 
                path="workspace/USER.md" 
                label="用户画像" 
                desc="用户个人信息与偏好"
                icon={<User size={14} className="text-green-500" />}
              />
              <PromptFileItem 
                path="workspace/AGENTS.md" 
                label="行为准则" 
                desc="工具使用与记忆操作指南"
                icon={<Wrench size={14} className="text-orange-500" />}
              />
            </div>

            {/* 记忆文件区域 */}
            <div className="text-sm text-gray-500 mb-2 flex items-center gap-1">
              <Brain size={13} />
              记忆文件
            </div>
            <div className="space-y-1">
              <FileItem path="memory/MEMORY.md" label="长期记忆" />
              <FileItem path="SKILLS_SNAPSHOT.md" label="技能快照" />
            </div>
          </div>
        )}
        
        {activeTab === 'skills' && (
          <div className="p-3">
            <div className="text-sm text-gray-500 mb-3">
              可用技能列表 ({skills.length})
            </div>
            {skillsLoading ? (
              <div className="text-center text-gray-400 py-4 text-sm">
                加载中...
              </div>
            ) : (
              <div className="space-y-2">
                {skills.map((skill, index) => (
                  <SkillItem 
                    key={index} 
                    name={skill.name} 
                    description={skill.description}
                    location={skill.location}
                  />
                ))}
                {skills.length === 0 && (
                  <div className="text-center text-gray-400 py-4 text-sm">
                    暂无可用技能
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
      
      {/* 底部工具栏 */}
      <div className="border-t border-apple-border p-3 space-y-2">
        {/* RAG 模式开关 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Database size={14} />
            RAG 模式
          </div>
          <button
            onClick={toggleRAGMode}
            className={`w-10 h-5 rounded-full transition-colors relative ${
              ragMode ? 'bg-klein-blue' : 'bg-gray-300'
            }`}
          >
            <span
              className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform ${
                ragMode ? 'left-5' : 'left-0.5'
              }`}
            />
          </button>
        </div>
        
        {/* 压缩按钮 */}
        <button
          onClick={handleCompress}
          disabled={!currentSessionId || isCompressing}
          className="w-full flex items-center justify-center gap-2 py-2 px-4 text-sm text-gray-600 border border-apple-border rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Wrench size={14} />
          {isCompressing ? '压缩中...' : '压缩对话'}
        </button>
        
        {/* Token 统计 */}
        <div className="text-xs text-gray-400 text-center">
          Token: {tokenInfo.total.toLocaleString()} 
          <span className="text-gray-300 mx-1">|</span>
          系统: {tokenInfo.system.toLocaleString()}
          <span className="text-gray-300 mx-1">|</span>
          消息: {tokenInfo.message.toLocaleString()}
        </div>
      </div>
    </div>
  )
}

// 文件项组件
function FileItem({ path, label }: { path: string; label: string }) {
  const { setCurrentFile } = useApp()
  
  return (
    <button
      onClick={() => setCurrentFile(path)}
      className="w-full flex items-center gap-2 p-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition-colors text-left"
    >
      <FileText size={14} className="text-gray-400" />
      {label}
    </button>
  )
}

// System Prompt 文件项组件
function PromptFileItem({ path, label, desc, icon }: { path: string; label: string; desc: string; icon: React.ReactNode }) {
  const { setCurrentFile } = useApp()
  
  return (
    <button
      onClick={() => setCurrentFile(path)}
      className="w-full flex flex-col gap-0.5 p-2 text-left hover:bg-blue-50 rounded-lg transition-colors"
    >
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-sm font-medium text-gray-700">{label}</span>
      </div>
      <div className="text-xs text-gray-400 ml-5">{desc}</div>
    </button>
  )
}

// 技能项组件
function SkillItem({ name, description, location }: { name: string; description: string; location: string }) {
  const { setCurrentFile } = useApp()
  
  // 转换路径格式：./backend/skills/xxx/SKILL.md -> skills/xxx/SKILL.md
  const filePath = location.replace(/^\.\/backend\//, '')
  
  return (
    <button
      onClick={() => setCurrentFile(filePath)}
      className="w-full flex flex-col gap-1 p-2 text-left hover:bg-gray-50 rounded-lg transition-colors"
    >
      <div className="flex items-center gap-2">
        <Sparkles size={14} className="text-vibrant-orange flex-shrink-0" />
        <span className="text-sm font-medium text-gray-700 truncate">{name}</span>
      </div>
      <div className="text-xs text-gray-400 line-clamp-2 ml-5">
        {description}
      </div>
    </button>
  )
}
