import { useEffect, useRef, useState } from 'react'
import { fetchImportStatus, uploadFiles } from '../api'
import { IMPORT_NODES, type ImportTask, type TaskStatus } from '../types'

const STATUS_TEXT: Record<TaskStatus, string> = {
  PENDING: '等待中',
  PROCESSING: '处理中',
  COMPLETED: '已完成',
  FAILED: '失败',
}

function StatusBadge({ status }: { status: TaskStatus }) {
  return <span className={`status-badge status-${status}`}>{STATUS_TEXT[status]}</span>
}

function TaskCard({ task }: { task: ImportTask }) {
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
      <div className="hint">task_id: {task.task_id}</div>
    </div>
  )
}

export default function ImportPanel() {
  const [files, setFiles] = useState<File[]>([])
  const [tasks, setTasks] = useState<ImportTask[]>([])
  const [uploading, setUploading] = useState(false)
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

  const handleUpload = async () => {
    if (!files.length) return
    setUploading(true)
    try {
      const ids = await uploadFiles(files)
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
            return { ...t, status: data.status, done_list: data.done_list, running_list: data.running_list }
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
          {tasks.map((t) => <TaskCard key={t.task_id} task={t} />)}
        </div>
      )}
    </div>
  )
}
