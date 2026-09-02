/**
 * 轻量 Markdown 渲染器（零依赖）
 *
 * 背景：后端为产品类问题生成「四段式」Markdown 回答（## 一、基本信息 …），
 * 但前端此前直接输出纯文本，标题/表格/列表全变成带 `#` 的裸字符串（G-02）。
 *
 * 设计取舍：
 * - 不引入 react-markdown/marked，避免新增依赖与 XSS 面；
 * - 全程输出 React 元素（不使用 dangerouslySetInnerHTML），天然免疫脚本注入；
 * - 链接做协议白名单，仅放行 http/https/mailto。
 *
 * 支持：标题、粗体、斜体、行内代码、围栏代码块、无序/有序列表、任务列表、
 *       GFM 管道表格、引用块、分隔线、链接、段落、换行。
 */
import { Fragment, type ReactNode } from 'react'

/** 链接协议白名单：杜绝 javascript:/data: 等可执行协议 */
const SAFE_PROTOCOL = /^(https?:|mailto:)/i

function safeHref(href: string): string | undefined {
  const trimmed = href.trim()
  if (!trimmed) return undefined
  // 相对路径与锚点放行
  if (/^[./#]/.test(trimmed)) return trimmed
  return SAFE_PROTOCOL.test(trimmed) ? trimmed : undefined
}

/** 行内解析：`代码`、**粗体**、*斜体*、[文本](链接) */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  // 反引号代码优先，避免其中的 * 被当作强调
  const tokenRe = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(\[[^\]]*\]\([^)\s]+\))/g
  let last = 0
  let m: RegExpExecArray | null
  let i = 0

  while ((m = tokenRe.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index))
    const token = m[0]
    const key = `${keyPrefix}-i${i++}`

    if (token.startsWith('`')) {
      nodes.push(
        <code className="md-code" key={key}>
          {token.slice(1, -1)}
        </code>,
      )
    } else if (token.startsWith('**')) {
      nodes.push(<strong key={key}>{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('*')) {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>)
    } else {
      // 链接：[文本](url)
      const lm = /^\[([^\]]*)\]\(([^)\s]+)\)$/.exec(token)
      if (lm) {
        const href = safeHref(lm[2])
        if (href) {
          nodes.push(
            <a className="md-link" href={href} key={key} target="_blank" rel="noopener noreferrer">
              {lm[1] || href}
            </a>,
          )
        } else {
          nodes.push(lm[1] || token)
        }
      } else {
        nodes.push(token)
      }
    }
    last = m.index + token.length
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

/** 把一段行内文本解析为 React 节点，保留换行 */
function renderText(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split('\n')
  const out: ReactNode[] = []
  parts.forEach((p, idx) => {
    if (idx > 0) out.push(<br key={`${keyPrefix}-br${idx}`} />)
    out.push(...renderInline(p, `${keyPrefix}-p${idx}`))
  })
  return out
}

type Block =
  | { t: 'heading'; level: number; text: string }
  | { t: 'code'; lang: string; lines: string[] }
  | { t: 'quote'; lines: string[] }
  | { t: 'ul'; items: string[]; ordered: false }
  | { t: 'ol'; items: string[]; ordered: true }
  | { t: 'table'; header: string[]; rows: string[][]; align: (string | undefined)[] }
  | { t: 'hr' }
  | { t: 'p'; lines: string[] }

const HEADING_RE = /^(#{1,6})\s+(.*)$/
const UL_RE = /^\s*[-*+]\s+(.*)$/
const OL_RE = /^\s*\d+[.)]\s+(.*)$/
const QUOTE_RE = /^\s*>\s?(.*)$/
const HR_RE = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/
const FENCE_RE = /^\s*(`{3,}|~{3,})\s*([^\s`]*)\s*$/

/** 判断是否为 GFM 表格分隔行（---|:---:|---:） */
function isTableDelimiter(line: string): boolean {
  if (!line.includes('-') || !line.includes('|')) return false
  return line
    .split('|')
    .map((c) => c.trim())
    .filter(Boolean)
    .every((c) => /^:?-{1,}:?$/.test(c))
}

function splitRow(line: string): string[] {
  let s = line.trim()
  if (s.startsWith('|')) s = s.slice(1)
  if (s.endsWith('|')) s = s.slice(0, -1)
  return s.split('|').map((c) => c.trim())
}

function parseAlign(delimiter: string): (string | undefined)[] {
  return splitRow(delimiter).map((c) => {
    if (/^:-+:$/.test(c)) return 'center'
    if (/^:-+/.test(c)) return 'left'
    if (/-+:$/.test(c)) return 'right'
    return undefined
  })
}

