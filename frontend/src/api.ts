/**
 * 精卫前端 · API 客户端
 *
 * 阶段4：全部请求经网关统一入口（8080），由网关负责路由转发与鉴权前置：
 *   /api/import/*  ->  导入服务 (8081)
 *   /api/query/*   ->  查询服务 (8082)
 *   /api/auth/*    ->  认证服务 (8083)
 *   /api/user/*    ->  用户服务 (8084)
 */
import type {
  ApiResponse,
  DocumentItem,
  ImportStatusResponse,
  KnowledgeBase,
  ModelListData,
  QueryRequest,
  QuerySubmitData,
  RejectedFile,
  TaskResultData,
  UploadResponse,
  Visibility,
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

const AUTH_KEY = 'jingwei_rag_user'
const ANON_KEY = 'jingwei_rag_anon_id'

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

/** 读取/生成本浏览器的匿名 ID（未登录访客隔离用，持久化在 localStorage）。 */
export function getAnonId(): string {
  try {
    let id = localStorage.getItem(ANON_KEY)
    if (!id) {
      id = genUUID()
      localStorage.setItem(ANON_KEY, id)
    }
    return id
  } catch {
    return ''
  }
}

/** 构造 Authorization 头（登录后自动附带 token）+ 匿名 ID 头（未登录访客隔离）。 */
function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getStoredToken()
  const anon = getAnonId()
  const headers: Record<string, string> = { ...extra }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (anon && !token) headers['X-Anon-Id'] = anon
  return headers
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

export async function authMe(token: string): Promise<{ username: string; role?: string }> {
  const res = await fetch(`${AUTH_PREFIX}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const json = (await res.json()) as ApiResponse<{ username: string; role?: string }>
  if (!res.ok || json.code !== 200) throw new Error('登录已过期，请重新登录')
  return json.data as { username: string; role?: string }
}

export async function authLogout(token: string): Promise<void> {
  await fetch(`${AUTH_PREFIX}/auth/logout`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  }).catch(() => {})
}

/** 拉取服务端「当前用户 / 当前访客」的会话列表。
 * 登录用户：token 解析身份；未登录访客：X-Anon-Id 头解析身份（各自只见自己的 guest 会话）。
 */
export async function listSessions(): Promise<
  { session_id: string; title: string; updated_at: string; meta: Record<string, unknown> }[]
> {
  const res = await fetch(`${QUERY_PREFIX}/sessions`, { headers: authHeaders() })
  const json = (await res.json()) as ApiResponse<{ sessions: any[] }>
  if (!res.ok || json.code !== 200) throw new Error(json.message || '获取会话列表失败')
  return (json.data?.sessions ?? []) as any[]
}

/** 删除服务端会话及其全部消息（硬删除）。未登录访客经 X-Anon-Id 头由服务端校验归属。 */
export async function deleteSessionApi(sessionId: string): Promise<void> {
  const res = await fetch(`${QUERY_PREFIX}/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  // 访客态会话可能尚未落库（首次发消息才创建），服务端返回 404 视为「无可删除」正常处理
  if (res.status === 404) return
  const json = (await res.json().catch(() => ({}))) as ApiResponse<{ session_id: string }>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `删除会话失败: ${res.status}`)
}

/** 登录即归并：把本浏览器（anon_id）下遗留的 guest 会话归并到当前登录用户。 */
export async function claimGuestSessions(): Promise<number> {
  const res = await fetch(`${QUERY_PREFIX}/sessions/claim`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ anon_id: getAnonId() }),
  })
  const json = (await res.json()) as ApiResponse<{ claimed: number }>
  if (!res.ok || json.code !== 200) throw new Error(json.message || '归并会话失败')
  return json.data?.claimed ?? 0
}

/**
 * 上传文件并返回任务 id 列表；visibility 控制资料私有/团队/共享；kb 指定目标逻辑知识库。
 *
 * G-01：后端会拒绝不支持的格式。全部被拒时抛错（含原因）；部分被拒时返回
 * `rejected` 清单，调用方须展示，避免"上传成功却零条入库"的静默失败。
 */
