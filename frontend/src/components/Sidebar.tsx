import type { ChatSession } from '../types'
import SessionList from './SessionList'
import SidebarFooter, { type ThemeMode } from './SidebarFooter'

interface SidebarProps {
  collapsed: boolean
  sessions: ChatSession[]
  activeSessionId: string | null
  activeView: 'chat' | 'import'
  theme: ThemeMode
  isLoggedIn: boolean
  username: string
  onToggle: () => void
  onNewChat: () => void
  onSelectSession: (id: string) => void
  onRenameSession: (id: string, newTitle: string) => void
  onDeleteSession: (id: string) => void
  onSwitchView: (view: 'chat' | 'import') => void
  onThemeChange: (theme: ThemeMode) => void
  onLogin: () => void
  onLogout: () => void
}

export default function Sidebar({
  collapsed,
  sessions,
  activeSessionId,
  activeView,
  theme,
  isLoggedIn,
  username,
  onToggle,
  onNewChat,
  onSelectSession,
  onRenameSession,
  onDeleteSession,
  onSwitchView,
  onThemeChange,
  onLogin,
  onLogout,
}: SidebarProps) {
  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}`}>
      {/* 顶部：折叠按钮 + 标题 */}
      <div className="sidebar-head">
        {!collapsed && (
          <div className="brand">
            <span className="brand-logo">智</span>
            <span className="brand-name">掌柜智库</span>
          </div>
        )}
        <button className="icon-btn" onClick={onToggle} title={collapsed ? '展开菜单' : '折叠菜单'}>
          {collapsed ? '»' : '«'}
        </button>
      </div>

      {!collapsed && (
        <>
          {/* 新建对话 */}
          <button className="new-chat-btn" onClick={onNewChat}>
            <span>＋</span> 新建对话
          </button>

          {/* 对话历史（仅登录后显示） */}
          {isLoggedIn && (
            <div className="sidebar-section">
              <div className="sidebar-label">对话历史</div>
              <SessionList
                sessions={sessions}
                activeSessionId={activeSessionId}
                activeView={activeView}
                onSelect={onSelectSession}
                onRename={onRenameSession}
                onDelete={onDeleteSession}
              />
            </div>
          )}

          {/* 底部功能区（独立组件：知识库管理 + 设置/主题切换 + 登录/用户信息） */}
          <SidebarFooter
            activeView={activeView}
            theme={theme}
            isLoggedIn={isLoggedIn}
            username={username}
            onSwitchView={onSwitchView}
            onThemeChange={onThemeChange}
            onLogin={onLogin}
            onLogout={onLogout}
          />
        </>
      )}
    </aside>
  )
}
