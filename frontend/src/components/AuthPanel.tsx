import { useState } from 'react'
import { authLogin, authRegister } from '../api'
import logoIcon from '../assets/logo-icon.png'

type AuthMode = 'login' | 'register'

interface AuthPanelProps {
  onLogin: (username: string, token: string) => void
  onCancel?: () => void
}

/**
 * 登录 / 注册表单（可作为 Modal 内容复用）。
 *
 * 提供登录/注册模式切换、表单校验、注册后自动登录。
 */
export default function AuthPanel({ onLogin, onCancel }: AuthPanelProps) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const switchMode = (m: AuthMode) => {
    setMode(m)
    setError('')
  }

  const handleSubmit = async () => {
    const name = username.trim()
    if (!name || !password) {
      setError('请输入用户名和密码')
      return
    }
    if (mode === 'register' && password !== confirm) {
      setError('两次输入的密码不一致')
      return
    }
    setLoading(true)
    setError('')
    try {
      if (mode === 'login') {
        const data = await authLogin(name, password)
        onLogin(data.username, data.token)
      } else {
        await authRegister(name, password)
        // 注册成功后自动登录
        const data = await authLogin(name, password)
        onLogin(data.username, data.token)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-card">
      <div className="auth-logo">
        <img src={logoIcon} alt="精卫" />
      </div>
      <h2 className="auth-title">精卫</h2>
      <p className="auth-sub">企业级私有知识库 · RAG 智能问答</p>

      <div className="auth-tabs">
        <button
          className={`auth-tab${mode === 'login' ? ' active' : ''}`}
          onClick={() => switchMode('login')}
        >
          登录
        </button>
        <button
          className={`auth-tab${mode === 'register' ? ' active' : ''}`}
          onClick={() => switchMode('register')}
        >
          注册
        </button>
      </div>

      <div className="auth-form">
        <div className="auth-field">
          <label>用户名</label>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="请输入用户名"
            autoComplete="username"
          />
        </div>
        <div className="auth-field">
          <label>密码</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            placeholder={mode === 'register' ? '至少 6 位' : '请输入密码'}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          />
        </div>
        {mode === 'register' && (
          <div className="auth-field">
            <label>确认密码</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              placeholder="再次输入密码"
              autoComplete="new-password"
            />
          </div>
        )}

        {error && <div className="auth-error">{error}</div>}

        <button className="auth-submit" onClick={handleSubmit} disabled={loading}>
          {loading ? '处理中...' : mode === 'login' ? '登 录' : '注 册'}
        </button>
      </div>

      <div className="auth-foot">
        {onCancel ? (
          <button className="auth-cancel" onClick={onCancel}>
            取消
          </button>
        ) : (
          '登录后即可使用知识库问答与管理功能'
        )}
      </div>
    </div>
  )
}
