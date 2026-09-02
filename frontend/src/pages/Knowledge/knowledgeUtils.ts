/** 知识库管理模块共享工具：展示名与统计（页面与子组件共用，避免各写一份） */
import type { DocumentItem } from '../../types'

/** 单个知识库的统计：资料数 / 切片数 */
export interface KbStat {
  docs: number
  chunks: number
}

/** 统计缺失时的占位值（共享同一引用，避免每次重建对象触发不必要渲染） */
export const EMPTY_STAT: KbStat = { docs: 0, chunks: 0 }

/** 默认库的内部名以 default@ 开头，展示为「默认库」 */
export function kbDisplayName(name: string): string {
  return name.startsWith('default@') ? '默认库' : name || '默认库'
}

/** 默认库图标：🏠，普通库：📁 */
export function kbIcon(name: string): string {
  return name.startsWith('default@') ? '🏠' : '📁'
}

/** 按知识库聚合资料数 / 切片数（后端不提供该聚合，前端基于全量资料计算） */
export function buildStatByKb(docs: DocumentItem[]): Map<string, KbStat> {
  const map = new Map<string, KbStat>()
  for (const d of docs) {
    const kb = d.kb_name || 'default'
    const cur = map.get(kb) ?? { docs: 0, chunks: 0 }
    cur.docs += 1
    cur.chunks += d.chunk_count ?? 0
    map.set(kb, cur)
  }
  return map
}
