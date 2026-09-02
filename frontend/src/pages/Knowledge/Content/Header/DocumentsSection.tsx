import { useEffect, useMemo, useState } from 'react'
import { listDocuments, listKnowledgeBases, offlineDocument } from '../../../../api'
import type { DocumentItem, KnowledgeBase } from '../../../../types'
import { kbDisplayName } from '../../knowledgeUtils'
import Icon from '../../../../components/Icon'
import { BookCard, AddBookCard } from '../Main/BookCard'
import { BatchBar, type BatchAction } from './BatchBar'

/** FR-IMP-05 + 普通用户知识库隔离：已导入资料管理（按知识库分组、每组可折叠） */
function DocumentsSection({
  username,
  isAdmin,
  kbFilter,
  refreshKey,
  batchMode,
  onOpenUpload,
  onManageDoc,
  onCountChange,
}: {
  username: string
  isAdmin: boolean
  kbFilter: string
  refreshKey?: number
  /** 是否处于批量操作模式（由页面级控制，与头部按钮联动） */
  batchMode?: boolean
  onOpenUpload?: () => void
  onManageDoc?: (item: DocumentItem) => void
  onCountChange?: (count: number) => void
}) {
  const [items, setItems] = useState<DocumentItem[]>([])
  const [kbList, setKbList] = useState<KnowledgeBase[]>([])
  const [err, setErr] = useState('')
  // 批量操作的成功回执（与 err 分开，避免错误态与成功态互相覆盖）
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')
  // 批量模式：选中的资料名集合 + 正在执行的批量动作
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [batchRunning, setBatchRunning] = useState<BatchAction | null>(null)

  // 加载知识库列表（用于分组排序，与上传组件相互独立加载）
  useEffect(() => {
    listKnowledgeBases().then(setKbList).catch(() => {})
  }, [])

  const reload = async () => {
    try {
      const list = await listDocuments(kbFilter)
      setItems(list)
      onCountChange?.(list.length)
    } catch (e) {
      setErr(e instanceof Error ? e.message : '获取资料失败')
    }
  }

  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kbFilter, refreshKey])

  // 退出批量模式时清空选择；切换知识库时同样清空（避免跨库残留选中）
  useEffect(() => {
    setSelected(new Set())
  }, [batchMode, kbFilter])

  const canManage = (it: DocumentItem) => isAdmin || (it.owner ?? '') === username

  /** 可批量操作的资料（无权限的条目不可选）。此处内联 canManage 的判断逻辑，
   *  避免 useMemo 依赖一个每次渲染都重建的函数而失去 memo 意义。 */
  const selectableItems = useMemo(
    () => items.filter((it) => isAdmin || (it.owner ?? '') === username),
    [items, isAdmin, username],
  )
  const selectedItems = useMemo(
    () => selectableItems.filter((it) => selected.has(it.item_name)),
    [selectableItems, selected],
  )
  const allSelected =
    selectableItems.length > 0 && selectedItems.length === selectableItems.length

  const toggleSelect = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }
  const toggleSelectAll = () => {
    setSelected(allSelected ? new Set() : new Set(selectableItems.map((it) => it.item_name)))
  }

  const handleOffline = async (name: string) => {
    if (!confirm(`确认下线资料「${name}」？其全部切片将从知识库移除。`)) return
    setBusy(name)
    try {
      await offlineDocument(name)
      await reload()
    } catch (e) {
      setErr(e instanceof Error ? e.message : '下线失败')
    } finally {
      setBusy('')
    }
  }

  /**
   * 批量执行：并发调用单条接口，结束后汇总成功/失败数。单次失败不影响其余条目。
   * @param expect 期望后端实际返回的值（仅可见性操作需要）。用于识别「请求成功但值被改写」的静默降级。
   */
  const runBatch = async (
    action: BatchAction,
    label: string,
    fn: (name: string) => Promise<unknown>,
    expect?: string,
  ) => {
    const targets = selectedItems
    if (!targets.length) return
    if (
      !confirm(
        action === 'offline'
          ? `确认下线选中的 ${targets.length} 份资料？其全部切片将从知识库移除，此操作不可撤销。`
          : `确认将选中的 ${targets.length} 份资料${label}？`,
      )
    )
      return
    setBatchRunning(action)
    setErr('')
    setNotice('')
    try {
      const results = await Promise.allSettled(targets.map((it) => fn(it.item_name)))
      const failed = results.filter((r) => r.status === 'rejected').length
      const ok = results.length - failed
      // 请求成功但后端返回的实际值与期望不符（如被降级），视为「未生效」并计入 warn
      const degraded =
        expect === undefined
          ? 0
          : results.filter(
              (r) => r.status === 'fulfilled' && typeof r.value === 'string' && r.value !== expect,
            ).length
      setSelected(new Set())
      await reload()
      if (failed > 0 || degraded > 0) {
        const firstErr = results.find((r) => r.status === 'rejected')
        const msg =
          firstErr && firstErr.status === 'rejected'
            ? firstErr.reason instanceof Error
              ? firstErr.reason.message
              : String(firstErr.reason)
            : ''
        const parts = [`成功 ${ok} 份`]
        if (failed > 0) parts.push(`失败 ${failed} 份`)
        if (degraded > 0) parts.push(`未生效 ${degraded} 份`)
        setErr(`批量${label}：${parts.join('，')}。${msg ? `首个错误：${msg}` : ''}`.trim())
      } else {
        setNotice(`已${label} ${ok} 份资料`)
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : `批量${label}失败`)
    } finally {
      setBatchRunning(null)
    }
  }

  // 按知识库分组（kb_name），保持 kbList 顺序，最后补未列出的库
  const groups: { kb: string; its: DocumentItem[] }[] = []
  const seen = new Set<string>()
  for (const b of kbList) {
    if (kbFilter && kbFilter !== b.name) continue
    const its = items.filter((it) => (it.kb_name || 'default') === b.name)
    groups.push({ kb: b.name, its })
    seen.add(b.name)
  }
  for (const it of items) {
    const kb = it.kb_name || 'default'
    if (seen.has(kb)) continue
    if (kbFilter && kbFilter !== kb) continue
    seen.add(kb)
    groups.push({ kb, its: items.filter((i) => (i.kb_name || 'default') === kb) })
  }

  return (
    <div className={`kb-section docs-col kb-content-docs${batchMode ? ' batch-open' : ''}`}>
      {/* 批量操作栏置于资料列表之前（DOM 顺序决定显示位置，CSS 只能控制吸顶行为） */}
      {batchMode && selectableItems.length > 0 && (
        <BatchBar
          allSelected={allSelected}
          toggleSelectAll={toggleSelectAll}
          selectedItems={selectedItems}
          selectableItems={selectableItems}
          batchRunning={batchRunning}
          runBatch={runBatch}
          kbList={kbList}
        />
      )}
      {/* 批量模式下无任何可管理资料时给出明确说明，避免「点了没反应」 */}
      {batchMode && selectableItems.length === 0 && items.length > 0 && (
        <div className="kb-inline-ok">
          <span>当前知识库没有你有权管理的资料，无法批量操作</span>
        </div>
      )}
      {/* 批量操作提示消息：显示在批量操作栏下方、资料列表上方 */}
      {err && (
        <div className="kb-inline-err">
          <span>⚠️ {err}</span>
          <button className="btn ghost" onClick={reload}>重试</button>
        </div>
      )}
      {notice && !err && (
        <div className="kb-inline-ok">
          <span>✅ {notice}</span>
          <button className="btn ghost" onClick={() => setNotice('')} type="button">关闭</button>
        </div>
      )}
      {items.length === 0 && !err ? (
        <div className="book-shelf empty-shelf">
          <AddBookCard onOpenUpload={onOpenUpload} />
        </div>
      ) : kbFilter ? (
        <div className="book-shelf">
          {items.map((it) => (
            <BookCard
              key={it.item_name}
              it={it}
              batchMode={!!batchMode}
              selected={selected.has(it.item_name)}
              manageable={canManage(it)}
              onToggleSelect={toggleSelect}
              onManageDoc={onManageDoc}
              onOffline={handleOffline}
              busyName={busy}
            />
          ))}
        </div>
      ) : (
        groups.map((g) => (
          <div className="kb-group" key={g.kb}>
            <div className="section-head-static kb-group-head">
              <span className="kb-group-icon">
                <Icon name={g.kb.startsWith('default@') ? 'home' : 'folder'} size={16} />
              </span>
              <span className="kb-group-name">{kbDisplayName(g.kb)}</span>
              <span className="kb-group-count">{g.its.length}</span>
            </div>
            <div className="kb-group-body">
              {g.its.length === 0 ? (
                <div className="book-shelf empty-shelf">
                  <AddBookCard onOpenUpload={onOpenUpload} />
                </div>
              ) : (
                <div className="book-shelf">
                  {g.its.map((it) => (
                    <BookCard
                      key={it.item_name}
                      it={it}
                      batchMode={!!batchMode}
                      selected={selected.has(it.item_name)}
                      manageable={canManage(it)}
                      onToggleSelect={toggleSelect}
                      onManageDoc={onManageDoc}
                      onOffline={handleOffline}
                      busyName={busy}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  )
}

export { DocumentsSection }
