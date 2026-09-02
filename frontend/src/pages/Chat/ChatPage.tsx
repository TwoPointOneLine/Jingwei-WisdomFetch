import ChatPanel from './ChatPanel'
import Sidebar from './Sidebar'
import ChatHeader from './ChatHeader'
import type { ThemeMode } from './SidebarFooter'
import type { ChatMessage, ChatSession } from '../../types'

interface ChatPageProps {
  collapsed: boolean
  sessions: ChatSession[]
  activeSessionId: string | null
  activeView: 'chat' | 'import'
  theme: ThemeMode
  isLoggedIn: boolean
  username: string
  sending: boolean
  activeSession: ChatSession | null
  onToggle: () => void
  onNewChat: () => void
  onSelectSession: (id: string) => void
  onRenameSession: (id: string, newTitle: string) => void
  onDeleteSession: (id: string) => void
  onSwitchView: (view: 'chat' | 'import') => void
  onThemeChange: (theme: ThemeMode) => void
  onLogin: () => void
  onLogout: () => void
  onUpload: () => void
  onMessagesChange: (messages: ChatMessage[]) => void
  onSendingChange: (sending: boolean) => void
}

/**
 * 对话界面（独立页面组件）：左侧菜单栏（Sidebar）+ 对话内容，整体作为一个完整界面。
 * 与知识库管理页面（KnowledgePage）通过按钮互相跳转，切换时左侧菜单不再混入知识库界面。
 */
export default function ChatPage({
  collapsed,
  sessions,
  activeSessionId,
  activeView,
  theme,
  isLoggedIn,
  username,
  sending,
  activeSession,
  onToggle,
  onNewChat,
  onSelectSession,
  onRenameSession,
  onDeleteSession,
  onSwitchView,
  onThemeChange,
  onLogin,
  onLogout,
  onUpload,
  onMessagesChange,
  onSendingChange,
}: ChatPageProps) {
  return (
    <div className="app">
      <Sidebar
        collapsed={collapsed}
        sessions={sessions}
        activeSessionId={activeSessionId}
        activeView={activeView}
        theme={theme}
        isLoggedIn={isLoggedIn}
        username={username}
        onToggle={onToggle}
        onNewChat={onNewChat}
        onSelectSession={onSelectSession}
        onRenameSession={onRenameSession}
        onDeleteSession={onDeleteSession}
        onSwitchView={onSwitchView}
        onThemeChange={onThemeChange}
        onLogin={onLogin}
        onLogout={onLogout}
      />

      <main className="main">
        {activeSession ? (
          <>
            <ChatHeader
              title={activeSession.title || '新对话'}
              meta={
                activeSession.messages.length > 0
                  ? `${activeSession.messages.length} 条消息`
                  : '欢迎开始新的对话'
              }
              onUpload={onUpload}
            />
            <ChatPanel
              session={activeSession}
              sending={sending}
              username={username}
              onChange={onMessagesChange}
              onSendingChange={onSendingChange}
            />
          </>
        ) : (
          <>
            <ChatHeader
              title="欢迎使用精卫"
              meta="开始新的对话"
              showUpload={false}
              onUpload={onUpload}
            />
            <div className="chat-empty" />
          </>
        )}
      </main>
    </div>
  )
}