export async function uploadFiles(
  files: File[],
  visibility: Visibility = 'private',
  kb: string = 'default',
): Promise<{ task_ids: string[]; rejected: RejectedFile[] }> {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  fd.append('visibility', visibility)
  fd.append('kb_name', kb)
  const res = await fetch(`${IMPORT_PREFIX}/upload`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  })
  const json = (await res.json()) as UploadResponse
  if (!res.ok || json.code >= 400) {
    // 全部被拒：优先展示后端给出的中文原因
    const detail = json.rejected?.map((r) => r.reason).join('；')
    throw new Error(detail || json.message || `upload failed: ${res.status}`)
  }
  return { task_ids: json.task_ids || [], rejected: json.rejected || [] }
}

/** 查询导入任务状态 */
export async function fetchImportStatus(taskId: string): Promise<ImportStatusResponse> {
  const res = await fetch(`${IMPORT_PREFIX}/status/${taskId}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`status failed: ${res.status}`)
  return (await res.json()) as ImportStatusResponse
}

/** FR-IMP-04：重试失败的导入任务（限管理员） */
export async function retryImport(taskId: string): Promise<void> {
  const res = await fetch(`${IMPORT_PREFIX}/status/${taskId}/retry`, {
    method: 'POST',
    headers: authHeaders(),
  })
  const json = (await res.json()) as ApiResponse<unknown>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `重试失败: ${res.status}`)
}

/** 列出已导入资料（按当前用户权限隔离：普通用户仅见自己的与共享的）；kb 可按知识库过滤 */
export async function listDocuments(kb: string = ''): Promise<DocumentItem[]> {
  const qs = kb ? `?kb_name=${encodeURIComponent(kb)}` : ''
  const res = await fetch(`${IMPORT_PREFIX}/documents${qs}`, { headers: authHeaders() })
  const json = (await res.json()) as ApiResponse<{ items: DocumentItem[] }>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `获取资料列表失败: ${res.status}`)
  return json.data?.items ?? []
}

/** 列出可用的逻辑知识库（默认库 + 当前用户创建的库） */
export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  const res = await fetch(`${IMPORT_PREFIX}/knowledge-bases`, { headers: authHeaders() })
  const json = (await res.json()) as ApiResponse<{ bases: KnowledgeBase[] }>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `获取知识库列表失败: ${res.status}`)
  return json.data?.bases ?? []
}

/** 新建逻辑知识库 */
export async function createKnowledgeBase(name: string): Promise<KnowledgeBase> {
  const fd = new FormData()
  fd.append('name', name)
  const res = await fetch(`${IMPORT_PREFIX}/knowledge-bases`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  })
  const json = (await res.json()) as ApiResponse<KnowledgeBase>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `创建知识库失败: ${res.status}`)
  return json.data as KnowledgeBase
}

/** 重命名逻辑知识库（默认库不可重命名）；返回新名称与受影响的资料数 */
export async function renameKnowledgeBase(
  name: string,
  newName: string,
): Promise<{ name: string; renamed: number }> {
  const fd = new FormData()
  fd.append('new_name', newName)
  const res = await fetch(`${IMPORT_PREFIX}/knowledge-bases/${encodeURIComponent(name)}/rename`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  })
  const json = (await res.json()) as ApiResponse<{ name: string; renamed: number }>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `重命名知识库失败: ${res.status}`)
  return json.data as { name: string; renamed: number }
}

/** 删除逻辑知识库（默认库不可删除）；库内资料会迁移到默认库 */
export async function deleteKnowledgeBase(
  name: string,
): Promise<{ name: string; moved_items: number; moved_to: string }> {
  const res = await fetch(`${IMPORT_PREFIX}/knowledge-bases/${encodeURIComponent(name)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  const json = (await res.json()) as ApiResponse<{
    name: string
    moved_items: number
    moved_to: string
  }>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `删除知识库失败: ${res.status}`)
  return json.data as { name: string; moved_items: number; moved_to: string }
}

/** 切换资料可见性：private（仅本人）/ team（团队可见）/ shared（全员共享检索）。owner 或管理员可操作。 */
/**
 * 切换资料可见性，返回后端**实际生效**的可见性。
 * 返回值可能与请求值不同（例如无团队时后端会拒绝而非降级），调用方应以此为准做校验。
 */
export async function setDocumentVisibility(
  itemName: string,
  visibility: Visibility,
): Promise<Visibility> {
  const res = await fetch(
    `${IMPORT_PREFIX}/documents/${encodeURIComponent(itemName)}/visibility?visibility=${visibility}`,
    { method: 'POST', headers: authHeaders() },
  )
  const json = (await res.json()) as ApiResponse<{ visibility?: Visibility }>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `切换可见性失败: ${res.status}`)
  return (json.data?.visibility ?? visibility) as Visibility
}

