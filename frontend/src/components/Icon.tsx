/**
 * 精卫 UI 图标库（线性、统一描边、对齐字形）
 *
 * 全部为单色 SVG，size 与 stroke 显式声明，组件用 1em 高度 + currentColor 即可自适应。
 * 用法：<Icon name="folder" size={16} /> 或 <Icon name="book" className="kb-side-icon-svg" />
 */
import type { SVGProps } from 'react'

export type IconName =
  // 导航 / 操作
  | 'arrow-left'
  | 'plus'
  | 'search'
  | 'close'
  | 'refresh'
  | 'check'
  | 'upload'
  // 业务
  | 'home'
  | 'folder'
  | 'folder-move'
  | 'database'
  | 'book'
  | 'document'
  | 'globe'
  | 'team'
  | 'lock'
  // 状态
  | 'check-circle'
  | 'warning-circle'
  | 'spinner'
  // 主题
  | 'sun'
  | 'moon'

interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'children' | 'name'> {
  name: IconName
  size?: number
  strokeWidth?: number
}

/** 24×24 viewBox 的内联 SVG 图标，描边色用 currentColor */
export default function Icon({ name, size = 18, strokeWidth = 1.6, ...rest }: IconProps) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
    ...rest,
  }
  switch (name) {
    case 'arrow-left':
      return (
        <svg {...common}>
          <path d="M19 12H5" />
          <path d="M12 19l-7-7 7-7" />
        </svg>
      )
    case 'plus':
      return (
        <svg {...common}>
          <path d="M12 5v14" />
          <path d="M5 12h14" />
        </svg>
      )
    case 'search':
      return (
        <svg {...common}>
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
        </svg>
      )
    case 'close':
      return (
        <svg {...common}>
          <path d="M18 6L6 18" />
          <path d="M6 6l12 12" />
        </svg>
      )
    case 'refresh':
      return (
        <svg {...common}>
          <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
          <path d="M21 3v5h-5" />
          <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
          <path d="M3 21v-5h5" />
        </svg>
      )
    case 'check':
      return (
        <svg {...common}>
          <path d="M20 6L9 17l-5-5" />
        </svg>
      )
    case 'upload':
      return (
        <svg {...common}>
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <path d="M17 8l-5-5-5 5" />
          <path d="M12 3v12" />
        </svg>
      )
    case 'home':
      return (
        <svg {...common}>
          <path d="M3 10.5L12 3l9 7.5" />
          <path d="M5 10v10h14V10" />
          <path d="M10 20v-6h4v6" />
        </svg>
      )
    case 'folder':
      return (
        <svg {...common}>
          <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        </svg>
      )
    case 'folder-move':
      return (
        <svg {...common}>
          <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v3" />
          <path d="M3 7v10a2 2 0 0 0 2 2h7" />
          <path d="M14 21l4-4-4-4" />
          <path d="M18 17h-7" />
        </svg>
      )
    case 'database':
      return (
        <svg {...common}>
          <ellipse cx="12" cy="5" rx="8" ry="3" />
          <path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
          <path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" />
        </svg>
      )
    case 'book':
      return (
        <svg {...common}>
          <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5a2.5 2.5 0 0 0 0 5H20" />
          <path d="M9 6h7" />
          <path d="M9 10h7" />
        </svg>
      )
    case 'document':
      return (
        <svg {...common}>
          <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
          <path d="M14 3v6h6" />
          <path d="M8 13h8" />
          <path d="M8 17h6" />
        </svg>
      )
    case 'globe':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18" />
          <path d="M12 3a13 13 0 0 1 0 18a13 13 0 0 1 0-18" />
        </svg>
      )
    case 'team':
      return (
        <svg {...common}>
          <circle cx="9" cy="9" r="3.2" />
          <path d="M3 20a6 6 0 0 1 12 0" />
          <circle cx="17" cy="8" r="2.4" />
          <path d="M16 20a4.5 4.5 0 0 1 5-4.4" />
        </svg>
      )
    case 'lock':
      return (
        <svg {...common}>
          <rect x="4" y="11" width="16" height="9" rx="2" />
          <path d="M8 11V7a4 4 0 0 1 8 0v4" />
        </svg>
      )
    case 'check-circle':
      return (
        <svg {...common}>
          <path d="M22 11.1V12a10 10 0 1 1-5.93-9.14" />
          <path d="M22 4L12 14.01l-3-3" />
        </svg>
      )
    case 'warning-circle':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 8v4" />
          <path d="M12 16h.01" />
        </svg>
      )
    case 'spinner':
      return (
        <svg {...common} style={{ animation: 'kb-icon-spin 0.8s linear infinite', ...rest.style }}>
          <path d="M21 12a9 9 0 1 1-6.22-8.56" />
        </svg>
      )
    case 'sun':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2" />
          <path d="M12 20v2" />
          <path d="M5 5l1.5 1.5" />
          <path d="M17.5 17.5L19 19" />
          <path d="M2 12h2" />
          <path d="M20 12h2" />
          <path d="M5 19l1.5-1.5" />
          <path d="M17.5 6.5L19 5" />
        </svg>
      )
    case 'moon':
      return (
        <svg {...common}>
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        </svg>
      )
  }
}
