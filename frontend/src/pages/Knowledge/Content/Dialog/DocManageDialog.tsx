import { useEffect, useState } from 'react'
import { moveDocument, setDocumentVisibility } from '../../../../api'
import type { DocumentItem, KnowledgeBase, Visibility } from '../../../../types'

interface Props {
  open: boolean
  item: DocumentItem | null
  kbList: KnowledgeBase[]
  currentUser: string
  userRole: string
  onClose: () => void
  onChanged: () => void
}

const VIS_LABEL: Record<Visibility, string> = {
  private: '私密',
  team: '团队',
  shared: '共享',
}

export default function DocManageDialog({
  open,
  item,
  kbList,
  currentUser,
  userRole,
  onClose,
  onChanged,
}: Props) {
  const [targetKb, setTargetKb] = useState('')
  const [visibility, setVisibility] = useState<Visibility>('private')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (item) {
      setTargetKb(item.kb_name || '')
      setVisibility(item.visibility ?? 'private')
      setErr('')
    }
  }, [item])

  if (!open || !item) return null
  const doc = item

  const isOwner = doc.owner === currentUser || userRole === 'admin'
  const movableKbs = kbList.filter(
    (kb) => kb.name !== doc.kb_name && (userRole === 'admin' || kb.owner === currentUser || kb.is_default),
  )
  const canMove = isOwner && movableKbs.length > 0

  async function applyMove() {
    if (!targetKb || targetKb === doc.kb_name) return
    setBusy(true)
    setErr('')
    try {
      await moveDocument(doc.item_name, targetKb)
      onChanged()
      onClose()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function applyVisibility() {
    if (visibility === doc.visibility) return
    setBusy(true)
    setErr('')
    try {
      await setDocumentVisibility(doc.item_name, visibility)
      onChanged()
      onClose()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-mask" onMouseDown={onClose}>
      <div className="doc-manage" onMouseDown={(e) => e.stopPropagation()}>
        <div className="doc-manage-head">
          <div className="doc-manage-title">{doc.item_name}</div>
          <button className="doc-manage-close" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>

        <div className="doc-manage-body">
          {!isOwner && (
            <div className="doc-manage-hint">非本人资料，仅可查看，修改需资料所有者或管理员操作。</div>
          )}

          <div className="doc-manage-group">
            <div className="doc-manage-label">共享 / 可见性</div>
            <div className="kb-option-cards">
              {(['private', 'team', 'shared'] as Visibility[]).map((v) => (
                <button
                  key={v}
                  className={`kb-option-card${visibility === v ? ' active' : ''}`}
                  disabled={!isOwner || busy}
                  onClick={() => setVisibility(v)}
                >
                  {VIS_LABEL[v]}
                </button>
              ))}
            </div>
          </div>

          <div className="doc-manage-group">
            <div className="doc-manage-label">移动到知识库</div>
            {canMove ? (
              <div className="kb-option-pills">
                {movableKbs.map((kb) => (
                  <button
                    key={kb.name}
                    className={`kb-option-pill${targetKb === kb.name ? ' active' : ''}`}
                    disabled={busy}
                    onClick={() => setTargetKb(kb.name)}
                  >
                    {kb.name}
                    {kb.is_default ? '（默认）' : ''}
                  </button>
                ))}
              </div>
            ) : (
              <div className="doc-manage-hint">无可移动的目标知识库。</div>
            )}
          </div>

          {err && <div className="doc-manage-error">{err}</div>}
        </div>

        <div className="doc-manage-foot">
          <button className="doc-btn ghost" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button
            className="doc-btn primary"
            disabled={!isOwner || busy || (visibility === doc.visibility && (!targetKb || targetKb === doc.kb_name))}
            onClick={() => {
              if (visibility !== doc.visibility) void applyVisibility()
              else void applyMove()
            }}
          >
            {busy ? '处理中…' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}
