import { useEffect, useMemo, useState } from 'react'
import ImportPanel from './Content/ImportPanel'
import UploadPanel from './Content/Dialog/UploadPanel'
import DocManageDialog from './Content/Dialog/DocManageDialog'
import KnowledgeHeader from './Content/Header/KnowledgeHeader'
import { DocumentsSection } from './Content/Header/DocumentsSection'
import KnowledgeSidebar from './Sidebar/KnowledgeSidebar'
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  listDocuments,
  listKnowledgeBases,
  renameKnowledgeBase,
} from '../../api'
import type { DocumentItem, ImportTask, KnowledgeBase, Visibility } from '../../types'
import { buildStatByKb, EMPTY_STAT } from './knowledgeUtils'

interface KnowledgePageProps {
  isAdmin: boolean
  username: string
  onBack: () => void
}

// 当前选中的知识库持久化：刷新后仍停留在同一个库
const SELECTED_KB_KEY = 'jingwei_rag_selected_kb'
// 导入可见性默认值持久化（页面已移除选项栏，改用记忆值）
const VISIBILITY_KEY = 'jingwei_rag_upload_visibility'

/** 读取持久化的可见性，非法值回落 private */
function loadVisibility(): Visibility {
  const raw = localStorage.getItem(VISIBILITY_KEY)
  return raw === 'team' || raw === 'shared' ? raw : 'private'
}

/**
 * 知识库管理界面（编排层）：只负责数据获取与状态管理，视图拆分为
 *   - KnowledgeSidebar：左侧知识库列表（品牌 / 总览统计 / 库列表 / 新建 / 返回对话）
 *   - KnowledgeHeader ：右侧内容区头部（面包屑 / 当前库统计 / 知识导入）
 *   - ImportPanel     ：所选库的知识内容
 * 弹窗（UploadPanel / DocManageDialog）同样提升到本层，便于跨组件联动。
 */
