import { useCallback, useEffect, useState } from 'react'
import AuthPanel from './components/AuthPanel'
import ChatPage from './pages/Chat/ChatPage'
import KnowledgePage from './pages/Knowledge/KnowledgePage'
import type { ThemeMode } from './pages/Chat/SidebarFooter'
import { authLogout, authMe, claimGuestSessions, deleteSessionApi, genUUID, listSessions } from './api'
import type { ChatMessage, ChatSession } from './types'
import './App.css'

const SESSIONS_KEY = 'jingwei_rag_sessions'
const ACTIVE_KEY = 'jingwei_rag_active'
const THEME_KEY = 'jingwei_rag_theme'
const AUTH_KEY = 'jingwei_rag_user'
const MAX_SESSIONS = 50

type View = 'chat' | 'import'

/** 视图 ↔ 地址栏 hash 映射：强制刷新 / 前进后退都停留在当前页面 */
const HASH_BY_VIEW: Record<View, string> = { chat: '#/', import: '#/knowledge' }

interface AuthUser {
  username: string
  token: string
  role?: string
}

/** 从地址栏 hash 解析当前视图（#/knowledge、#/import 均指向知识库页） */
function viewFromHash(): View {
  const raw = window.location.hash.replace(/^#\/?/, '').trim().toLowerCase()
  return raw === 'knowledge' || raw === 'import' ? 'import' : 'chat'
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
  const [sessions, setSessions] = useState<ChatSession[]>(loadSessions)
  const [activeId, setActiveId] = useState<string | null>(loadActive)
  const [theme, setTheme] = useState<ThemeMode>(loadTheme)
  const [user, setUser] = useState<AuthUser | null>(loadUser)
  const [view, setView] = useState<View>(() => (user ? viewFromHash() : 'chat'))
  const [showAuth, setShowAuth] = useState(false)
  const [sending, setSending] = useState(false)
  // 未登录时点击「知识库」：挂起目标视图，登录成功后直接进入
  const [pendingImport, setPendingImport] = useState(false)

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

  /** 切换视图并同步地址栏：非 replace 时会写入历史，浏览器前进/后退可用 */
  const applyView = useCallback((next: View, replace = false) => {
    setView(next)
    const hash = HASH_BY_VIEW[next]
    if (window.location.hash === hash) return
    const url = `${window.location.pathname}${window.location.search}${hash}`
    if (replace) window.history.replaceState(null, '', url)
    else window.location.hash = hash
  }, [])

  // 地址栏变化（前进/后退、手动改 hash）→ 同步视图
  useEffect(() => {
    const onHashChange = () => {
      const next = viewFromHash()
      // 知识库页需登录：未登录则退回对话页并弹出登录
      if (next === 'import' && !user) {
        applyView('chat', true)
        setShowAuth(true)
        return
      }
      setView(next)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [user, applyView])

  // 首次挂载：未登录时地址栏不允许停留在知识库页（避免刷新后地址与界面不一致）
  useEffect(() => {
    if (!user && viewFromHash() === 'import') {
      window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#/`)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
    applyView('chat')
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
    applyView('chat')
    setSending(false)
    localStorage.setItem(ACTIVE_KEY, id)
  }

  /** 重命名会话 */
  const renameSession = (id: string, newTitle: string) => {
    updateSession(id, (s) => ({ ...s, title: newTitle, updatedAt: Date.now() }))
  }

  /** 删除会话：先乐观更新本地，再请求后端硬删除；后端失败则回滚。
   * 关键修复：此前根本未调用后端删除接口，导致登录时 listSessions 把服务端旧会话重新合并回本地。 */
  const deleteSession = useCallback(
    async (id: string) => {
      // 乐观更新前先记录快照，便于失败回滚
      let rollback: ChatSession[] | null = null
      let rollbackActive: string | null = null
      setSessions((prev) => {
        rollback = prev
        const next = prev.filter((s) => s.id !== id)
        if (activeId === id) {
          const fallbackId = next[0]?.id ?? null
          setActiveId(fallbackId)
          localStorage.setItem(ACTIVE_KEY, fallbackId ?? '')
        }
        return next
      })
      setSending(false)
      try {
        await deleteSessionApi(id)
      } catch {
        // 回滚本地状态，保证 UI 与后端一致
        if (rollback) setSessions(rollback)
        if (rollbackActive !== null) setActiveId(rollbackActive)
      }
    },
    [activeId],
  )

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
    // 登录后进入对话页（若此前点击「知识库」触发的登录，则直接进入知识库页）
    applyView(pendingImport ? 'import' : 'chat', true)
    setPendingImport(false)
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
    setPendingImport(false)
    // 退出后知识库页不可用，退回对话页
    applyView('chat', true)
  }

  /** 点击上传知识库：需先登录（普通用户也可管理自己的知识库） */
  const handleUploadClick = () => {
    if (!user) {
      setPendingImport(true)
      setShowAuth(true)
      return
    }
    applyView('import')
  }

  /** 关闭登录弹窗并清除挂起目标 */
  const closeAuth = () => {
    setShowAuth(false)
    setPendingImport(false)
  }

  return (
    <>
      {view === 'chat' ? (
        <ChatPage
          collapsed={collapsed}
          sessions={sessions}
          activeSessionId={activeId}
          activeView={view}
          theme={theme}
          isLoggedIn={!!user}
          username={user?.username ?? ''}
          sending={sending}
          activeSession={activeSession}
          onToggle={() => setCollapsed((c) => !c)}
          onNewChat={newChat}
          onSelectSession={selectSession}
          onRenameSession={renameSession}
          onDeleteSession={deleteSession}
          onSwitchView={(v) => applyView(v)}
          onThemeChange={setTheme}
          onLogin={() => setShowAuth(true)}
          onLogout={handleLogout}
          onUpload={handleUploadClick}
          onMessagesChange={
            activeId ? handleMessagesChange(activeId) : () => {}
          }
          onSendingChange={setSending}
        />
      ) : (
        <KnowledgePage
          isAdmin={user?.role === 'admin'}
          username={user?.username ?? ''}
          onBack={() => applyView('chat')}
        />
      )}

      {/* 登录 / 注册 modal（未登录对话时点击「登录」弹出） */}
      {showAuth && (
        <div className="auth-overlay" onClick={closeAuth}>
          <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
            <AuthPanel onLogin={handleLogin} onCancel={closeAuth} />
          </div>
        </div>
      )}
    </>
  )
}
