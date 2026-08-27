import { useEffect, useRef, useState } from 'react'
import { fetchImportStatus, listDocuments, offlineDocument, retryImport, setDocumentVisibility, uploadFiles } from '../api'
import { IMPORT_NODES, type DocumentItem, type ImportTask, type TaskStatus, type Visibility } from '../types'

const STATUS_TEXT: Record<TaskStatus, string> = {
  PENDING: '等待中',
  PROCESSING: '处理中',
  COMPLETED: '已完成',
  FAILED: '失败',
}

function StatusBadge({ status }: { status: TaskStatus }) {
  return <span className={`status-badge status-${status}`}>{STATUS_TEXT[status]}</span>
}

function TaskCard({ task, onRetry }: { task: ImportTask; onRetry: (id: string) => void }) {
  const done = new Set(task.done_list)
  const running = new Set(task.running_list)
  return (
    <div className="task">
      <div className="task-head">
        <span className="task-fname">{task.filename}</span>
        <StatusBadge status={task.status} />
      </div>
      <div className="node-progress">
        {IMPORT_NODES.map((n) => (
          <span
            key={n}
            className={
              'node-chip' +
              (done.has(n) ? ' done' : running.has(n) ? ' running' : '')
            }
          >
            {n}
          </span>
        ))}
      </div>
      {/* FR-IMP-04：失败原因结构化展示 + 重试 */}
      {task.status === 'FAILED' && (
        <div className="task-error">
          <div className="err-msg">失败原因：{task.error || '未知错误'}</div>
          <button className="btn ghost" onClick={() => onRetry(task.task_id)}>
            重试
          </button>
        </div>
      )}
      <div className="hint">task_id: {task.task_id}</div>
    </div>
  )
}

