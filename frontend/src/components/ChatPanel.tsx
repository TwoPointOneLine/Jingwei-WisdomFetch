import { useEffect, useRef } from 'react'
import { fetchTaskResult, openSSE, submitQuery } from '../api'
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
        const answer = (r as { llm_output?: string }).llm_output
        if (answer) {
          patchLast((m) => ({ ...m, content: answer, streaming: false }))
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
        onFinal: (answer) => {
          if (timeoutTriggered) return
          window.clearTimeout(timeoutId)
          stopTypewriter()
          patchLast((m) => ({
            ...m,
            content: answer || m.content,
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
            <div className="welcome-title">你好！我是掌柜智库知识助手</div>
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
            {m.sources && m.sources.length > 0 && (
              <div className="source-box">
                <div className="source-title">参考来源</div>
                {m.sources.map((s, j) => (
                  <div className="source-item" key={j}>
                    {s.title || s.url || s.chunk_id || (s.content ? s.content.slice(0, 60) : '')}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 消息输入区（独立组件：文件上传 + 模型选择 + 文本输入） */}
      <ChatInput sending={sending} onSend={ask} />
    </div>
  )
}
