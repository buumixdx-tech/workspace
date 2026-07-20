import { useState } from 'react'
import { useAuth } from '../App'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const { login } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await login(username, password)
    } catch (err) {
      setError(err.response?.data?.message || '登录失败')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-card shadow-card p-8">
          <h1 className="text-2xl font-bold text-center mb-2">资产管理系统</h1>
          <p className="text-text-secondary text-center mb-8">投影仪灯泡管理</p>

          {error && (
            <div className="bg-red-50 text-danger text-sm p-3 rounded-btn mb-4">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">
                用户名
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-input focus:border-primary"
                placeholder="请输入用户名"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">
                密码
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-input focus:border-primary"
                placeholder="请输入密码"
                required
              />
            </div>
            <button
              type="submit"
              className="w-full bg-primary text-white py-2 rounded-btn hover:bg-blue-600 transition-colors"
            >
              登录
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
