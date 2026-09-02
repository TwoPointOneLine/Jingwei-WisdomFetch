import { useEffect, useRef, useState } from 'react'
import type { ChatSession } from '../../types'

interface SessionListProps {
  sessions: ChatSession[]
  activeSessionId: string | null
  activeView: 'chat' | 'import'
  onSelect: (id: string) => void
  onRename: (id: string, newTitle: string) => void
  onDelete: (id: string) => void
}

/** 时间格式化：今天显示时分，其他显示月/日 */
export function formatSessionTime(ts: number): string {
  const d = new Date(ts)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/**
 * 单个对话项：正常态（标题 + 时间 + 悬停操作按钮）与内联重命名编辑态。
 */
function SessionItem({
  session,
  isActive,
  onSelect,
  onRename,
  onDelete,
}: {
  session: ChatSession
  isActive: boolean
  onSelect: () => void
  onRename: (title: string) => void
  onDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // 进入编辑态时聚焦并选中文本
  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  const startEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    setDraft(session.title || '新对话')
    setEditing(true)
  }

  const commitRename = () => {
    setEditing(false)
    const value = draft.trim()
    if (value && value !== (session.title || '新对话')) {
      onRename(value)
    }
  }

  // 删除：点击后确认
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    // 简单确认，避免误删
    if (window.confirm(`确定删除对话「${session.title || '新对话'}」吗？删除后不可恢复。`)) {
      onDelete()
    }
  }

  // 编辑态：渲染输入框
  if (editing) {
    return (
      <div className="session-item editing">
        <input
          ref={inputRef}
          className="session-rename-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commitRename}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              commitRename()
            } else if (e.key === 'Escape') {
              setEditing(false)
            }
          }}
          onClick={(e) => e.stopPropagation()}
        />
      </div>
    )
  }

  return (
    <div
      className={`session-item${isActive ? ' active' : ''}`}
      onClick={onSelect}
      title={session.title || '新对话'}
    >
      <span className="session-title">{session.title || '新对话'}</span>
      {/* 悬停操作：重命名 / 删除 */}
      <span className="session-actions">
        <button className="session-action" title="重命名" onClick={startEdit}>
          ✎
        </button>
        <button className="session-action danger" title="删除" onClick={handleDelete}>
          🗑
        </button>
      </span>
      {/* 时间显示在最后面 */}
      <span className="session-time">{formatSessionTime(session.updatedAt)}</span>
    </div>
  )
}

/**
 * 对话历史列表（可复用）：展示会话、支持选择 / 重命名 / 删除。
 *
 * 组件保持自身交互状态（内联重命名、编辑态），通过回调向上通知操作，
 * 不直接持有数据，便于被不同容器复用。
 */
export default function SessionList({
  sessions,
  activeSessionId,
  activeView,
  onSelect,
  onRename,
  onDelete,
}: SessionListProps) {
  return (
    <div className="session-list">
      {sessions.length === 0 && (
        <div className="session-empty">暂无对话，点击上方「新建对话」开始</div>
      )}
      {sessions.map((s) => (
        <SessionItem
          key={s.id}
          session={s}
          isActive={s.id === activeSessionId && activeView === 'chat'}
          onSelect={() => onSelect(s.id)}
          onRename={(title) => onRename(s.id, title)}
          onDelete={() => onDelete(s.id)}
        />
      ))}
    </div>
  )
}
