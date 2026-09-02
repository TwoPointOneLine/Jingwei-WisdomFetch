import { kbDisplayName, kbIcon, type KbStat } from '../../knowledgeUtils'
import Icon, { type IconName } from '../../../../components/Icon'


interface KnowledgeHeaderProps {
  /** 当前选中的知识库内部名（空串表示未选择） */
  selectedKb: string
  /** 当前知识库的统计：资料数 / 切片数 */
  stat: KbStat
  /** 是否处于批量操作模式 */
  batchMode: boolean
  /** 无资料时禁用批量入口（无可选条目） */
  canBatch: boolean
  onToggleBatch: () => void
  onImport: () => void
}

/**
 * 知识库管理页 · 右侧内容区头部
 *
 * 与对话页标题栏（.chat-titlebar）共用 64px / 边框 / 背景规格，
 * 但布局为「左对齐标题块 + 右侧操作」，区别于对话页的「三栏居中」。
 */
export default function KnowledgeHeader({
  selectedKb,
  stat,
  batchMode,
  canBatch,
  onToggleBatch,
  onImport,
}: KnowledgeHeaderProps) {
  const empty = selectedKb === ''
  const iconName: IconName = empty ? 'folder' : (kbIcon(selectedKb) === '🏠' ? 'home' : 'folder')

  return (
    <header className="kb-content-head kb-content-head-left">
      <div className="kb-head-block">
        <div className="chat-title kb-head-title">
          <Icon name={iconName} size={16} className="kb-head-title-icon" />
          <span className="kb-head-title-name">
            {empty ? '未选择知识库' : kbDisplayName(selectedKb)}
          </span>
        </div>
        <div className="chat-meta kb-head-meta">
          {empty ? '请从左侧选择一个知识库' : `${stat.docs} 份资料 · ${stat.chunks} 切片`}
        </div>
      </div>

      <div className="kb-head-right">
        <button
          className={`btn ghost batch-toggle-btn${batchMode ? ' active' : ''}`}
          type="button"
          onClick={onToggleBatch}
          disabled={!canBatch && !batchMode}
          title={canBatch ? '批量选择资料进行统一操作' : '当前知识库暂无资料'}
        >
          <Icon name="check-circle" size={15} />
          <span>{batchMode ? '退出批量' : '批处理操作'}</span>
        </button>
        <button className="btn primary upload-kb-btn" type="button" onClick={onImport}>
          <Icon name="upload" size={15} />
          <span>知识导入</span>
        </button>
      </div>
    </header>
  )
}
