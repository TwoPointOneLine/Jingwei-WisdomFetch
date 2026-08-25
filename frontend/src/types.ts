/** 掌柜智库前端 · API 类型定义 */

/** 导入任务状态 */
export type TaskStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'

/** 导入链节点（用于进度展示） */
export const IMPORT_NODES = [
  'upload_file',
  'node_entry',
  'node_pdf_to_md',
  'node_md_img',
  'node_document_split',
  'node_item_name_recognition',
  'node_bge_embedding',
  'node_import_milvus',
] as const

/** 上传响应（import-server） */
export interface UploadResponse {
  code: number
  message: string
  task_ids: string[]
}

/** 导入任务状态响应（import-server，扁平结构，无 data 包裹） */
export interface ImportStatusResponse {
  code: number
  task_id: string
  status: TaskStatus
  done_list: string[]
  running_list: string[]
}

/** 导入任务 UI 展示项 */
export interface ImportTask {
  task_id: string
  filename: string
  status: TaskStatus
  done_list: string[]
  running_list: string[]
}

/** 查询请求体（query-server） */
export interface QueryRequest {
  session_id: string
  query: string
  need_stream_output?: boolean
  item_name?: string | null
  model?: string | null
  username?: string | null
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
  sources?: Array<{ title?: string; url?: string; chunk_id?: string; content?: string }>
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
