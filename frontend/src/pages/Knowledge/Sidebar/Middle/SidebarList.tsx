import { useEffect, useRef, useState } from 'react'
import type { KnowledgeBase } from '../../../../types'
import { EMPTY_STAT, kbDisplayName, type KbStat } from '../../knowledgeUtils'
import Icon, { type IconName } from '../../../../components/Icon'

/** 左侧知识库（方库）列表（中部主体）：含内联重命名、更多操作菜单、删除触发 */
function SidebarList({
  kbList,
  selectedKb,
  statByKb,
  onSelect,
  onRename,
  onRequestDelete,
}: {
  kbList: KnowledgeBase[]
  selectedKb: string
  statByKb: Map<string, KbStat>
  onSelect: (name: string) => void
  onRename: (oldName: string, newName: string) => Promise<void>
  onRequestDelete: (kb: KnowledgeBase) => void
}) {
  // 展开操作菜单的库名（同时只允许一个）
  const [menuFor, setMenuFor] = useState<string | null>(null)
  // 正在内联重命名的库名
  const [editingKb, setEditingKb] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  // Esc 取消重命名时抑制 blur 提交
  const cancelEditRef = useRef(false)
  const editInputRef = useRef<HTMLInputElement>(null)

  // 点击空白处收起操作菜单
  useEffect(() => {
    if (!menuFor) return
    const close = () => setMenuFor(null)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [menuFor])

  // 进入重命名时聚焦并全选
  useEffect(() => {
    if (editingKb) editInputRef.current?.select()
  }, [editingKb])

  const startRename = (kb: KnowledgeBase) => {
    setMenuFor(null)
    setEditName(kb.name)
    setEditingKb(kb.name)
  }

  const commitRename = async () => {
    const target = editingKb
    const next = editName.trim()
    setEditingKb(null)
    if (!target || !next || next === target) return
    try {
      await onRename(target, next)
    } catch {
      /* 失败提示由父组件统一展示 */
    }
  }

  return (
    <div className="kb-sidebar-list">
      {kbList.map((b) => {
        const st = statByKb.get(b.name) ?? EMPTY_STAT
        const iconName: IconName = b.is_default ? 'home' : 'folder'
        const editing = editingKb === b.name
        return (
          <div
            key={b.name}
            className={`kb-side-item${selectedKb === b.name ? ' active' : ''}${editing ? ' editing' : ''}`}
          >
            {editing ? (
              <div className="kb-side-edit">
                <span className="kb-side-icon"><Icon name={iconName} size={17} /></span>
                <input
                  ref={editInputRef}
                  className="kb-side-edit-input"
                  value={editName}
                  maxLength={64}
                  onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      commitRename()
                    } else if (e.key === 'Escape') {
                      e.preventDefault()
                      cancelEditRef.current = true
                      setEditingKb(null)
                    }
                  }}
                  onBlur={() => {
                    if (cancelEditRef.current) {
                      cancelEditRef.current = false
                      return
                    }
                    commitRename()
                  }}
                  autoFocus
                />
              </div>
            ) : (
              <>
                <button
                  type="button"
                  className="kb-side-main"
                  onClick={() => onSelect(b.name)}
                  title={b.name}
                >
                  <span className="kb-side-icon"><Icon name={iconName} size={17} /></span>
                  <span className="kb-side-text">
                    <span className="kb-side-name">{kbDisplayName(b.name)}</span>
                    <span className="kb-side-sub">{st.docs} 份资料 · {st.chunks} 切片</span>
                  </span>
                  {b.is_default && <span className="kb-side-tag">默认</span>}
                </button>

                {/* 默认库不可重命名 / 删除 */}
                {!b.is_default && (
                  <div className="kb-side-ops">
                    <button
                      type="button"
                      className="kb-side-more"
                      title="更多操作"
                      aria-label="更多操作"
                      onClick={(e) => {
                        e.stopPropagation()
                        setMenuFor(menuFor === b.name ? null : b.name)
                      }}
                    >
                      <span className="kb-side-more-dot" />
                      <span className="kb-side-more-dot" />
                      <span className="kb-side-more-dot" />
                    </button>
                    {menuFor === b.name && (
                      <div
                        className="kb-side-menu"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          type="button"
                          className="kb-side-menu-item"
                          onClick={() => startRename(b)}
                        >
                          <Icon name="document" size={14} />
                          <span>重命名</span>
                        </button>
                        <button
                          type="button"
                          className="kb-side-menu-item danger"
                          onClick={() => {
                            setMenuFor(null)
                            onRequestDelete(b)
                          }}
                        >
                          <Icon name="close" size={14} />
                          <span>删除</span>
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )
      })}
    </div>
  )
}

export { SidebarList }
