/** 精卫前端 · API 类型定义 */

/** 导入任务状态 */
export type TaskStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'

/** 导入链节点（用于进度展示，须与后端 main_graph 节点保持一致；upload_file 属上传阶段不计入） */
export const IMPORT_NODES = [
  'node_entry',
  'node_pdf_to_md',
  'node_md_img',
  'node_document_metadata',
  'node_document_split',
  'node_item_name_recognition',
  'node_bge_embedding',
  'node_import_milvus',
] as const

/** G-01：被拒绝的文件（格式不支持等） */
export interface RejectedFile {
  filename: string
  reason: string
}

/** 上传响应（import-server） */
export interface UploadResponse {
  code: number
  message: string
  task_ids: string[]
  /** G-01：被拒文件清单，前端必须展示，否则用户以为"上传成功却查不到" */
  rejected?: RejectedFile[]
}

/** 导入任务状态响应（import-server，扁平结构，无 data 包裹） */
export interface ImportStatusResponse {
  code: number
  task_id: string
  status: TaskStatus
  done_list: string[]
  running_list: string[]
  /** FR-IMP-04：失败原因（结构化返回，失败时由后端填写） */
  error?: string | null
}

/** 导入任务 UI 展示项 */
export interface ImportTask {
  task_id: string
  filename: string
  status: TaskStatus
  done_list: string[]
  running_list: string[]
  /** FR-IMP-04：失败原因（结构化返回） */
  error?: string | null
}

/** 查询请求体（query-server） */
export interface QueryRequest {
  session_id: string
  query: string
  need_stream_output?: boolean
  item_name?: string | null
  model?: string | null
  username?: string | null
  /** 未登录访客的匿名 ID（前端本地持久化），用于 guest 会话按单浏览器隔离 */
  anon_id?: string | null
}

/** 查询服务通用响应（query-server，data 包裹） */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/** 查询任务提交结果 */
export interface QuerySubmitData {
  task_id: string
  session_id: string
}

/** 查询任务结果 */
export interface TaskResultData {
  status: TaskStatus
  done_list: string[]
  running_list: string[]
}

/** 对话消息 */
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  /** 兼容旧字段：保留历史会话中可能存在的参考来源 */
  sources?: Array<{ title?: string; url?: string; chunk_id?: string; content?: string }>
  /** FR-CITE-02：结构化来源引用（可信标记 / 可展开），由 SSE final 或 /task/result 返回 */
  citations?: Citation[]
  /** FR-COMP-05：本消息是否已提交过反馈 */
  feedbackGiven?: boolean
}

/** FR-CITE-02：来源引用结构（与后端 /chat/query final 的 citations 对齐） */
export interface Citation {
  index: number
  title: string
  /** 来源系统：milvus=内部资料，web=外网（FR-QA-06，需提示看官方渠道） */
  source: string
  external?: boolean
  content_type?: string
  product_name?: string
  product_code?: string
  risk_level?: string
  publish_date?: string
  /** G-04：补齐全字段 */
  institution_name?: string
  industry?: string
  market?: string
  entry_name?: string
  source_file?: string
  source_path?: string
  /** G-08：原文片段（命中原文档前 200 字） */
  snippet?: string
}

/** SSE 事件类型 */
export type SSEEventName = 'delta' | 'final' | 'error' | 'close'

/** 对话会话（用于侧栏历史列表） */
export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  updatedAt: number
}

/** 可用的对话模型项 */
export interface ChatModel {
  id: string
  name: string
  description?: string
}

/** 模型列表响应 */
export interface ModelListData {
  models: ChatModel[]
  default: string
}

/** 资料可见性：private=仅本人可见/可检索；team=团队可见（同团队成员共享检索）；shared=全员共享检索 */
export type Visibility = 'private' | 'team' | 'shared'

/** 已导入资料项（import-server /documents） */
export interface DocumentItem {
  item_name: string
  chunk_count: number
  source_files: string[]
  product_name?: string
  publish_date?: string
  /** 归属用户名（普通用户只能管理自己的） */
  owner?: string
  /** 可见性 */
  visibility?: Visibility
  /** 所属团队 ID（仅 visibility=team 时有效） */
  team_id?: string
  /** 所属逻辑知识库（导入时选择；同一 Milvus 集合内以 kb_name 区分） */
  kb_name?: string
}

/** 逻辑知识库（import-server /knowledge-bases） */
export interface KnowledgeBase {
  name: string
  /** 创建者用户名（默认库为空串） */
  owner: string
  /** 是否默认库（default，内置无需创建） */
  is_default: boolean
}
