/**
 * 导入格式白名单（G-01）
 *
 * 背景：此前前端 `accept` 声明了 .txt/.doc/.docx，但后端只有 PDF/Markdown 解析器，
 * 不支持的文件会"上传成功却零条入库"，用户完全无感知。
 *
 * 方案：以**后端 `/api/import/formats`** 为单一事实来源，前端启动时拉取并缓存；
 * 拉取失败时回退到内置默认值（与后端 `doc_format.SUPPORTED_EXTS` 保持一致）。
 */
import { useEffect, useState } from 'react'

/** 内置兜底值：必须与 backend jingwei_knowledge/rag/import_/doc_format.py 的 SUPPORTED_EXTS 同步 */
export const FALLBACK_ACCEPT = '.pdf,.md,.markdown'

export interface SupportedFormats {
  exts: string[]
  accept: string
  display: string
}

let cache: SupportedFormats | null = null
let inflight: Promise<SupportedFormats> | null = null

/** 拉取后端格式白名单（进程内缓存，重复调用只发一次请求）。 */
export async function loadSupportedFormats(): Promise<SupportedFormats> {
  if (cache) return cache
  if (!inflight) {
    inflight = (async () => {
      try {
        const res = await fetch('/api/import/formats')
        const json = (await res.json()) as {
          code: number
          data?: { exts?: string[]; accept?: string; display?: string }
        }
        const data = json?.data
        if (data?.accept) {
          cache = {
            exts: data.exts ?? [],
            accept: data.accept,
            display: data.display ?? '',
          }
          return cache
        }
      } catch {
        // 回退默认值
      }
      cache = { exts: FALLBACK_ACCEPT.split(','), accept: FALLBACK_ACCEPT, display: 'PDF、Markdown' }
      return cache
    })()
  }
  return inflight
}

/** React Hook：获取 accept 属性与格式展示名。 */
export function useSupportedFormats(): { accept: string; display: string } {
  const [fmt, setFmt] = useState<SupportedFormats | null>(cache)
  useEffect(() => {
    if (cache) return
    let alive = true
    loadSupportedFormats().then((f) => {
      if (alive) setFmt(f)
    })
    return () => {
      alive = false
    }
  }, [])
  return { accept: fmt?.accept ?? FALLBACK_ACCEPT, display: fmt?.display ?? 'PDF、Markdown' }
}
