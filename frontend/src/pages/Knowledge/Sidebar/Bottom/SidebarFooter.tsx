import { useState } from 'react'
import Icon from '../../../../components/Icon'

/** 左侧栏底部：新建知识库输入 + 总览统计条 */
function SidebarFooter({
  kbCount,
  totalDocs,
  totalChunks,
  onCreate,
}: {
  kbCount: number
  totalDocs: number
  totalChunks: number
  onCreate: (name: string) => Promise<void>
}) {
  const [newKb, setNewKb] = useState('')

  const submit = async () => {
    const name = newKb.trim()
    if (!name) return
    try {
      await onCreate(name)
      setNewKb('')
    } catch {
      /* 创建失败：保留输入内容，便于修改后重试 */
    }
  }

  return (
    <>
      <div className="kb-side-create">
        <div className="kb-side-new">
          <Icon name="plus" size={14} className="kb-side-new-icon" />
          <input
            className="kb-new-input"
            placeholder="新建知识库…"
            value={newKb}
            onChange={(e) => setNewKb(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
          />
          <button className="kb-new-btn" onClick={submit} disabled={!newKb.trim()} type="button">
            新建
          </button>
        </div>
      </div>

      {/* 总览统计条 */}
      <div className="kb-sidebar-stats">
        <div className="kb-stat">
          <span className="kb-stat-num">{kbCount}</span>
          <span className="kb-stat-label">知识库</span>
        </div>
        <span className="kb-stat-divider" />
        <div className="kb-stat">
          <span className="kb-stat-num">{totalDocs}</span>
          <span className="kb-stat-label">资料</span>
        </div>
        <span className="kb-stat-divider" />
        <div className="kb-stat">
          <span className="kb-stat-num">{totalChunks}</span>
          <span className="kb-stat-label">切片</span>
        </div>
      </div>
    </>
  )
}

export { SidebarFooter }
