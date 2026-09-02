import { useState } from 'react'
import type { KnowledgeBase } from '../../../types'
import { type KbStat } from '../knowledgeUtils'
import Icon from '../../../components/Icon'
import { SidebarHead } from './Top/SidebarHead'
import { SidebarList } from './Middle/SidebarList'
import { SidebarFooter } from './Bottom/SidebarFooter'
import { SidebarDeleteDialog } from './Dialog/SidebarDeleteDialog'

interface KnowledgeSidebarProps {
  /** 知识库列表（默认库 + 当前用户创建的库） */
  kbList: KnowledgeBase[]
  /** 当前选中的知识库内部名 */
  selectedKb: string
  /** 每个知识库的统计（key 为知识库内部名） */
  statByKb: Map<string, KbStat>
  /** 全局统计：资料总数 / 切片总数 */
  totalDocs: number
  totalChunks: number
  loading: boolean
  /** 加载或创建失败的提示（空串表示无错误） */
  error: string
  onSelect: (name: string) => void
  /** 新建知识库：成功 resolve、失败 reject（失败时输入框保留内容便于修改重试） */
  onCreate: (name: string) => Promise<void>
  /** 重命名知识库：成功 resolve、失败 reject */
  onRename: (oldName: string, newName: string) => Promise<void>
  /** 删除知识库：成功 resolve、失败 reject */
  onDelete: (name: string) => Promise<void>
  onBack: () => void
}

/**
 * 知识库管理页 · 左侧知识库（方库）列表
 *
 * 编排层：自上而下为「头部 → 库列表 → 新建输入 → 统计条 → 删除确认弹窗」。
 * 头部与对话页侧栏（Sidebar）完全同构，复用 .sidebar-head 容器 + .brand-horizontal
 * 横版 logo，右侧 .kb-back-btn 为返回对话入口（故底部不再重复放置返回按钮）。
 * 库列表项支持重命名 / 删除（默认库两项均不可操作，由后端再次兜底校验）。
 */
export default function KnowledgeSidebar({
  kbList,
  selectedKb,
  statByKb,
  totalDocs,
  totalChunks,
  loading,
  error,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  onBack,
}: KnowledgeSidebarProps) {
  // 待确认删除的库
  const [pendingDelete, setPendingDelete] = useState<KnowledgeBase | null>(null)
  const [deleting, setDeleting] = useState(false)

  const confirmDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await onDelete(pendingDelete.name)
      setPendingDelete(null)
    } catch {
      /* 失败提示由父组件统一展示，弹窗保持打开便于重试 */
    } finally {
      setDeleting(false)
    }
  }

  return (
    <aside className="kb-sidebar">
      {/* 头部：与对话页侧栏一致（横版 logo 按主题切换 + 右侧返回对话） */}
      <SidebarHead onBack={onBack} />

      {error && <div className="kb-inline-err kb-sidebar-err"><span>⚠️ {error}</span></div>}

      {loading ? (
        <div className="kb-sidebar-loading">
          <span className="kb-spin-dots" /> 加载中…
        </div>
      ) : kbList.length === 0 ? (
        <div className="kb-sidebar-empty">
          <span className="kb-sidebar-empty-icon"><Icon name="database" size={26} /></span>
          <span className="kb-sidebar-empty-title">还没有知识库</span>
          <span className="kb-sidebar-empty-sub">在下方输入名称新建一个</span>
        </div>
      ) : (
        <SidebarList
          kbList={kbList}
          selectedKb={selectedKb}
          statByKb={statByKb}
          onSelect={onSelect}
          onRename={onRename}
          onRequestDelete={(kb) => setPendingDelete(kb)}
        />
      )}

      <SidebarFooter
        kbCount={kbList.length}
        totalDocs={totalDocs}
        totalChunks={totalChunks}
        onCreate={onCreate}
      />

      {/* 删除确认弹窗 */}
      <SidebarDeleteDialog
        pendingDelete={pendingDelete}
        statByKb={statByKb}
        deleting={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </aside>
  )
}