/** 将资料移动到其它逻辑知识库（owner 或管理员可操作） */
export async function moveDocument(itemName: string, targetKb: string): Promise<void> {
  const fd = new FormData()
  fd.append('target_kb', targetKb)
  const res = await fetch(`${IMPORT_PREFIX}/documents/${encodeURIComponent(itemName)}/move`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  })
  const json = (await res.json()) as ApiResponse<unknown>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `移动失败: ${res.status}`)
}

/** 下线某资料，删除其全部 chunk（owner 或管理员可操作） */
export async function offlineDocument(itemName: string): Promise<void> {
  const res = await fetch(`${IMPORT_PREFIX}/documents/${encodeURIComponent(itemName)}/offline`, {
    method: 'POST',
    headers: authHeaders(),
  })
  const json = (await res.json()) as ApiResponse<unknown>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `下线失败: ${res.status}`)
}

/** FR-COMP-05：提交用户对答案的反馈（满意度 / 纠错） */
export interface FeedbackRequest {
  session_id: string
  message_id?: string
  rating?: number
  feedback_type?: string
  content?: string
  username?: string
  anon_id?: string
}
export async function submitFeedback(req: FeedbackRequest): Promise<void> {
  const res = await fetch(`${QUERY_PREFIX}/feedback`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(req),
  })
  const json = (await res.json()) as ApiResponse<unknown>
  if (!res.ok || json.code !== 200) throw new Error(json.message || `反馈提交失败: ${res.status}`)
}

/** 提交查询任务 */
export async function submitQuery(req: QueryRequest): Promise<QuerySubmitData> {
  const body: QueryRequest = { ...req }
  // 未登录访客：附上本浏览器匿名 ID，使 guest 会话按单浏览器隔离
  if (!getStoredToken() && !body.anon_id) {
    body.anon_id = getAnonId()
  }
  const res = await fetch(`${QUERY_PREFIX}/chat/query`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
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
  /** FR-CITE-02：final 同时透传结构化来源引用 citations */
  onFinal: (answer: string, citations?: import('./types').Citation[]) => void
  onError: (message: string) => void
}

/**
 * 建立 SSE 流式连接（按 session_id 关联）。
 * 返回关闭函数。
 */
export function openSSE(sessionId: string, handlers: SSEHandlers): () => void {
  // EventSource 无法携带 Authorization 头，改为通过查询参数透传 token（网关支持 ?token=）
  const token = getStoredToken()
  const anon = getAnonId()
  const params = new URLSearchParams()
  if (token) params.set('token', token)
  else if (anon) params.set('anon_id', anon)
  const qs = params.toString() ? `?${params.toString()}` : ''
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
      const data = JSON.parse((e as MessageEvent).data) as {
        answer?: string
        citations?: import('./types').Citation[]
      }
      handlers.onFinal(data.answer || '', data.citations)
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
