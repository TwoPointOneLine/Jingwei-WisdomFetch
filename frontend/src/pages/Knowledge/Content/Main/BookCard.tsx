import type { DocumentItem, Visibility } from '../../../../types'
import Icon, { type IconName } from '../../../../components/Icon'

// 由 item_name 派生稳定的封面配色（基于字符串哈希选色板）
const COVER_PALETTE = [
  { bg: 'linear-gradient(135deg,#1B2A4E 0%,#2C3E66 100%)', accent: '#C89B3C' },
  { bg: 'linear-gradient(135deg,#2E4A3B 0%,#3E6B52 100%)', accent: '#8FD9A8' },
  { bg: 'linear-gradient(135deg,#3A2E4E 0%,#5A4376 100%)', accent: '#C9A8E0' },
  { bg: 'linear-gradient(135deg,#4E2E2E 0%,#7A4343 100%)', accent: '#E0A8A8' },
  { bg: 'linear-gradient(135deg,#1F3A4E 0%,#2E5676 100%)', accent: '#8FC9E0' },
  { bg: 'linear-gradient(135deg,#4E3A1F 0%,#7A5A2E 100%)', accent: '#E0C98F' },
]
function coverOf(key: string) {
  let h = 0
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0
  return COVER_PALETTE[h % COVER_PALETTE.length]
}

export const visLabel = (v?: Visibility) =>
  v === 'shared' ? '共享' : v === 'team' ? '团队可见' : '私有'
export const visCls = (v?: Visibility) =>
  v === 'shared' ? 'vis-shared' : v === 'team' ? 'vis-team' : 'vis-private'

// 书本封面卡片（书架式展示）
function BookCard({
  it,
  batchMode,
  selected,
  manageable,
  onToggleSelect,
  onManageDoc,
  onOffline,
  busyName,
}: {
  it: DocumentItem
  batchMode: boolean
  selected: boolean
  manageable: boolean
  onToggleSelect: (name: string) => void
  onManageDoc?: (item: DocumentItem) => void
  onOffline?: (name: string) => void
  busyName?: string
}) {
  const cov = coverOf(it.item_name)
  const title = it.item_name
  const uploader = it.owner || '系统'
  const isShared = it.visibility === 'shared'
  const coverIcon: IconName =
    it.visibility === 'shared' ? 'globe' : it.visibility === 'team' ? 'team' : 'book'
  const checked = selected
  return (
    <div
      className={
        'book-card vis-' +
        (it.visibility ?? 'private') +
        (batchMode ? ' selectable' : '') +
        (checked ? ' selected' : '')
      }
      title={it.item_name}
    >
      {/* 批量模式：可管理条目显示复选框；无权管理的条目不可选 */}
      {batchMode && (
        <label className={`book-check${manageable ? '' : ' disabled'}`}>
          <input
            type="checkbox"
            checked={checked}
            disabled={!manageable}
            onChange={() => manageable && onToggleSelect(it.item_name)}
            onClick={(e) => e.stopPropagation()}
            aria-label={`选择 ${it.item_name}`}
          />
          <span className="book-check-box">
            {checked && <Icon name="check" size={12} strokeWidth={2.6} />}
          </span>
        </label>
      )}
      <div
        className="book-cover"
        style={{ background: cov.bg }}
        role="button"
        tabIndex={0}
        onClick={() => {
          if (batchMode && manageable) onToggleSelect(it.item_name)
          else onManageDoc?.(it)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            if (batchMode && manageable) onToggleSelect(it.item_name)
            else onManageDoc?.(it)
          }
        }}
      >
        <div className="book-spine" style={{ background: cov.accent }} />
        <div className="book-cover-inner">
          <div className="book-emoji">
            <Icon name={coverIcon} size={22} />
          </div>
          <div className="book-title">{title}</div>
          <div className="book-rule" style={{ background: cov.accent }} />
          <div className="book-author">上传者 · {uploader}</div>
        </div>
        <span className={`vis-badge ${visCls(it.visibility)}`}>{visLabel(it.visibility)}</span>
      </div>
      <div className="book-foot">
        <div className="book-foot-meta">
          <span>{it.chunk_count} 切片</span>
          {it.product_name ? <span>· {it.product_name}</span> : null}
        </div>
        {/* 批量模式下隐藏单条操作，统一走底部批量操作栏 */}
        {!batchMode && (
          <div className="book-actions">
            {manageable ? (
              <button
                className="btn ghost danger-ghost book-action-btn"
                disabled={busyName === it.item_name}
                onClick={(e) => {
                  e.stopPropagation()
                  onOffline?.(it.item_name)
                }}
                title="下线该资料"
              >
                {busyName === it.item_name ? (
                  <Icon name="spinner" size={13} />
                ) : (
                  <>
                    <Icon name="close" size={13} />
                    <span>下线</span>
                  </>
                )}
              </button>
            ) : (
              <span className="doc-readonly">
                {isShared ? '全员共享' : it.visibility === 'team' ? '团队共享' : '他人资料'}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// 「添加知识」占位书本卡片：点击唤起导入对话框
function AddBookCard({ onOpenUpload }: { onOpenUpload?: () => void }) {
  return (
    <button
      className="book-card add-book-card"
      type="button"
      onClick={onOpenUpload}
      title="导入知识"
    >
      <div className="book-cover add-book-cover">
        <div className="book-spine" />
        <div className="book-cover-inner">
          <div className="book-emoji"><Icon name="upload" size={20} /></div>
          <div className="book-title">导入知识</div>
          <div className="book-rule" />
          <div className="book-author">点击此处，将文档汇入当前知识库</div>
        </div>
      </div>
    </button>
  )
}

export { COVER_PALETTE, coverOf, BookCard, AddBookCard }
