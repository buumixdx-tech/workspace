import { apiClient } from '../client'

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface User {
  id: number
  username: string
  role: string
  is_active: boolean
  created_at?: string
}

export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<LoginResponse>('/auth/login', data).then(r => r.data) as unknown as Promise<LoginResponse>,

  refresh: (refresh_token: string) =>
    apiClient.post<LoginResponse>('/auth/refresh', { refresh_token }).then(r => r.data) as unknown as Promise<LoginResponse>,

  logout: (refresh_token: string) =>
    apiClient.post('/auth/logout', { refresh_token }),

  getMe: () =>
    apiClient.get<User>('/auth/me').then(r => r.data) as unknown as Promise<User>,

  changePassword: (old_password: string, new_password: string) =>
    apiClient.put('/auth/me/password', { old_password, new_password }),
}