export default function KnowledgePage({ isAdmin, username, onBack }: KnowledgePageProps) {
  const [kbList, setKbList] = useState<KnowledgeBase[]>([])
  const [selectedKb, setSelectedKb] = useState(() => localStorage.getItem(SELECTED_KB_KEY) || '')
  const [kbLoading, setKbLoading] = useState(false)
  const [kbErr, setKbErr] = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const [uploadVisibility, setUploadVisibility] = useState<Visibility>(loadVisibility)
  const [manageItem, setManageItem] = useState<DocumentItem | null>(null)
  const [docRefreshKey, setDocRefreshKey] = useState(0)
  // 导入任务列表（提升到页面级：上传成功后展示进度，完成后刷新资料列表）
  const [importTasks, setImportTasks] = useState<ImportTask[]>([])
  // 全量资料（仅用于统计：侧栏每库数量、顶部总览）
  const [allDocs, setAllDocs] = useState<DocumentItem[]>([])
  // 批量操作模式（头部按钮开关，资料区据此显示复选框与批量操作栏）
  const [batchMode, setBatchMode] = useState(false)

  // 选中库持久化（空值不写入）
  useEffect(() => {
    if (selectedKb) localStorage.setItem(SELECTED_KB_KEY, selectedKb)
    else localStorage.removeItem(SELECTED_KB_KEY)
  }, [selectedKb])

  // 导入可见性持久化
  useEffect(() => {
    localStorage.setItem(VISIBILITY_KEY, uploadVisibility)
  }, [uploadVisibility])

  // 拉全量资料用于统计（失败静默：统计缺失不影响主流程）
  useEffect(() => {
    listDocuments('')
      .then(setAllDocs)
      .catch(() => setAllDocs([]))
  }, [docRefreshKey])

  useEffect(() => {
    const loadKbList = async () => {
      setKbLoading(true)
      try {
        const bases = await listKnowledgeBases()
        setKbList(bases)
        // 选中值失效（首次进入 / 库被删）时回落到第一个库
        if (!selectedKb || !bases.some((b) => b.name === selectedKb)) {
          setSelectedKb(bases[0]?.name ?? '')
        }
      } catch (e) {
        setKbErr(e instanceof Error ? e.message : '加载知识库失败')
      } finally {
        setKbLoading(false)
      }
    }
    loadKbList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 每个知识库的 资料数 / 切片数
  const statByKb = useMemo(() => buildStatByKb(allDocs), [allDocs])
  const totalDocs = allDocs.length
  const totalChunks = allDocs.reduce((s, d) => s + (d.chunk_count ?? 0), 0)
  const curStat = statByKb.get(selectedKb || 'default') ?? EMPTY_STAT

  /** 新建知识库：成功后自动选中；失败时写入错误提示并向上抛出（保留输入框内容） */
  const handleCreateKb = async (name: string) => {
    try {
      const created = await createKnowledgeBase(name)
      setKbList((prev) => [...prev.filter((b) => b.name !== created.name), created])
      setSelectedKb(created.name)
      setKbErr('')
    } catch (e) {
      setKbErr(e instanceof Error ? e.message : '创建失败')
      throw e
    }
  }

  /** 重命名知识库：同步列表与选中值，并刷新统计（资料归属已随库名改写） */
  const handleRenameKb = async (oldName: string, newName: string) => {
    try {
      await renameKnowledgeBase(oldName, newName)
      setKbList((prev) =>
        prev.map((b) => (b.name === oldName ? { ...b, name: newName } : b)),
      )
      // 重命名的是当前选中库时，同步选中值与其持久化键
      setSelectedKb((cur) => (cur === oldName ? newName : cur))
      setKbErr('')
      setDocRefreshKey((k) => k + 1)
    } catch (e) {
      setKbErr(e instanceof Error ? e.message : '重命名失败')
      throw e
    }
  }

  /** 删除知识库：库内资料已由后端迁移到默认库，前端回落选中第一个库 */
  const handleDeleteKb = async (name: string) => {
    try {
      await deleteKnowledgeBase(name)
      setKbList((prev) => {
        const next = prev.filter((b) => b.name !== name)
        // 删除的是当前选中库时，回落到剩余第一个（默认库始终置顶）
        setSelectedKb((cur) => (cur === name ? (next[0]?.name ?? '') : cur))
        return next
      })
      setKbErr('')
      setDocRefreshKey((k) => k + 1)
    } catch (e) {
      setKbErr(e instanceof Error ? e.message : '删除失败')
      throw e
    }
  }

  return (
    <div className="kb-app">
      <main className="kb-main">
        <div className="kb-split">
          <KnowledgeSidebar
            kbList={kbList}
            selectedKb={selectedKb}
            statByKb={statByKb}
            totalDocs={totalDocs}
            totalChunks={totalChunks}
            loading={kbLoading}
            error={kbErr}
            onSelect={setSelectedKb}
            onCreate={handleCreateKb}
            onRename={handleRenameKb}
            onDelete={handleDeleteKb}
            onBack={onBack}
          />

          {/* 右侧列：所选知识库对应的知识内容 */}
          <section className="kb-content">
            <KnowledgeHeader
              selectedKb={selectedKb}
              stat={curStat}
              batchMode={batchMode}
              canBatch={curStat.docs > 0}
              onToggleBatch={() => setBatchMode((v) => !v)}
              onImport={() => setShowUpload(true)}
            />
            {/* 资料区：紧贴头部下方，属于头部区域而非滚动主体 */}
            <DocumentsSection
              username={username}
              isAdmin={isAdmin}
              kbFilter={selectedKb}
              refreshKey={docRefreshKey}
              batchMode={batchMode}
              onOpenUpload={() => setShowUpload(true)}
              onManageDoc={(item) => setManageItem(item)}
            />
            {/* 导入任务区：仅在有进行中/历史任务时占据主体部分 */}
            {importTasks.length > 0 && (
              <div className="kb-content-body">
                <ImportPanel
                  tasks={importTasks}
                  onTasksChange={setImportTasks}
                  onImportDone={() => setDocRefreshKey((k) => k + 1)}
                />
              </div>
            )}
          </section>
        </div>
      </main>

      <UploadPanel
        open={showUpload}
        onClose={() => setShowUpload(false)}
        kb={selectedKb}
        visibility={uploadVisibility}
        onVisibilityChange={setUploadVisibility}
        onUploaded={(created) => setImportTasks((prev) => [...prev, ...created])}
      />

      <DocManageDialog
        open={manageItem !== null}
        item={manageItem}
        kbList={kbList}
        currentUser={username}
        userRole={isAdmin ? 'admin' : 'member'}
        onClose={() => setManageItem(null)}
        onChanged={() => setDocRefreshKey((k) => k + 1)}
      />
    </div>
  )
}
