import { create } from 'zustand'

interface User {
  id: number
  username: string
  role: string
  is_active: boolean
}

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean

  setTokens: (accessToken: string, refreshToken: string) => void
  setUser: (user: User) => void
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<boolean>
  clearAuth: () => void
}

const SESSION_TOKEN_KEY = 'auth_access_token'
const REFRESH_TOKEN_KEY = 'auth_refresh_token'

// API 地址：开发环境使用空值走 Vite proxy，远端部署时填服务器地址
const API_URL = import.meta.env.VITE_API_URL || ''

// 直接操作 sessionStorage/localStorage，不走 persist middleware
// accessToken: sessionStorage（仅当前标签页，XSS 无法跨标签页窃取）
// refreshToken: localStorage（跨标签页同步，7天过期）

export const useAuthStore = create<AuthState>()((set, get) => ({
  accessToken: sessionStorage.getItem(SESSION_TOKEN_KEY),
  refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY),
  user: null,
  isAuthenticated: !!sessionStorage.getItem(SESSION_TOKEN_KEY),
  isLoading: false,

  setTokens: (accessToken, refreshToken) => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, accessToken)
    if (refreshToken) {
      localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
    }
    set({ accessToken, refreshToken, isAuthenticated: true })
  },

  setUser: (user) => {
    set({ user })
  },

  login: async (username, password) => {
    set({ isLoading: true })
    try {
      const response = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })

      if (!response.ok) {
        throw new Error('登录失败')
      }

      const data = await response.json()
      // 支持两种格式：远端 {success, data: {access_token}} 或 本地 {access_token}
      const token = data?.data?.access_token || data?.access_token
      const refreshToken = data?.data?.refresh_token || data?.refresh_token

      get().setTokens(token, refreshToken)

      // 登录后获取用户信息
      const meRes = await fetch(`${API_URL}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (meRes.ok) {
        const meData = await meRes.json()
        set({ user: meData.data, isLoading: false })
      } else {
        set({ isLoading: false })
      }
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },

  logout: async () => {
    const refreshToken = get().refreshToken
    const accessToken = get().accessToken

    // 尝试通知服务器撤销 refresh token（失败不影响本地登出）
    if (refreshToken && accessToken) {
      try {
        await fetch(`${API_URL}/api/v1/auth/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
      } catch {
        // 忽略网络错误
      }
    }

    get().clearAuth()
  },

  refresh: async () => {
    const refreshToken = get().refreshToken
    if (!refreshToken) {
      get().clearAuth()
      return false
    }

    try {
      const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })

      if (!res.ok) {
        get().clearAuth()
        return false
      }

      const data = await res.json()
      // server /refresh 返回 api_success 格式 {success: true, data: {access_token, refresh_token}}
      const token = data?.data?.access_token || data?.access_token
      const newRefresh = data?.data?.refresh_token || data?.refresh_token
      get().setTokens(token, newRefresh)
      return true
    } catch {
      get().clearAuth()
      return false
    }
  },

  clearAuth: () => {
    sessionStorage.removeItem(SESSION_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    set({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false })
  },
}))
