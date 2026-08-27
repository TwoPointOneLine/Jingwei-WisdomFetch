import { useCallback, useEffect, useState } from 'react'
import ChatPanel from './components/ChatPanel'
import ImportPanel from './components/ImportPanel'
import Sidebar from './components/Sidebar'
import AuthPanel from './components/AuthPanel'
import ChatHeader from './components/ChatHeader'
import type { ThemeMode } from './components/SidebarFooter'
import { authLogout, authMe, claimGuestSessions, genUUID, listSessions } from './api'
import type { ChatMessage, ChatSession } from './types'
import './App.css'

const SESSIONS_KEY = 'jingwei_rag_sessions'
const ACTIVE_KEY = 'jingwei_rag_active'
const THEME_KEY = 'jingwei_rag_theme'
const AUTH_KEY = 'jingwei_rag_user'
const MAX_SESSIONS = 50

type View = 'chat' | 'import'

interface AuthUser {
  username: string
  token: string
  role?: string
}

function loadTheme(): ThemeMode {
  return (localStorage.getItem(THEME_KEY) as ThemeMode) || 'light'
}

function loadUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    if (!raw) return null
    const u = JSON.parse(raw) as AuthUser
    return u && u.token ? u : null
  } catch {
    return null
  }
}

/** 根据消息生成对话标题（用首条用户消息前 N 字） */
function makeTitle(messages: ChatMessage[]): string {
  const first = messages.find((m) => m.role === 'user')
  if (!first) return ''
  const t = first.content.replace(/\s+/g, ' ').trim()
  return t.length > 16 ? `${t.slice(0, 16)}…` : t
}

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw) as ChatSession[]
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

function loadActive(): string | null {
  return localStorage.getItem(ACTIVE_KEY)
}

