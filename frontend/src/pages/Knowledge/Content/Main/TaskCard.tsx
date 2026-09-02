import { IMPORT_NODES, type ImportTask, type TaskStatus } from '../../../../types'
import Icon from '../../../../components/Icon'

const STATUS_TEXT: Record<TaskStatus, string> = {
  PENDING: '等待中',
  PROCESSING: '处理中',
  COMPLETED: '已完成',
  FAILED: '失败',
}

function StatusBadge({ status }: { status: TaskStatus }) {
  return <span className={`status-badge status-${status}`}>{STATUS_TEXT[status]}</span>
}

function TaskCard({ task, onRetry }: { task: ImportTask; onRetry: (id: string) => void }) {
  const done = new Set(task.done_list)
  const running = new Set(task.running_list)
  // 只统计导入链图内节点：upload_file 属上传阶段不计入，
  // 否则 PDF 任务 done 数（9）> 节点数（8）会显示 113%
  const doneInGraph = IMPORT_NODES.filter((n) => done.has(n)).length
  // Markdown 文件会跳过 node_pdf_to_md，完成时按 100% 展示
  const progress =
    task.status === 'COMPLETED' ? 100 : Math.min(100, Math.round((doneInGraph / IMPORT_NODES.length) * 100))
  return (
    <div className="task">
      <div className="task-head">
        <div className="task-head-left">
          <span className="task-icon"><Icon name="document" size={18} /></span>
          <span className="task-fname">{task.filename}</span>
        </div>
        <StatusBadge status={task.status} />
      </div>
      <div className="task-progress">
        <div
          className={`task-progress-bar status-${task.status}`}
          style={{ width: `${progress}%` }}
        />
        <div className="task-progress-text">{progress}% · {STATUS_TEXT[task.status]}</div>
      </div>
      <div className="node-progress">
        {IMPORT_NODES.map((n) => (
          <span
            key={n}
            className={
              'node-chip' +
              (done.has(n) ? ' done' : running.has(n) ? ' running' : '')
            }
          >
            {n}
          </span>
        ))}
      </div>
      {/* FR-IMP-04：失败原因结构化展示 + 重试 */}
      {task.status === 'FAILED' && (
        <div className="task-error">
          <div className="err-msg">失败原因：{task.error || '未知错误'}</div>
          <button className="btn ghost" onClick={() => onRetry(task.task_id)}>
            重试
          </button>
        </div>
      )}
      <div className="task-id">{task.task_id}</div>
    </div>
  )
}

export { STATUS_TEXT, StatusBadge, TaskCard }
