import { useEffect, useRef, useState } from 'react'
import { fetchModels, uploadFiles } from '../api'
import type { ChatModel } from '../types'

interface ChatInputProps {
  sending: boolean
  onSend: (text: string, model: string) => void
}

export default function ChatInput({ sending, onSend }: ChatInputProps) {
  const [text, setText] = useState('')
  const [models, setModels] = useState<ChatModel[]>([])
  const [model, setModel] = useState('')
  const [showModelPicker, setShowModelPicker] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // 输入框根据内容自动增高（不超过 max-height）
  const autoResize = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  // 加载模型列表（默认选中「自动」）
  useEffect(() => {
    fetchModels()
      .then((data) => {
        setModels(data.models || [])
        // 默认「自动」：不预设具体模型，由后端选择默认模型
        setModel('')
      })
      .catch(() => {
        setModels([
          { id: 'qwen-plus', name: 'qwen-plus', description: '通用对话模型' },
          { id: 'qwen-vl-max', name: 'qwen-vl-max', description: '多模态视觉模型' },
        ])
        setModel('')
      })
  }, [])

  const handleSend = () => {
    const q = text.trim()
    if (!q || sending) return
    setText('')
    onSend(q, model)
    // 发送后重置输入框高度
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleFile = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    const list = Array.from(files)
    setUploading(true)
    setUploadMsg(null)
    try {
      const ids = await uploadFiles(list)
      setUploadMsg({
        ok: true,
        text: `已上传 ${list.length} 个文件${ids.length ? `（${ids.length} 个任务）` : ''}`,
      })
    } catch (e) {
      setUploadMsg({ ok: false, text: `上传失败：${e instanceof Error ? e.message : e}` })
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
      setTimeout(() => setUploadMsg(null), 4000)
    }
  }

  return (
    <div className="input-bar">
      {/* 一体化输入卡片：上文本、下工具行 */}
      <div className="ai-input-card">
        {/* 文本输入区（自动增高） */}
        <textarea
          ref={textareaRef}
          className="ai-input-textarea"
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            autoResize()
          }}
          onInput={autoResize}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
          placeholder="和精卫说点什么..."
          disabled={sending}
          rows={1}
        />

        {/* 工具行：左模型 / 右上传+发送 */}
        <div className="ai-input-tools">
          <div className="ai-input-tools-left">
            {/* 模型选择（按钮 + 弹窗） */}
            <div className="model-picker-wrap">
              <button
                className="ai-model-btn"
                type="button"
                onClick={() => setShowModelPicker((v) => !v)}
                title="选择对话模型"
              >
                {model ? models.find((m) => m.id === model)?.name || model : 'Auto'}
                <span className="ai-model-caret">▾</span>
              </button>

              {showModelPicker && (
                <>
                  <div className="model-picker-backdrop" onClick={() => setShowModelPicker(false)} />
                  <div className="model-picker">
                    <div className="model-picker-title">选择模型</div>
                    <button
                      className={`model-option${model === '' ? ' active' : ''}`}
                      onClick={() => {
                        setModel('')
                        setShowModelPicker(false)
                      }}
                    >
                      <span className="model-option-name">Auto</span>
                      <span className="model-option-desc">由系统默认选择</span>
                    </button>
                    {models.map((m) => (
                      <button
                        key={m.id}
                        className={`model-option${model === m.id ? ' active' : ''}`}
                        onClick={() => {
                          setModel(m.id)
                          setShowModelPicker(false)
                        }}
                      >
                        <span className="model-option-name">{m.name}</span>
                        {m.description && (
                          <span className="model-option-desc">{m.description}</span>
                        )}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
            {uploading && <span className="ai-uploading">上传中...</span>}
            {uploadMsg && (
              <span className={`ai-upload-msg ${uploadMsg.ok ? 'ok' : 'err'}`}>
                {uploadMsg.text}
              </span>
            )}
          </div>

          <div className="ai-input-tools-right">
            {/* 上传文件（加号图标，位于发送左边） */}
            <button
              className="ai-icon-btn"
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              title="上传文件到知识库"
            >
              ＋
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.md,.markdown,.txt,.doc,.docx"
              style={{ display: 'none' }}
              onChange={(e) => handleFile(e.target.files)}
            />
            <button
              className="ai-send-btn"
              type="button"
              onClick={handleSend}
              disabled={sending || !text.trim()}
              title="发送"
            >
              ↑
            </button>
          </div>
        </div>
      </div>

      {/* 底部提示 */}
      <div className="input-hint">内容由 AI 生成，仅供参考</div>
    </div>
  )
}
