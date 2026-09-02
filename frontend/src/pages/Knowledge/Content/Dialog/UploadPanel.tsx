import { useRef, useState } from 'react'
import { uploadFiles } from '../../../../api'
import { useSupportedFormats } from '../../../../formats'
import type { ImportTask, RejectedFile, Visibility } from '../../../../types'

/**
 * 上传组件（对话框模式）：仅保留第一步「添加文件」。
 * 目标知识库与可见性由主页面（知识选项卡）提前选择，通过 props 传入。
 */
const VIS_OPTIONS: { value: Visibility; icon: string; label: string }[] = [
  { value: 'private', icon: '🔒', label: '私有' },
  { value: 'team', icon: '👥', label: '团队可见' },
  { value: 'shared', icon: '🌐', label: '共享' },
]

export default function UploadPanel({
  kb,
  visibility,
  onVisibilityChange,
  onUploaded,
  open = false,
  onClose,
}: {
  kb: string
  visibility: Visibility
  onVisibilityChange?: (v: Visibility) => void
  onUploaded: (tasks: ImportTask[]) => void
  open?: boolean
  onClose?: () => void
}) {
  const [files, setFiles] = useState<File[]>([])
  const [dragover, setDragover] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [rejected, setRejected] = useState<RejectedFile[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  // G-01：accept 与提示文案跟随后端白名单（单一事实来源）
  const { accept, display } = useSupportedFormats()

  if (!open) return null

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
    setRejected([])
    try {
      const { task_ids: ids, rejected: bad } = await uploadFiles(files, visibility, kb)
      const created: ImportTask[] = ids.map((tid, i) => ({
        task_id: tid,
        filename: files[i]?.name ?? tid,
        status: 'PROCESSING',
        done_list: [],
        running_list: [],
      }))
      onUploaded(created)
      // G-01：部分文件被拒时保留在列表并展示原因，不静默丢弃
      const badNames = new Set(bad.map((r) => r.filename))
      setFiles((prev) => prev.filter((f) => badNames.has(f.name)))
      setRejected(bad)
      if (fileInputRef.current) fileInputRef.current.value = ''
      if (!bad.length) onClose?.() // 全部成功才关闭弹窗
    } catch (e) {
      alert(`上传失败：${e instanceof Error ? e.message : e}`)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="upload-modal-overlay" onClick={onClose}>
      <div className="upload-modal" onClick={(e) => e.stopPropagation()}>
        <div className="upload-modal-head">
          <h3 className="kb-section-title">
            <span className="kb-section-num">📥</span>
            <span>知识导入</span>
          </h3>
          <button className="upload-modal-close" type="button" onClick={onClose} title="关闭">
            ×
          </button>
        </div>

        <div className="upload-modal-body">
          <div className="kb-section-head" style={{ marginBottom: 0 }}>
            <h3 className="kb-section-title">
              <span className="kb-section-num">1</span>
              <span>添加文件</span>
            </h3>
            <span className="kb-section-hint">拖拽或点击选择，支持 {display}，可多选</span>
          </div>

          <div
            className={`dropzone foot-drop${dragover ? ' dragover' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragover(true) }}
            onDragLeave={() => setDragover(false)}
            onDrop={(e) => { e.preventDefault(); setDragover(false); addFiles(e.dataTransfer.files) }}
          >
            <div className="dz-icon">📥</div>
            <div className="dz-title">{dragover ? '松开以上传文件' : '拖拽文件到此处，或点击选择'}</div>
            <div className="dz-sub">支持 {display} 文档，可多选</div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={accept}
              style={{ display: 'none' }}
              onChange={(e) => e.target.files && addFiles(e.target.files)}
            />
          </div>

          {/* G-01：被拒文件原因展示（否则用户以为"上传成功却查不到"） */}
          {rejected.length > 0 && (
            <div className="upload-rejected">
              <div className="upload-rejected-title">
                ⚠️ {rejected.length} 个文件未能导入
              </div>
              {rejected.map((r) => (
                <div className="upload-rejected-item" key={r.filename}>
                  <span className="upload-rejected-name">{r.filename}</span>
                  <span className="upload-rejected-reason">{r.reason}</span>
                </div>
              ))}
            </div>
          )}

          {/* 导入设置：目标库（跟随左侧选中库，只读）+ 可见性（可切换并记忆） */}
          <div className="upload-settings">
            <div className="upload-setting-row">
              <span className="upload-setting-label">导入目标库</span>
              <span className="upload-setting-kb">
                <span className="upload-setting-kb-icon">📁</span>
                <span className="upload-setting-kb-name" title={kb}>
                  {kb || '默认库'}
                </span>
              </span>
            </div>
            <div className="upload-setting-row">
              <span className="upload-setting-label">可见性</span>
              <div className="upload-vis-group">
                {VIS_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={`upload-vis-btn${visibility === opt.value ? ' active' : ''}`}
                    onClick={() => onVisibilityChange?.(opt.value)}
                  >
                    <span className="upload-vis-icon">{opt.icon}</span>
                    <span>{opt.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {files.length > 0 && (
            <div className="kb-section">
              <div className="kb-section-head">
                <h3 className="kb-section-title">
                  <span className="kb-section-num">⇧</span>
                  <span>待上传文件（{files.length}）</span>
                </h3>
                <span className="kb-section-hint">
                  共 {(files.reduce((s, f) => s + f.size, 0) / 1024).toFixed(1)} KB
                </span>
              </div>
              <div className="file-list">
                {files.map((f, i) => (
                  <div className="file-item" key={`${f.name}:${f.size}`}>
                    <span className="file-icon">📄</span>
                    <div className="file-info">
                      <span className="file-name">{f.name}</span>
                      <span className="file-size">{(f.size / 1024).toFixed(1)} KB</span>
                    </div>
                    <button className="file-remove" onClick={() => removeFile(i)} title="移除">
                      ×
                    </button>
                  </div>
                ))}
              </div>
              <div className="kb-actions">
                <button className="btn primary kb-upload-btn" onClick={handleUpload} disabled={uploading}>
                  {uploading ? <span className="kb-spinner" /> : <span>🚀</span>}
                  <span>{uploading ? '上传中...' : `上传到 ${kb || '默认库'}`}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