/** FR-IMP-05 + 普通用户知识库隔离：已导入资料管理（按权限只展示「自己的 + 共享的」） */
function DocumentsSection({ username, isAdmin }: { username: string; isAdmin: boolean }) {
  const [items, setItems] = useState<DocumentItem[]>([])
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState('')

  const reload = async () => {
    try {
      setItems(await listDocuments())
    } catch (e) {
      setErr(e instanceof Error ? e.message : '获取资料失败')
    }
  }
  useEffect(() => {
    reload()
  }, [])

  const canManage = (it: DocumentItem) => isAdmin || (it.owner ?? '') === username

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

  // 可见性三态循环：private -> team -> shared -> private
  const handleToggleVisibility = async (it: DocumentItem) => {
    if (!canManage(it)) return
    const order: Visibility[] = ['private', 'team', 'shared']
    const cur = (it.visibility ?? 'private') as Visibility
    const next = order[(order.indexOf(cur) + 1) % order.length]
    setBusy(it.item_name)
    try {
      await setDocumentVisibility(it.item_name, next)
      await reload()
    } catch (e) {
      setErr(e instanceof Error ? e.message : '切换可见性失败')
    } finally {
      setBusy('')
    }
  }

  const visLabel = (v?: Visibility) =>
    v === 'shared' ? '共享' : v === 'team' ? '团队可见' : '私有'
  const visCls = (v?: Visibility) =>
    v === 'shared' ? 'vis-shared' : v === 'team' ? 'vis-team' : 'vis-private'
  // 三态循环：私有 → 团队 → 共享 → 私有
  const nextVisLabel = (v?: Visibility) =>
    v === 'private' ? '团队可见' : v === 'team' ? '共享' : '私有'

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 className="card-title">已导入资料（{items.length}）</h3>
      {err && <div className="fb-err">{err}</div>}
      {items.length === 0 && <div className="hint">暂无已导入资料</div>}
      {items.map((it) => {
        const isShared = it.visibility === 'shared'
        return (
          <div className="doc-item" key={it.item_name}>
            <div className="doc-main">
              <span className="doc-name">{it.item_name}</span>
              <span className={`vis-badge ${visCls(it.visibility)}`}>
                {visLabel(it.visibility)}
              </span>
              <span className="doc-meta">
                {it.chunk_count} 切片
                {it.owner ? ` · 归属 ${it.owner}` : ''}
                {it.product_name ? ` · ${it.product_name}` : ''}
                {it.publish_date ? ` · ${it.publish_date}` : ''}
              </span>
              <span className="doc-files">{it.source_files.join(', ')}</span>
            </div>
            <div className="doc-actions">
              {/* 仅本人或管理员可切换可见性 / 下线 */}
              {canManage(it) ? (
                <>
                  <button
                    className="btn ghost"
                    disabled={busy === it.item_name}
                    onClick={() => handleToggleVisibility(it)}
                    title="点击循环切换：私有 → 团队 → 共享"
                  >
                    {busy === it.item_name ? '...' : `转「${nextVisLabel(it.visibility)}」`}
                  </button>
                  <button
                    className="btn ghost"
                    disabled={busy === it.item_name}
                    onClick={() => handleOffline(it.item_name)}
                  >
                    {busy === it.item_name ? '下线中...' : '下线'}
                  </button>
                </>
              ) : (
                <span className="hint">{isShared ? '全员共享' : it.visibility === 'team' ? '团队共享' : '他人资料'}</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function ImportPanel({ isAdmin = false, username = '' }: { isAdmin?: boolean; username?: string }) {
  const [files, setFiles] = useState<File[]>([])
  const [tasks, setTasks] = useState<ImportTask[]>([])
  const [uploading, setUploading] = useState(false)
  const [visibility, setVisibility] = useState<Visibility>('private')
  const [dragover, setDragover] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const addFiles = (list: FileList | File[]) => {
    const arr = Array.from(list)
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`))
      return [...prev, ...arr.filter((f) => !seen.has(`${f.name}:${f.size}`))]
    })
  }

  const removeFile = (idx: number) => setFiles((prev) => prev.filter((_, i) => i !== idx))

  // 失败任务重试
  const handleRetry = async (taskId: string) => {
    try {
      await retryImport(taskId)
      setTasks((prev) =>
        prev.map((t) =>
          t.task_id === taskId ? { ...t, status: 'PROCESSING', done_list: [], running_list: [], error: null } : t,
        ),
      )
    } catch (e) {
      alert(`重试失败：${e instanceof Error ? e.message : e}`)
    }
  }

  const handleUpload = async () => {
    if (!files.length) return
    setUploading(true)
    try {
      const ids = await uploadFiles(files, visibility)
      const created: ImportTask[] = ids.map((tid, i) => ({
        task_id: tid,
        filename: files[i]?.name ?? tid,
        status: 'PROCESSING',
        done_list: [],
        running_list: [],
      }))
      setTasks((prev) => [...created, ...prev])
      setFiles([])
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (e) {
      alert(`上传失败：${e instanceof Error ? e.message : e}`)
    } finally {
      setUploading(false)
    }
  }

  // 轮询任务状态
  useEffect(() => {
    if (!tasks.length) return
    const timer = setInterval(async () => {
      const updated = await Promise.all(
        tasks.map(async (t) => {
          try {
            const data = await fetchImportStatus(t.task_id)
            return { ...t, status: data.status, done_list: data.done_list, running_list: data.running_list, error: data.error }
          } catch {
            return t
          }
        }),
      )
      setTasks(updated)
    }, 2000)
    return () => clearInterval(timer)
  }, [tasks.length]) // 仅当任务数量变化时重建轮询

  return (
    <div className="panel">
      <div
        className={`dropzone${dragover ? ' dragover' : ''}`}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragover(true) }}
        onDragLeave={() => setDragover(false)}
        onDrop={(e) => { e.preventDefault(); setDragover(false); addFiles(e.dataTransfer.files) }}
      >
        <div className="dz-title">拖拽文件到此处，或点击选择</div>
        <div className="dz-sub">支持 PDF / Markdown 文档，可多选</div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.md,.markdown"
          style={{ display: 'none' }}
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {/* 可见性选择：私有（仅自己）/ 团队可见（同团队成员共享检索）/ 共享（全员检索） */}
      <div className="vis-select">
        <span className="vis-label">资料可见性：</span>
        <label className={visibility === 'private' ? 'vis-opt active' : 'vis-opt'}>
          <input
            type="radio"
            name="vis"
            checked={visibility === 'private'}
            onChange={() => setVisibility('private')}
          />
          私有（仅自己可见/可检索）
        </label>
        <label
          className={visibility === 'team' ? 'vis-opt active' : 'vis-opt'}
          title={!username ? '需登录且属于某团队' : ''}
        >
          <input
            type="radio"
            name="vis"
            checked={visibility === 'team'}
            onChange={() => setVisibility('team')}
          />
          团队可见（同团队成员可检索）
        </label>
        <label className={visibility === 'shared' ? 'vis-opt active' : 'vis-opt'}>
          <input
            type="radio"
            name="vis"
            checked={visibility === 'shared'}
            onChange={() => setVisibility('shared')}
          />
          共享（全员可检索）
        </label>
      </div>
      {visibility === 'team' && !username && (
        <div className="hint" style={{ marginTop: 6 }}>请先登录后再上传团队资料。</div>
      )}

      {files.length > 0 && (
        <div className="file-list">
          {files.map((f, i) => (
            <div className="file-item" key={`${f.name}:${f.size}`}>
              <span className="file-name">{f.name}</span>
              <span className="file-size">{(f.size / 1024).toFixed(1)} KB</span>
              <button className="btn ghost" onClick={() => removeFile(i)}>
                移除
              </button>
            </div>
          ))}
          <button className="btn primary" style={{ marginTop: 12 }} disabled={uploading} onClick={handleUpload}>
            {uploading ? '上传中...' : '上传并开始导入'}
          </button>
        </div>
      )}

      {tasks.length > 0 && (
        <div className="card">
          <h3 className="card-title">导入任务</h3>
          {tasks.map((t) => (
            <TaskCard key={t.task_id} task={t} onRetry={handleRetry} />
          ))}
        </div>
      )}

      {/* FR-IMP-05：已导入资料管理（普通用户仅见自己 + 共享的） */}
      <DocumentsSection username={username} isAdmin={isAdmin} />
    </div>
  )
}
