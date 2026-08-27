import { useState } from 'react'

export type ThemeMode = 'light' | 'dark'

interface SidebarFooterProps {
  activeView: 'chat' | 'import'
  theme: ThemeMode
  isLoggedIn: boolean
  isAdmin: boolean
  username: string
  onSwitchView: (view: 'chat' | 'import') => void
  onThemeChange: (theme: ThemeMode) => void
  onLogin: () => void
  onLogout: () => void
}

/**
 * 侧栏底部功能区（独立组件）：知识库管理入口 + 登录（未登录）/ 用户信息（已登录）+ 设置（弹窗）。
 *
 * 登录按钮位于「设置」上方；设置以居中弹窗形式打开（主题切换等）。
 */
export default function SidebarFooter({
  activeView,
  theme,
  isLoggedIn,
  isAdmin,
  username,
  onSwitchView,
  onThemeChange,
  onLogin,
  onLogout,
}: SidebarFooterProps) {
  const [showSettings, setShowSettings] = useState(false)

  return (
    <div className="sidebar-foot">
      {/* 知识库管理入口：登录 + 管理员（FR-AUTH-02），其余角色点击提示无权限 */}
      {isLoggedIn && (
        <button
          className={`menu-item${activeView === 'import' ? ' active' : ''}`}
          onClick={() => {
            if (!isAdmin) {
              alert('仅管理员可访问知识库管理')
              return
            }
            onSwitchView('import')
          }}
        >
          <span className="menu-item-icon">📚</span>
          <span className="menu-item-label">知识库管理</span>
        </button>
      )}

      {/* 登录（未登录时） */}
      {!isLoggedIn && (
        <button className="menu-item login-item" onClick={onLogin}>
          <span className="menu-item-icon">🔑</span>
          <span className="menu-item-label">登录</span>
        </button>
      )}

      {/* 已登录：用户信息 + 退出登录 */}
      {isLoggedIn && (
        <div className="sidebar-user">
          <div className="sidebar-user-avatar" title={username}>
            {username ? username.charAt(0).toUpperCase() : '?'}
          </div>
          <div className="sidebar-user-info">
            <span className="sidebar-user-name" title={username}>
              {username}
            </span>
            <span className="sidebar-user-status">已登录</span>
          </div>
          <button
            className="sidebar-user-logout"
            onClick={onLogout}
            title="退出登录"
            aria-label="退出登录"
          >
            退出
          </button>
        </div>
      )}

      {/* 设置入口（弹层锚点，置于最下方） */}
      <div className="settings-wrap">
        <button className="menu-item" onClick={() => setShowSettings(true)}>
          <span className="menu-item-icon">⚙️</span>
          <span className="menu-item-label">设置</span>
        </button>

        {/* 设置弹层：显示在设置按钮上方 */}
        {showSettings && (
          <>
            {/* 透明遮罩：捕获外部点击关闭 */}
            <div className="settings-popover-backdrop" onClick={() => setShowSettings(false)} />
            <div className="settings-popover">
              <div className="settings-popover-title">设置</div>
              <div className="settings-popover-body">
                <div className="settings-label">外观</div>
                <div className="settings-row">
                  <span className="settings-row-label">主题</span>
                  <div className="theme-toggle">
                    <button
                      className={`theme-option${theme === 'light' ? ' active' : ''}`}
                      onClick={() => onThemeChange('light')}
                    >
                      ☀️ 浅色
                    </button>
                    <button
                      className={`theme-option${theme === 'dark' ? ' active' : ''}`}
                      onClick={() => onThemeChange('dark')}
                    >
                      🌙 深色
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
