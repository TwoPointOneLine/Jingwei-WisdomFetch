import { useEffect, useRef, useState } from 'react'
import { fetchTaskResult, getAnonId, openSSE, submitFeedback, submitQuery } from '../api'
import type { ChatMessage, ChatSession } from '../types'
import ChatInput from './ChatInput'

interface ChatPanelProps {
  session: ChatSession
  sending: boolean
  username: string
  onChange: (messages: ChatMessage[]) => void
  onSendingChange: (sending: boolean) => void
}

export default function ChatPanel({
  session,
  sending,
  username,
  onChange,
  onSendingChange,
}: ChatPanelProps) {
  const boxRef = useRef<HTMLDivElement>(null)
  // 始终持有最新消息，避免流式快速 delta 时基于过期闭包导致内容丢失
  const messagesRef = useRef<ChatMessage[]>(session.messages)

  // 会话切换时同步最新消息到 ref（流式期间不被 session 闭包覆盖）
  useEffect(() => {
    messagesRef.current = session.messages
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.id])

  // 自动滚动到底部
  useEffect(() => {
    if (boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight
  }, [session.messages])

  const commitMessages = (messages: ChatMessage[]) => {
    messagesRef.current = messages
    onChange(messages)
  }

  const patchLast = (fn: (m: ChatMessage) => ChatMessage) => {
    const cur = messagesRef.current
    commitMessages(cur.map((m, i) => (i === cur.length - 1 ? fn(m) : m)))
  }

  const patchByIndex = (idx: number, fn: (m: ChatMessage) => ChatMessage) => {
    const cur = messagesRef.current
    commitMessages(cur.map((m, i) => (i === idx ? fn(m) : m)))
  }

  const ask = async (q: string, model: string) => {
    if (!q.trim() || sending) return
    onSendingChange(true)
    commitMessages([
      ...messagesRef.current,
      { role: 'user', content: q },
      { role: 'assistant', content: '', streaming: true, sources: [] },
    ])

    let taskId = ''
    let closed = false
    const close = () => {
      closed = true
    }

    // 打字机节流：delta 先进缓冲，定时刷帧到消息，保证逐字流式效果
    const pendingRef: string[] = []
    let typewriterId = 0
    const flushTypewriter = () => {
      typewriterId = window.setInterval(() => {
        const batch = pendingRef.splice(0, 1).join('')
        if (batch) {
          patchLast((m) => ({ ...m, content: m.content + batch }))
        }
      }, 35)
    }
    const stopTypewriter = () => {
      if (typewriterId) window.clearInterval(typewriterId)
      typewriterId = 0
      // 清空残留缓冲
      if (pendingRef.length) {
        const rest = pendingRef.splice(0).join('')
        if (rest) patchLast((m) => ({ ...m, content: m.content + rest }))
      }
    }

    // 60 秒 SSE 超时兜底：若仍未收到 final，主动拉取 task_result
    let timeoutTriggered = false
    const timeoutId = window.setTimeout(async () => {
      if (closed) return
      timeoutTriggered = true
      stopTypewriter()
      try {
        const r = await fetchTaskResult(taskId)
        const answer = (r as { llm_output?: string; citations?: import('../types').Citation[] }).llm_output
        const citations = (r as { citations?: import('../types').Citation[] }).citations
        if (answer) {
          patchLast((m) => ({ ...m, content: answer, citations, streaming: false }))
        }
      } catch (e) {
        // ignore
      } finally {
        onSendingChange(false)
      }
    }, 60_000)

    try {
      const submitRes = await submitQuery({
        session_id: session.id,
        query: q,
        need_stream_output: true,
        model: model || null,
        username: username || null,
      })
      taskId = submitRes?.task_id || ''

      flushTypewriter()
      openSSE(session.id, {
        onDelta: (text) => {
          // 入缓冲，由打字机定时刷帧
          pendingRef.push(text)
        },
        onFinal: (answer, citations) => {
          if (timeoutTriggered) return
          window.clearTimeout(timeoutId)
          stopTypewriter()
          patchLast((m) => ({
            ...m,
            content: answer || m.content,
            citations,
            streaming: false,
          }))
          onSendingChange(false)
          close()
        },
        onError: (message) => {
          if (timeoutTriggered) return
          window.clearTimeout(timeoutId)
          stopTypewriter()
          // EventSource onerror 在连接异常或服务端正常关闭时都会触发。
          // 若已有内容（final/delta 已收齐），仅停止 streaming，不覆盖为错误。
          const cur = messagesRef.current
          const last = cur[cur.length - 1]
          if (last && last.content) {
            patchLast((m) => ({ ...m, streaming: false }))
          } else if (message && message !== "连接中断") {
            // 真正无内容且非正常关闭的连接错误
            patchLast((m) => ({
              ...m,
              content: `[错误] ${message}`,
              streaming: false,
            }))
          } else {
            patchLast((m) => ({ ...m, streaming: false }))
          }
          onSendingChange(false)
          close()
        },
      })
    } catch (e) {
      window.clearTimeout(timeoutId)
      stopTypewriter()
      patchLast((m) => ({
        ...m,
        content: `[请求失败] ${e instanceof Error ? e.message : e}`,
        streaming: false,
      }))
      onSendingChange(false)
    }
  }

  return (
    <div className="chat-main">
      {/* 对话内容区 */}
      <div className="chat-box" ref={boxRef}>
        {session.messages.length === 0 && (
          <div className="welcome">
            <div className="welcome-icon">📚</div>
            <div className="welcome-title">你好！我是精卫知识助手</div>
            <div className="hint">例如：RS-12 万用表怎么测电阻？</div>
          </div>
        )}
        {session.messages.map((m, i) => (
          <div className={`msg ${m.role}`} key={i}>
            <div className="msg-role">{m.role === 'user' ? '你' : '助手'}</div>
            <div className="msg-content">
              {m.content}
              {m.streaming && <span className="cursor" />}
            </div>

            {/* FR-CITE-02：结构化来源引用（可信标记 / 可展开）。优先 citations，兼容旧 sources */}
            {m.role === 'assistant' && (m.citations?.length || m.sources?.length) ? (
              <CitationList citations={m.citations} legacySources={m.sources} />
            ) : null}

            {/* FR-COMP-05：对助手回答提供反馈（已反馈后禁用） */}
            {m.role === 'assistant' && !m.streaming && (
              <FeedbackBar
                sessionId={session.id}
                messageId={String(i)}
                username={username}
                given={!!m.feedbackGiven}
                onGiven={() =>
                  patchByIndex(i, (mm) => ({ ...mm, feedbackGiven: true }))
                }
              />
            )}
          </div>
        ))}
      </div>

      {/* 消息输入区（独立组件：文件上传 + 模型选择 + 文本输入） */}
      <ChatInput sending={sending} onSend={ask} />
    </div>
  )
}

/** FR-CITE-02：结构化来源引用展示（可信标记 / 可展开） */
function CitationList({
  citations,
  legacySources,
}: {
  citations?: import('../types').Citation[]
  legacySources?: Array<{ title?: string; url?: string; chunk_id?: string; content?: string }>
}) {
  const [open, setOpen] = useState(false)
  if (citations && citations.length) {
    return (
      <div className="source-box">
        <div className="source-title" onClick={() => setOpen((o) => !o)}>
          参考来源（{citations.length}）{open ? '▲' : '▼'}
        </div>
        {open &&
          citations.map((c) => (
            <div className={`source-item${c.external ? ' external' : ''}`} key={c.index}>
              <span className="src-idx">{c.index}.</span>
              <span className="src-title">{c.title || c.product_name || c.source_file || '未知来源'}</span>
              {c.external && <span className="tag tag-external">外部</span>}
              {c.risk_level && c.risk_level !== '未提及' && (
                <span className="tag tag-risk">风险 {c.risk_level}</span>
              )}
              {c.content_type && <span className="tag">{c.content_type}</span>}
              <div className="src-meta">
                {c.product_code && <span>代码 {c.product_code}</span>}
                {c.publish_date && <span>发布 {c.publish_date}</span>}
                {c.source_file && <span>文件 {c.source_file}</span>}
              </div>
            </div>
          ))}
      </div>
    )
  }
  // 兼容旧 sources
  if (legacySources && legacySources.length) {
    return (
      <div className="source-box">
        <div className="source-title">参考来源（{legacySources.length}）</div>
        {legacySources.map((s, j) => (
          <div className="source-item" key={j}>
            {s.title || s.url || s.chunk_id || (s.content ? s.content.slice(0, 60) : '')}
          </div>
        ))}
      </div>
    )
  }
  return null
}

/** FR-COMP-05：对助手回答的反馈（点赞 / 点踩 / 纠错） */
function FeedbackBar({
  sessionId,
  messageId,
  username,
  given,
  onGiven,
}: {
  sessionId: string
  messageId: string
  username: string
  given: boolean
  onGiven: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [err, setErr] = useState('')

  const send = async (rating: number, type: string) => {
    setBusy(true)
    setErr('')
    try {
      await submitFeedback({
        session_id: sessionId,
        message_id: messageId,
        rating,
        feedback_type: type,
        content: type === 'correction' ? text : undefined,
        username: username || undefined,
        anon_id: !username ? getAnonId() : undefined,
      })
      onGiven()
      setOpen(false)
      setText('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : '反馈失败')
    } finally {
      setBusy(false)
    }
  }

  if (given) {
    return <div className="feedback-bar done">已收到反馈，感谢</div>
  }
  return (
    <div className="feedback-bar">
      <button className="fb-btn" disabled={busy} onClick={() => send(1, 'like')}>
        👍 有用
      </button>
      <button className="fb-btn" disabled={busy} onClick={() => send(-1, 'dislike')}>
        👎 没用
      </button>
      <button className="fb-btn" disabled={busy} onClick={() => setOpen((o) => !o)}>
        ✏️ 纠错
      </button>
      {open && (
        <div className="fb-correction">
          <textarea
            placeholder="请描述问题或补充正确信息（可选）"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button className="btn primary" disabled={busy} onClick={() => send(0, 'correction')}>
            提交纠错
          </button>
        </div>
      )}
      {err && <div className="fb-err">{err}</div>}
    </div>
  )
}
