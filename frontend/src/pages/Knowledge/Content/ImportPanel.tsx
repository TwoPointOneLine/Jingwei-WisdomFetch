import { useEffect, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { fetchImportStatus, retryImport } from '../../../api'
import type { ImportTask } from '../../../types'
import { TaskCard } from './Main/TaskCard'

/** 任务完成后的短暂展示时长（ms），到期自动从列表移除 */
const DONE_LINGER_MS = 2500

/**
 * 导入任务面板：仅负责进行中/历史导入任务的轮询与展示。
 * 已导入资料区（DocumentsSection）已提升至头部区域，不再属于本面板。
 * 任务处理完毕（COMPLETED）后短暂展示即自动消失；失败任务保留以便重试。
 */
export default function ImportPanel({
  tasks,
  onTasksChange,
  onImportDone,
}: {
  /** 导入任务列表（由页面级状态管理，上传成功后注入） */
  tasks: ImportTask[]
  onTasksChange?: Dispatch<SetStateAction<ImportTask[]>>
  /** 任一任务完成时回调（用于刷新已导入资料列表） */
  onImportDone?: () => void
}) {
  const prevStatusRef = useRef<Record<string, string>>({})
  // 完成清理定时器：多个任务同时完成时只调度一次
  const cleanupRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (cleanupRef.current) clearTimeout(cleanupRef.current)
    }
  }, [])

  // 失败任务重试
  const handleRetry = async (taskId: string) => {
    try {
      await retryImport(taskId)
      onTasksChange?.((prev) =>
        prev.map((t) =>
          t.task_id === taskId ? { ...t, status: 'PROCESSING', done_list: [], running_list: [], error: null } : t,
        ),
      )
    } catch (e) {
      alert(`重试失败：${e instanceof Error ? e.message : e}`)
    }
  }

  // 轮询任务状态
  useEffect(() => {
    if (!tasks.length) return
    const timer = setInterval(async () => {
      const updated = await Promise.all(
        tasks.map(async (t) => {
          try {
            const data = await fetchImportStatus(t.task_id)
            // 后端返回小写状态值（pending/processing/completed/failed），归一化为前端大写枚举，
            // 否则 FAILED/COMPLETED 分支永远匹配不上，任务会假死在"进行中"
            return {
              ...t,
              status: String(data.status ?? '').toUpperCase() as ImportTask['status'],
              done_list: data.done_list,
              running_list: data.running_list,
              error: data.error,
            }
          } catch {
            return t
          }
        }),
      )
      // 有任务新近完成 → 通知上层刷新资料列表
      const newlyDone = updated.some(
        (t) => t.status === 'COMPLETED' && prevStatusRef.current[t.task_id] !== 'COMPLETED',
      )
      if (newlyDone) {
        onImportDone?.()
        // 完成的任务短暂展示"已完成"后自动移除，任务区随之收起
        if (!cleanupRef.current) {
          cleanupRef.current = setTimeout(() => {
            cleanupRef.current = null
            onTasksChange?.((prev) => prev.filter((t) => t.status !== 'COMPLETED'))
          }, DONE_LINGER_MS)
        }
      }
      prevStatusRef.current = Object.fromEntries(updated.map((t) => [t.task_id, t.status ?? '']))
      onTasksChange?.(updated)
    }, 2000)
    return () => clearInterval(timer)
  }, [tasks])

  if (!tasks.length) return null

  return (
    <div className="panel import-layout">
      <div className="import-grid">
        <div className="import-col">
          <div className="kb-section">
            <div className="task-list">
              {tasks.map((t) => (
                <TaskCard key={t.task_id} task={t} onRetry={handleRetry} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