export default function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [view, setView] = useState<View>('chat')
  const [sessions, setSessions] = useState<ChatSession[]>(loadSessions)
  const [activeId, setActiveId] = useState<string | null>(loadActive)
  const [theme, setTheme] = useState<ThemeMode>(loadTheme)
  const [user, setUser] = useState<AuthUser | null>(loadUser)
  const [showAuth, setShowAuth] = useState(false)
  const [sending, setSending] = useState(false)

  // 登录后校验 token 是否仍有效
  useEffect(() => {
    if (user?.token) {
      authMe(user.token)
        .then((data) => {
          if (data.username !== user.username) handleLogout()
          // FR-AUTH-02：同步角色
          else if (data.role && data.role !== user.role) {
            const updated = { ...user, role: data.role }
            setUser(updated)
            localStorage.setItem(AUTH_KEY, JSON.stringify(updated))
          }
        })
        .catch(() => handleLogout())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 会话持久化
  useEffect(() => {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions))
  }, [sessions])

  // 主题持久化 + 应用到根元素
  useEffect(() => {
    localStorage.setItem(THEME_KEY, theme)
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  // 找到当前会话
  const activeSession = sessions.find((s) => s.id === activeId) ?? null

  const updateSession = useCallback(
    (id: string, fn: (s: ChatSession) => ChatSession) => {
      setSessions((prev) => {
        const next = prev.map((s) => (s.id === id ? fn(s) : s))
        // 同步持久化，确保刷新不丢（不依赖 useEffect 的异步时机）
        localStorage.setItem(SESSIONS_KEY, JSON.stringify(next))
        return next
      })
    },
    [],
  )

  /** 新建对话 */
  const newChat = () => {
    const id = genUUID()
    const session: ChatSession = { id, title: '', messages: [], updatedAt: Date.now() }
    setSessions((prev) => [session, ...prev].slice(0, MAX_SESSIONS))
    setActiveId(id)
    setView('chat')
    setSending(false)
    localStorage.setItem(ACTIVE_KEY, id)
  }

  /** 首次加载时若无会话则自动建一个 */
  useEffect(() => {
    if (sessions.length === 0) {
      const id = genUUID()
      const session: ChatSession = { id, title: '', messages: [], updatedAt: Date.now() }
      setSessions([session])
      setActiveId(id)
    } else if (!activeId || !sessions.some((s) => s.id === activeId)) {
      setActiveId(sessions[0].id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const selectSession = (id: string) => {
    setActiveId(id)
    setView('chat')
    setSending(false)
    localStorage.setItem(ACTIVE_KEY, id)
  }

  /** 重命名会话 */
  const renameSession = (id: string, newTitle: string) => {
    updateSession(id, (s) => ({ ...s, title: newTitle, updatedAt: Date.now() }))
  }

  /** 删除会话 */
  const deleteSession = (id: string) => {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id)
      // 若删除的是当前会话，回退到剩余第一条（若无则自动新建）
      if (activeId === id) {
        const fallbackId = next[0]?.id ?? null
        setActiveId(fallbackId)
        localStorage.setItem(ACTIVE_KEY, fallbackId ?? '')
      }
      return next
    })
    setSending(false)
  }

  /** 处理会话消息变化 */
  const handleMessagesChange = (id: string) => (messages: ChatMessage[]) => {
    updateSession(id, (s) => ({
      ...s,
      messages,
      title: s.title || makeTitle(messages),
      updatedAt: Date.now(),
    }))
  }

  /** 登录成功 */
  const handleLogin = (username: string, token: string) => {
    const nextUser: AuthUser = { username, token }
    setUser(nextUser)
    localStorage.setItem(AUTH_KEY, JSON.stringify(nextUser))
    setShowAuth(false)
    // 登录后进入对话页
    setView('chat')
    // FR-AUTH-02：登录后立即取角色，用于 admin 视图判定
    authMe(token)
      .then((data) => {
        if (data.role) {
          const updated = { ...nextUser, role: data.role }
          setUser(updated)
          localStorage.setItem(AUTH_KEY, JSON.stringify(updated))
        }
      })
      .catch(() => {/* 取角色失败不阻断登录 */})
    // 登录即归并：先把本浏览器（anon_id）下遗留的 guest 会话归并到当前用户，
    // 再拉取服务端「当前用户」会话刷新侧栏（保留历史、切换账号不丢未登录会话）。
    claimGuestSessions()
      .catch(() => {/* 归并失败不阻断，仍继续拉列表 */})
      .finally(() => {
        listSessions()
          .then((serverSessions) => {
            if (!serverSessions.length) return
            setSessions((prev) => {
              const byId = new Map(prev.map((s) => [s.id, s]))
              for (const ss of serverSessions) {
                const existing = byId.get(ss.session_id)
                byId.set(ss.session_id, {
                  id: ss.session_id,
                  title: ss.title || existing?.title || '',
                  messages: existing?.messages || [],
                  updatedAt: existing?.updatedAt || Date.parse(ss.updated_at) || Date.now(),
                })
              }
              return Array.from(byId.values()).slice(0, MAX_SESSIONS)
            })
          })
          .catch(() => {/* 服务端拉取失败不阻断：保留本地会话 */})
      })
  }

  /** 退出登录 */
  const handleLogout = async () => {
    if (user?.token) {
      await authLogout(user.token)
    }
    setUser(null)
    localStorage.removeItem(AUTH_KEY)
  }

  /** 点击上传知识库：需先登录（普通用户也可管理自己的知识库） */
  const handleUploadClick = () => {
    if (!user) {
      setShowAuth(true)
      return
    }
    setView('import')
  }

  return (
    <div className="app">
      <Sidebar
        collapsed={collapsed}
        sessions={sessions}
        activeSessionId={activeId}
        activeView={view}
        theme={theme}
        isLoggedIn={!!user}
        isAdmin={user?.role === 'admin'}
        username={user?.username ?? ''}
        onToggle={() => setCollapsed((c) => !c)}
        onNewChat={newChat}
        onSelectSession={selectSession}
        onRenameSession={renameSession}
        onDeleteSession={deleteSession}
        onSwitchView={(v) => setView(v)}
        onThemeChange={setTheme}
        onLogin={() => setShowAuth(true)}
        onLogout={handleLogout}
      />

      <main className="main">
        {view === 'chat' && activeSession ? (
          <>
            {/* 顶部标题栏（独立组件：标题居中 + 右上角上传知识库） */}
            <ChatHeader
              title={activeSession.title || '新对话'}
              meta={
                activeSession.messages.length > 0
                  ? `${activeSession.messages.length} 条消息`
                  : '欢迎开始新的对话'
              }
              onUpload={handleUploadClick}
            />
            <ChatPanel
              session={activeSession}
              sending={sending}
              username={user?.username ?? ''}
              onChange={handleMessagesChange(activeSession.id)}
              onSendingChange={setSending}
            />
          </>
        ) : (
          <>
            <ChatHeader
              title="知识库管理"
              meta="上传文档，建立私有知识库"
              showUpload={false}
              onUpload={() => setView('import')}
            />
            <div className="import-wrap">
              <ImportPanel isAdmin={user?.role === 'admin'} username={user?.username ?? ''} />
            </div>
          </>
        )}
      </main>

      {/* 登录 / 注册 modal（未登录对话时点击「登录」弹出） */}
      {showAuth && (
        <div className="auth-overlay" onClick={() => setShowAuth(false)}>
          <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
            <AuthPanel onLogin={handleLogin} onCancel={() => setShowAuth(false)} />
          </div>
        </div>
      )}
    </div>
  )
}
