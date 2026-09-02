import type {DocumentItem, KnowledgeBase, Visibility} from '../../../../types'
import {moveDocument, offlineDocument, setDocumentVisibility} from '../../../../api'
import Icon from '../../../../components/Icon'
import {kbDisplayName} from '../../knowledgeUtils'
import {visLabel} from '../Main/BookCard'

/** 批量操作的种类 */
export type BatchAction = 'visibility' | 'move' | 'offline'

/** 批量操作栏（sticky 吸底，仅在批量模式且有可管理资料时展示） */
function BatchBar({
                    allSelected,
                    toggleSelectAll,
                    selectedItems,
                    selectableItems,
                    batchRunning,
                    runBatch,
                    kbList,
                  }: {
  allSelected: boolean
  toggleSelectAll: () => void
  selectedItems: DocumentItem[]
  selectableItems: DocumentItem[]
  batchRunning: BatchAction | null
  runBatch: (
    action: BatchAction,
    label: string,
    fn: (name: string) => Promise<unknown>,
    expect?: string,
  ) => Promise<void>
  kbList: KnowledgeBase[]
}) {
  return (
    <div className="batch-bar">
      <label className="batch-select-all">
        <input
          type="checkbox"
          checked={allSelected}
          onChange={toggleSelectAll}
          aria-label="全选"
        />
        <span className="book-check-box">
          {allSelected && <Icon name="check" size={12} strokeWidth={2.6}/>}
        </span>
        <span>{allSelected ? '取消全选' : '全选'}</span>
      </label>

      <span className="batch-count">
        已选 <b>{selectedItems.length}</b> / {selectableItems.length} 份
      </span>

      <div className="batch-actions">
        <span className="batch-label">设为</span>
        {(['private', 'team', 'shared'] as Visibility[]).map((v) => (
          <button
            key={v}
            className="btn ghost batch-btn"
            type="button"
            disabled={!selectedItems.length || batchRunning !== null}
            title={`将选中资料设为${visLabel(v)}`}
            onClick={() =>
              runBatch(
                'visibility',
                `设为${visLabel(v)}`,
                (n) => setDocumentVisibility(n, v),
                v, // 校验后端实际生效值，防止「返回成功但未生效」
              )
            }
          >
            {batchRunning === 'visibility' ? (
              <Icon name="spinner" size={13}/>
            ) : (
              <>
                <Icon name={v === 'private' ? 'lock' : v === 'team' ? 'team' : 'globe'} size={13}/>
                <span>{visLabel(v)}</span>
              </>
            )}
          </button>
        ))}

        <span className="batch-divider"/>

        <button
          className="btn ghost danger-ghost batch-btn"
          type="button"
          disabled={!selectedItems.length || batchRunning !== null}
          onClick={() => runBatch('offline', '下线', offlineDocument)}
        >
          {batchRunning === 'offline' ? (
            <Icon name="spinner" size={13}/>
          ) : (
            <>
              <Icon name="close" size={13}/>
              <span>下线</span>
            </>
          )}
        </button>

        <span className="batch-divider"/>

        <span className="batch-label">移动到</span>
        <select
          className="kb-filter batch-kb-select"
          value=""
          disabled={!selectedItems.length || batchRunning !== null}
          onChange={(e) => {
            const target = e.target.value
            if (!target) return
            e.target.value = ''
            runBatch('move', `移动到「${kbDisplayName(target)}」`, (n) => moveDocument(n, target))
          }}
          aria-label="移动到知识库"
        >
          <option value="">选择知识库…</option>
          {kbList.map((b) => (
            <option key={b.name} value={b.name}>
              {kbDisplayName(b.name)}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}

export {BatchBar}
