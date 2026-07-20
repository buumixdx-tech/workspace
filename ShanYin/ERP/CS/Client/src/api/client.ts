/// <reference types="vite/client" />
import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

// API 地址配置
// 本地开发: 使用空值走 Vite proxy
// 远端部署: VITE_API_URL=https://your-server.com
const API_URL = import.meta.env.VITE_API_URL || ''
const API_BASE = API_URL ? `${API_URL}/api/v1` : '/api/v1'

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: false,
})

// Track if we're currently refreshing to prevent multiple refresh calls
let isRefreshing = false
let failedQueue: Array<{
  resolve: (value: unknown) => void
  reject: (reason?: unknown) => void
}> = []

// Cleanup on HMR
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    isRefreshing = false
    failedQueue = []
  })
}

const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

// Request interceptor: add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().accessToken
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle 401 and token refresh
apiClient.interceptors.response.use(
  (response) => {
    // 服务端返回 {success: true, data: {...}} 格式
    if (response.data?.success !== undefined) {
      if (!response.data.success) {
        throw new Error(response.data.error?.message || response.data.error || '操作失败')
      }
      // 返回 data 字段内容，而不是整个 wrapper
      return response.data.data
    }
    return response.data
  },
  async (error) => {
    const originalRequest = error.config

    // Handle 401 - token expired
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Queue the request while refreshing
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            return apiClient(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        await useAuthStore.getState().refresh()
        const newToken = useAuthStore.getState().accessToken
        processQueue(null, newToken)
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return apiClient(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError as Error, null)
        useAuthStore.getState().clearAuth()
        window.location.href = import.meta.env.BASE_URL + '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    const detail = error.response?.data?.detail
    const message = Array.isArray(detail)
      ? detail.map((e: any) => e.msg || JSON.stringify(e)).join('; ')
      : (typeof detail === 'string' ? detail : error.message)
      || '网络错误'
    return Promise.reject(new Error(message))
  }
)