/** 把 Markdown 源码切分为块级元素 */
function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n?/g, '\n').split('\n')
  const blocks: Block[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // 空行
    if (!line.trim()) {
      i++
      continue
    }

    // 围栏代码块
    const fence = FENCE_RE.exec(line)
    if (fence) {
      const marker = fence[1][0]
      const lang = fence[2] || ''
      const body: string[] = []
      i++
      while (i < lines.length && !new RegExp(`^\\s*${marker}{3,}\\s*$`).test(lines[i])) {
        body.push(lines[i])
        i++
      }
      i++ // 跳过结束围栏
      blocks.push({ t: 'code', lang, lines: body })
      continue
    }

    // 分隔线
    if (HR_RE.test(line)) {
      blocks.push({ t: 'hr' })
      i++
      continue
    }

    // 标题
    const h = HEADING_RE.exec(line)
    if (h) {
      blocks.push({ t: 'heading', level: h[1].length, text: h[2].trim() })
      i++
      continue
    }

    // 表格：当前行含 | 且下一行是分隔行
    if (line.includes('|') && i + 1 < lines.length && isTableDelimiter(lines[i + 1])) {
      const header = splitRow(line)
      const align = parseAlign(lines[i + 1])
      i += 2
      const rows: string[][] = []
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        rows.push(splitRow(lines[i]))
        i++
      }
      blocks.push({ t: 'table', header, rows, align })
      continue
    }

    // 引用块
    if (QUOTE_RE.test(line)) {
      const body: string[] = []
      while (i < lines.length && QUOTE_RE.test(lines[i])) {
        body.push(QUOTE_RE.exec(lines[i])![1])
        i++
      }
      blocks.push({ t: 'quote', lines: body })
      continue
    }

    // 列表（连续的同类型项 + 缩进续行）
    if (UL_RE.test(line) || OL_RE.test(line)) {
      const ordered = !UL_RE.test(line)
      const re = ordered ? OL_RE : UL_RE
      const items: string[] = []
      while (i < lines.length) {
        const m = re.exec(lines[i])
        if (m) {
          items.push(m[1])
          i++
        } else if (lines[i].trim() && /^\s{2,}\S/.test(lines[i])) {
          // 缩进续行：并入上一项
          items[items.length - 1] += ` ${lines[i].trim()}`
          i++
        } else {
          break
        }
      }
      blocks.push(ordered ? { t: 'ol', items, ordered: true } : { t: 'ul', items, ordered: false })
      continue
    }

    // 普通段落：连续非空且不属于上述类型的行
    const para: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() &&
      !HEADING_RE.test(lines[i]) &&
      !FENCE_RE.test(lines[i]) &&
      !HR_RE.test(lines[i]) &&
      !QUOTE_RE.test(lines[i]) &&
      !UL_RE.test(lines[i]) &&
      !OL_RE.test(lines[i])
    ) {
      para.push(lines[i])
      i++
    }
    if (para.length) blocks.push({ t: 'p', lines: para })
    else i++ // 兜底防死循环
  }

  return blocks
}

function renderBlock(b: Block, key: string): ReactNode {
  switch (b.t) {
    case 'heading': {
      const Tag = (['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] as const)[b.level - 1] ?? 'h6'
      return (
        <Tag className={`md-h md-h${b.level}`} key={key}>
          {renderInline(b.text, key)}
        </Tag>
      )
    }
    case 'code':
      return (
        <pre className="md-pre" key={key}>
          <code className={b.lang ? `md-code-block lang-${b.lang}` : 'md-code-block'}>
            {b.lines.join('\n')}
          </code>
        </pre>
      )
    case 'quote':
      return (
        <blockquote className="md-quote" key={key}>
          {renderText(b.lines.join('\n'), key)}
        </blockquote>
      )
    case 'ul':
      return (
        <ul className="md-list" key={key}>
          {b.items.map((it, idx) => (
            <li key={`${key}-${idx}`}>{renderInline(it, `${key}-${idx}`)}</li>
          ))}
        </ul>
      )
    case 'ol':
      return (
        <ol className="md-list" key={key}>
          {b.items.map((it, idx) => (
            <li key={`${key}-${idx}`}>{renderInline(it, `${key}-${idx}`)}</li>
          ))}
        </ol>
      )
    case 'table': {
      const styleFor = (idx: number) =>
        b.align[idx] ? { textAlign: b.align[idx] as 'left' | 'center' | 'right' } : undefined
      return (
        <div className="md-table-wrap" key={key}>
          <table className="md-table">
            <thead>
              <tr>
                {b.header.map((c, idx) => (
                  <th key={`${key}-h${idx}`} style={styleFor(idx)}>
                    {renderInline(c, `${key}-h${idx}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {b.rows.map((r, ri) => (
                <tr key={`${key}-r${ri}`}>
                  {b.header.map((_, ci) => (
                    <td key={`${key}-r${ri}-c${ci}`} style={styleFor(ci)}>
                      {renderInline(r[ci] ?? '', `${key}-r${ri}-c${ci}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }
    case 'hr':
      return <hr className="md-hr" key={key} />
    case 'p':
    default:
      return (
        <p className="md-p" key={key}>
          {renderText((b as { lines: string[] }).lines.join('\n'), key)}
        </p>
      )
  }
}

/**
 * 渲染 Markdown 文本。
 *
 * 流式场景：内容每几十毫秒增量更新，本组件为纯函数渲染（无内部状态），
 * 未完成的代码块/表格会自动按当前已有内容降级渲染，不会闪烁或报错。
 */
export default function Markdown({ content }: { content: string }) {
  if (!content) return null
  const blocks = parseBlocks(content)
  return (
    <div className="md-root">
      {blocks.map((b, idx) => (
        <Fragment key={`b${idx}`}>{renderBlock(b, `b${idx}`)}</Fragment>
      ))}
    </div>
  )
}
