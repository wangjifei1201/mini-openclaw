'use client'

import { useState, useEffect } from 'react'
import { 
  Bot, 
  Play, 
  Square, 
  RefreshCw,
  ChevronRight,
  ChevronDown,
  Sparkles,
  Activity,
  Plus,
  X,
  ArrowLeft,
  Shield,
  BookOpen,
  Brain,
  Wrench,
  Trash2
} from 'lucide-react'
import { getAgents, controlAgent, getAgentProfile, createAgent, deleteAgent, AgentInfo, AgentProfileResponse } from '@/lib/api'

type ViewMode = 'list' | 'profile' | 'create'

export default function AgentsPanel() {
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [controlling, setControlling] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('list')

  // Profile 状态
  const [profileData, setProfileData] = useState<AgentProfileResponse | null>(null)
  const [profileLoading, setProfileLoading] = useState(false)
  const [expandedSection, setExpandedSection] = useState<string | null>('identity')

  // 创建表单状态
  const [createForm, setCreateForm] = useState({
    agent_name: '',
    skills: '',
    identity: '',
    soul: '',
  })
  const [creating, setCreating] = useState(false)

  const loadAgents = async () => {
    setLoading(true)
    try {
      const response = await getAgents()
      setAgents(response.data || [])
    } catch (error) {
      console.error('加载Agent列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAgents()
    const interval = setInterval(loadAgents, 5000)
    return () => clearInterval(interval)
  }, [])

  // 查看 Agent Profile
  const handleViewProfile = async (agentName: string) => {
    setProfileLoading(true)
    setViewMode('profile')
    setExpandedSection('identity')
    try {
      const response = await getAgentProfile(agentName)
      setProfileData(response.data)
    } catch (error) {
      console.error('加载Agent画像失败:', error)
    } finally {
      setProfileLoading(false)
    }
  }

  // 控制 Agent 启停
  const handleControl = async (e: React.MouseEvent, agentName: string, action: 'start' | 'stop') => {
    e.stopPropagation()
    setControlling(agentName)
    try {
      await controlAgent(agentName, action)
      await loadAgents()
    } catch (error) {
      console.error('控制Agent失败:', error)
    } finally {
      setControlling(null)
    }
  }

  // 创建 Agent
  const handleCreate = async () => {
    if (!createForm.agent_name.trim()) return
    setCreating(true)
    try {
      const skills = createForm.skills
        .split(/[,，\n]/)
        .map(s => s.trim())
        .filter(Boolean)
      await createAgent({
        agent_name: createForm.agent_name.trim(),
        agent_type: 'domain',
        skills,
        identity: createForm.identity || undefined,
        soul: createForm.soul || undefined,
      })
      setCreateForm({ agent_name: '', skills: '', identity: '', soul: '' })
      setViewMode('list')
      await loadAgents()
    } catch (error) {
      console.error('创建Agent失败:', error)
      alert(`创建失败: ${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setCreating(false)
    }
  }

  // 删除 Agent
  const handleDelete = async (e: React.MouseEvent, agentName: string) => {
    e.stopPropagation()
    if (!confirm(`确定要删除 ${agentName} 吗？`)) return
    try {
      await deleteAgent(agentName)
      await loadAgents()
    } catch (error) {
      console.error('删除Agent失败:', error)
    }
  }

  const getStatusBgColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-green-500'
      case 'busy': return 'bg-blue-500'
      case 'idle': return 'bg-gray-400'
      case 'stopped': return 'bg-red-500'
      default: return 'bg-gray-400'
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'primary': return 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
      case 'coordinator': return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
      case 'domain': return 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300'
      default: return 'bg-gray-100 text-gray-700 dark:bg-slate-700 dark:text-gray-300'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'text-green-500'
      case 'busy': return 'text-blue-500'
      case 'idle': return 'text-gray-400'
      case 'stopped': return 'text-red-500'
      default: return 'text-gray-400'
    }
  }

  // ============ Profile 详情视图 ============
  if (viewMode === 'profile') {
    return (
      <div className="h-full flex flex-col">
        {/* 返回头部 */}
        <div className="flex items-center gap-2 p-3 border-b border-apple-border">
          <button
            onClick={() => { setViewMode('list'); setProfileData(null) }}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
          >
            <ArrowLeft size={14} className="text-gray-500 dark:text-gray-400" />
          </button>
          <Bot size={16} className="text-klein-blue" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate">
            {profileData?.agent_name || '加载中...'}
          </span>
          {profileData && (
            <span className={`text-xs px-1.5 py-0.5 rounded ${getTypeColor(profileData.agent_type)}`}>
              {profileData.agent_type}
            </span>
          )}
        </div>

        {profileLoading ? (
          <div className="flex-1 flex items-center justify-center text-gray-400 dark:text-gray-500 text-sm">
            加载中...
          </div>
        ) : profileData ? (
          <div className="flex-1 overflow-y-auto p-3 space-y-1">
            {/* Agent 基本信息 */}
            <div className="flex items-center gap-2 pb-2 mb-1 border-b border-gray-100 dark:border-slate-700">
              <div className={`w-2 h-2 rounded-full ${getStatusBgColor(profileData.status)}`} />
              <span className={`text-xs ${getStatusColor(profileData.status)}`}>{profileData.status}</span>
              <span className="text-gray-300 dark:text-gray-600">|</span>
              <div className="flex flex-wrap gap-1">
                {profileData.skills.map((skill, i) => (
                  <span key={i} className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-gray-400 rounded">
                    {skill}
                  </span>
                ))}
              </div>
            </div>

            {/* 自我认知 IDENTITY.md */}
            <ProfileSection
              title="自我认知"
              desc="Agent 的名称与身份设定"
              icon={<Shield size={14} className="text-blue-500" />}
              content={profileData.profile.identity}
              isExpanded={expandedSection === 'identity'}
              onToggle={() => setExpandedSection(expandedSection === 'identity' ? null : 'identity')}
            />

            {/* 核心设定 SOUL.md */}
            <ProfileSection
              title="核心设定"
              desc="Agent 的灵魂与行为风格"
              icon={<BookOpen size={14} className="text-purple-500" />}
              content={profileData.profile.soul}
              isExpanded={expandedSection === 'soul'}
              onToggle={() => setExpandedSection(expandedSection === 'soul' ? null : 'soul')}
            />

            {/* 行为准则 AGENTS_LOCAL.md */}
            {profileData.profile.agents_local && (
              <ProfileSection
                title="行为准则"
                desc="工具使用与操作指南"
                icon={<Wrench size={14} className="text-orange-500" />}
                content={profileData.profile.agents_local}
                isExpanded={expandedSection === 'agents_local'}
                onToggle={() => setExpandedSection(expandedSection === 'agents_local' ? null : 'agents_local')}
              />
            )}

            {/* 记忆 MEMORY.md */}
            {profileData.profile.memory && (
              <ProfileSection
                title="记忆"
                desc="Agent 的长期记忆"
                icon={<Brain size={14} className="text-green-500" />}
                content={profileData.profile.memory}
                isExpanded={expandedSection === 'memory'}
                onToggle={() => setExpandedSection(expandedSection === 'memory' ? null : 'memory')}
              />
            )}
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400 dark:text-gray-500 text-sm">
            加载失败
          </div>
        )}
      </div>
    )
  }

  // ============ 创建 Agent 视图 ============
  if (viewMode === 'create') {
    return (
      <div className="h-full flex flex-col">
        <div className="flex items-center gap-2 p-3 border-b border-apple-border">
          <button
            onClick={() => setViewMode('list')}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
          >
            <ArrowLeft size={14} className="text-gray-500 dark:text-gray-400" />
          </button>
          <Plus size={16} className="text-klein-blue" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-200">创建 Agent</span>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {/* 名称 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">名称 *</label>
            <input
              type="text"
              value={createForm.agent_name}
              onChange={(e) => setCreateForm(prev => ({ ...prev, agent_name: e.target.value }))}
              placeholder="如: code_agent"
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-gray-800 dark:text-gray-200 rounded-lg focus:border-klein-blue focus:ring-0 outline-none"
            />
            <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">仅支持字母、数字、下划线、连字符</p>
          </div>

          {/* 技能 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">技能</label>
            <input
              type="text"
              value={createForm.skills}
              onChange={(e) => setCreateForm(prev => ({ ...prev, skills: e.target.value }))}
              placeholder="逗号分隔，如: code_review, testing"
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-gray-800 dark:text-gray-200 rounded-lg focus:border-klein-blue focus:ring-0 outline-none"
            />
          </div>

          {/* 自我认知 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">自我认知 (IDENTITY)</label>
            <textarea
              value={createForm.identity}
              onChange={(e) => setCreateForm(prev => ({ ...prev, identity: e.target.value }))}
              placeholder="Agent 的身份定位和能力描述，留空使用默认模板"
              rows={4}
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-gray-800 dark:text-gray-200 rounded-lg focus:border-klein-blue focus:ring-0 outline-none resize-none"
            />
          </div>

          {/* 核心设定 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">核心设定 (SOUL)</label>
            <textarea
              value={createForm.soul}
              onChange={(e) => setCreateForm(prev => ({ ...prev, soul: e.target.value }))}
              placeholder="Agent 的核心职责和行为准则，留空使用默认模板"
              rows={4}
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-gray-800 dark:text-gray-200 rounded-lg focus:border-klein-blue focus:ring-0 outline-none resize-none"
            />
          </div>
        </div>

        {/* 创建按钮 */}
        <div className="p-3 border-t border-apple-border">
          <button
            onClick={handleCreate}
            disabled={!createForm.agent_name.trim() || creating}
            className="w-full py-2 bg-klein-blue text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
          >
            {creating ? '创建中...' : '创建 Agent'}
          </button>
        </div>
      </div>
    )
  }

  // ============ Agent 列表视图 ============
  return (
    <div className="h-full flex flex-col">
      {/* 标题栏 */}
      <div className="flex items-center justify-between p-3 border-b border-apple-border">
        <div className="flex items-center gap-2">
          <Bot size={16} className="text-klein-blue" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Agents</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setViewMode('create')}
            className="p-1 text-gray-400 dark:text-gray-500 hover:text-klein-blue dark:hover:text-blue-400 transition-colors"
            title="创建Agent"
          >
            <Plus size={14} />
          </button>
          <button
            onClick={loadAgents}
            disabled={loading}
            className="p-1 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            title="刷新"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Agent列表 */}
      <div className="flex-1 overflow-y-auto">
        {loading && agents.length === 0 ? (
          <div className="text-center text-gray-400 dark:text-gray-500 py-8 text-sm">
            加载中...
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {agents.map((agent) => (
              <div
                key={agent.agent_name}
                onClick={() => handleViewProfile(agent.agent_name)}
                className="rounded-lg border border-gray-100 dark:border-slate-700 hover:border-gray-200 dark:hover:border-slate-600 hover:bg-gray-50/50 dark:hover:bg-slate-700/50 transition-colors cursor-pointer"
              >
                <div className="flex items-center justify-between p-2">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${getStatusBgColor(agent.status)}`} />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate">
                      {agent.agent_name}
                    </span>
                    <span className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 ${getTypeColor(agent.agent_type)}`}>
                      {agent.agent_type}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-1">
                    {/* 启停按钮 - 仅 domain */}
                    {agent.agent_type === 'domain' && (
                      <>
                        <button
                          onClick={(e) => handleControl(
                            e, 
                            agent.agent_name, 
                            agent.status === 'stopped' ? 'start' : 'stop'
                          )}
                          disabled={controlling === agent.agent_name}
                          className={`p-1 rounded transition-colors ${
                            agent.status === 'stopped'
                              ? 'text-green-500 hover:bg-green-50 dark:hover:bg-green-900/20'
                              : 'text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20'
                          }`}
                          title={agent.status === 'stopped' ? '启动' : '停止'}
                        >
                          {controlling === agent.agent_name ? (
                            <RefreshCw size={12} className="animate-spin" />
                          ) : agent.status === 'stopped' ? (
                            <Play size={12} />
                          ) : (
                            <Square size={12} />
                          )}
                        </button>
                        <button
                          onClick={(e) => handleDelete(e, agent.agent_name)}
                          className="p-1 rounded text-gray-300 dark:text-gray-600 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                          title="删除"
                        >
                          <Trash2 size={12} />
                        </button>
                      </>
                    )}
                    <ChevronRight size={14} className="text-gray-300 dark:text-gray-600" />
                  </div>
                </div>
                {/* 技能预览 */}
                <div className="px-2 pb-2 flex flex-wrap gap-1">
                  {agent.skills.slice(0, 4).map((skill, i) => (
                    <span key={i} className="text-[10px] px-1.5 py-0.5 bg-gray-50 dark:bg-slate-700 text-gray-400 dark:text-gray-500 rounded">
                      {skill}
                    </span>
                  ))}
                  {agent.skills.length > 4 && (
                    <span className="text-[10px] text-gray-300 dark:text-gray-600">+{agent.skills.length - 4}</span>
                  )}
                </div>
              </div>
            ))}
            
            {agents.length === 0 && (
              <div className="text-center text-gray-400 dark:text-gray-500 py-4 text-sm">
                暂无Agent
              </div>
            )}
          </div>
        )}
      </div>
      
      {/* 底部统计 */}
      <div className="p-2 border-t border-apple-border text-xs text-gray-400 dark:text-gray-500">
        共 {agents.length} 个Agent | {
          agents.filter(a => a.status === 'running' || a.status === 'busy').length
        } 个活跃
      </div>
    </div>
  )
}


// ============ Profile 折叠区域组件 ============
function ProfileSection({
  title,
  desc,
  icon,
  content,
  isExpanded,
  onToggle,
}: {
  title: string
  desc: string
  icon: React.ReactNode
  content: string
  isExpanded: boolean
  onToggle: () => void
}) {
  return (
    <div className="rounded-lg border border-gray-100 dark:border-slate-700 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 p-2.5 text-left hover:bg-gray-50/50 dark:hover:bg-slate-700/50 transition-colors"
      >
        {icon}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-gray-700 dark:text-gray-200">{title}</div>
          <div className="text-[10px] text-gray-400 dark:text-gray-500">{desc}</div>
        </div>
        {isExpanded ? (
          <ChevronDown size={14} className="text-gray-400 dark:text-gray-500 flex-shrink-0" />
        ) : (
          <ChevronRight size={14} className="text-gray-400 dark:text-gray-500 flex-shrink-0" />
        )}
      </button>
      {isExpanded && (
        <div className="border-t border-gray-100 dark:border-slate-700 px-3 py-2">
          {content ? (
            <pre className="text-xs text-gray-600 dark:text-gray-300 whitespace-pre-wrap leading-relaxed font-sans bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-600 rounded-md p-3 max-h-64 overflow-y-auto">
              {content}
            </pre>
          ) : (
            <div className="text-xs text-gray-300 dark:text-gray-600 italic">暂无内容</div>
          )}
        </div>
      )}
    </div>
  )
}
