/**
 * 掌柜智库前端 · API 客户端
 *
 * 阶段4：全部请求经网关统一入口（8080），由网关负责路由转发与鉴权前置：
 *   /api/import/*  ->  导入服务 (8081)
 *   /api/query/*   ->  查询服务 (8082)
 *   /api/auth/*    ->  认证服务 (8083)
 *   /api/user/*    ->  用户服务 (8084)
 */
import type {
  ApiResponse,
  ImportStatusResponse,
  ModelListData,
  QueryRequest,
  QuerySubmitData,
  TaskResultData,
  UploadResponse,
} from './types'

/**
 * 环境说明：
 * - DEV（Vite dev server，端口 5173）：走 /api/import、/api/query、/api/auth，由 Vite 代理到网关 8080。
 * - PROD（构建产物由网关 8080 托管）：同样走网关统一入口（同源，无需跨域）。
 */
const isProd = import.meta.env.PROD
const GATEWAY_BASE = isProd ? 'http://127.0.0.1:8080' : ''
const IMPORT_PREFIX = `${GATEWAY_BASE}/api/import`
const QUERY_PREFIX = `${GATEWAY_BASE}/api/query`
const AUTH_PREFIX = `${GATEWAY_BASE}/api/auth`
// 预留：用户服务 /api/user（前端接入档案/角色管理时启用）

const AUTH_KEY = 'shopkeeper_rag_user'

/** 从 localStorage 读取登录 token（未登录返回空串） */
function getStoredToken(): string {
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    if (!raw) return ''
    const u = JSON.parse(raw) as { username: string; token: string }
    return u.token || ''
  } catch {
    return ''
  }
}

/** 构造 Authorization 头（登录后自动附带 token） */
function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getStoredToken()
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

/** 认证相关 API */
export async function authRegister(username: string, password: string): Promise<{ username: string }> {
  const res = await fetch(`${AUTH_PREFIX}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const json = (await res.json()) as ApiResponse<{ username: string }>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `注册失败: ${res.status}`)
  return json.data as { username: string }
}

export async function authLogin(username: string, password: string): Promise<{ username: string; token: string }> {
  const res = await fetch(`${AUTH_PREFIX}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const json = (await res.json()) as ApiResponse<{ username: string; token: string }>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `登录失败: ${res.status}`)
  return json.data as { username: string; token: string }
}

export async function authMe(token: string): Promise<{ username: string }> {
  const res = await fetch(`${AUTH_PREFIX}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const json = (await res.json()) as ApiResponse<{ username: string }>
  if (!res.ok || json.code !== 200) throw new Error('登录已过期，请重新登录')
  return json.data as { username: string }
}

export async function authLogout(token: string): Promise<void> {
  await fetch(`${AUTH_PREFIX}/auth/logout`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  }).catch(() => {})
}

/** 上传文件并返回任务 id 列表 */
export async function uploadFiles(files: File[]): Promise<string[]> {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const res = await fetch(`${IMPORT_PREFIX}/upload`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  })
  if (!res.ok) throw new Error(`upload failed: ${res.status}`)
  const json = (await res.json()) as UploadResponse
  return json.task_ids || []
}

/** 查询导入任务状态 */
export async function fetchImportStatus(taskId: string): Promise<ImportStatusResponse> {
  const res = await fetch(`${IMPORT_PREFIX}/status/${taskId}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`status failed: ${res.status}`)
  return (await res.json()) as ImportStatusResponse
}

/** 提交查询任务 */
export async function submitQuery(req: QueryRequest): Promise<QuerySubmitData> {
  const res = await fetch(`${QUERY_PREFIX}/chat/query`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`query failed: ${res.status}`)
  const json = (await res.json()) as ApiResponse<QuerySubmitData>
  return json.data
}

/** 获取可用对话模型列表 */
export async function fetchModels(): Promise<ModelListData> {
  const res = await fetch(`${QUERY_PREFIX}/models`)
  if (!res.ok) throw new Error(`models failed: ${res.status}`)
  const json = (await res.json()) as ApiResponse<ModelListData>
  return json.data
}

/** 查询任务最终结果 */
export async function fetchTaskResult(taskId: string): Promise<TaskResultData> {
  const res = await fetch(`${QUERY_PREFIX}/task/result/${taskId}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`result failed: ${res.status}`)
  const json = (await res.json()) as ApiResponse<TaskResultData>
  return json.data
}

/** SSE 事件回调 */
export interface SSEHandlers {
  onDelta: (text: string) => void
  onFinal: (answer: string) => void
  onError: (message: string) => void
}

/**
 * 建立 SSE 流式连接（按 session_id 关联）。
 * 返回关闭函数。
 */
export function openSSE(sessionId: string, handlers: SSEHandlers): () => void {
  // EventSource 无法携带 Authorization 头，改为通过查询参数透传 token（网关支持 ?token=）
  const token = getStoredToken()
  const qs = token ? `?token=${encodeURIComponent(token)}` : ''
  const es = new EventSource(`${QUERY_PREFIX}/chat/stream/${sessionId}${qs}`)

  es.addEventListener('delta', (e) => {
    try {
      const data = JSON.parse((e as MessageEvent).data) as { text?: string }
      if (data.text) handlers.onDelta(data.text)
    } catch {
      /* ignore malformed */
    }
  })

  es.addEventListener('final', (e) => {
    try {
      const data = JSON.parse((e as MessageEvent).data) as { answer?: string }
      handlers.onFinal(data.answer || '')
    } catch {
      handlers.onFinal('')
    }
    es.close()
  })

  es.addEventListener('error', (e) => {
    try {
      const data = JSON.parse((e as MessageEvent).data) as { error?: string }
      handlers.onError(data.error || '未知错误')
    } catch {
      handlers.onError('连接中断')
    }
    es.close()
  })

  es.onerror = () => es.close()

  return () => es.close()
}

/** 生成 UUID（session 用） */
export function genUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}
