import type { KnowledgeBase } from '../../../../types'
import { EMPTY_STAT, kbDisplayName, type KbStat } from '../../knowledgeUtils'

/** 删除知识库确认弹窗 */
function SidebarDeleteDialog({
  pendingDelete,
  statByKb,
  deleting,
  onConfirm,
  onCancel,
}: {
  pendingDelete: KnowledgeBase | null
  statByKb: Map<string, KbStat>
  deleting: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  if (!pendingDelete) return null
  return (
    <div className="modal-mask" onClick={() => !deleting && onCancel()}>
      <div className="doc-manage kb-confirm" onClick={(e) => e.stopPropagation()}>
        <div className="doc-manage-head">
          <span className="doc-manage-title">删除知识库</span>
          <button className="doc-manage-close" onClick={onCancel} disabled={deleting} type="button">
            ×
          </button>
        </div>
        <div className="doc-manage-body">
          <p className="kb-confirm-text">
            确定要删除知识库「<b>{kbDisplayName(pendingDelete.name)}</b>」吗？
          </p>
          <div className="doc-manage-hint">
            库内的 {(statByKb.get(pendingDelete.name) ?? EMPTY_STAT).docs} 份资料将移动到默认库，
            <b>不会被删除</b>。此操作不可撤销。
          </div>
        </div>
        <div className="doc-manage-foot">
          <button className="doc-btn ghost" onClick={onCancel} disabled={deleting} type="button">
            取消
          </button>
          <button
            className="doc-btn primary danger"
            onClick={onConfirm}
            disabled={deleting}
            type="button"
          >
            {deleting ? '删除中…' : '确认删除'}
          </button>
        </div>
      </div>
    </div>
  )
}

export { SidebarDeleteDialog }
