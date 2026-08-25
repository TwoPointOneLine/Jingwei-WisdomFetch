interface ChatHeaderProps {
  title: string
  meta?: string
  showUpload?: boolean
  onUpload?: () => void
}

/**
 * 右侧顶部标题栏（独立组件）：对话标题居中，右侧为「上传知识库」按钮。
 *
 * 通过三栏布局实现标题绝对居中：左/右侧各占等宽容器，中间标题居中。
 */
export default function ChatHeader({ title, meta, showUpload = true, onUpload }: ChatHeaderProps) {
  return (
    <header className="chat-titlebar">
      {/* 左侧占位（保持标题居中） */}
      <div className="titlebar-side" />

      {/* 中间标题（居中） */}
      <div className="titlebar-center">
        <div className="chat-title">{title}</div>
        {meta && <div className="chat-meta">{meta}</div>}
      </div>

      {/* 右侧：上传知识库按钮 */}
      <div className="titlebar-side titlebar-right">
        {showUpload && (
          <button className="btn primary upload-kb-btn" onClick={onUpload}>
            📤 上传知识库
          </button>
        )}
      </div>
    </header>
  )
}
