import { apiClient } from '../client'

// 服务端实际返回的数据结构
export interface Customer {
  id: number
  name: string
  info: Record<string, unknown> | string | null
  status: string | null
  created_at?: string
  updated_at?: string
}

export interface Point {
  id: number
  name: string
  type: string
  address: string
  customer_id: number | null
  supplier_id: number | null
  owner_name?: string | null
  owner_type?: string | null
}

export interface Supplier {
  id: number
  name: string
  category: string | null
  address: string | null
  info: Record<string, unknown> | null
}

export interface SKU {
  id: number
  name: string
  type_level1: string | null
  type_level2: string | null
  model: string | null
  params: Record<string, unknown>
  supplier_id: number | null
  unit?: string
  deposit?: number
}

export interface Partner {
  id: number
  name: string
  type: string
  address: string | null
  contact_info: string | null
  content: string | null
}

export interface BankAccount {
  id: number
  owner_type: string
  owner_id: number | null
  owner_name: string
  bank_name: string
  account_no: string
  is_default: boolean
  status: string
  account_info: {
    开户名称: string
    银行名称: string
    银行账号: string
  }
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export const masterApi = {
  customers: {
    list: (params?: { page?: number; size?: number; search?: string }) =>
      apiClient.get<PaginatedResponse<Customer>>('/master/customers', { params }) as unknown as Promise<PaginatedResponse<Customer>>,
    create: (data: Partial<Customer>) =>
      apiClient.post<{ success: boolean }>('/master/create-customer', data) as unknown as Promise<{ success: boolean }>,
    update: (data: Partial<Customer>[]) =>
      apiClient.put<{ success: boolean }>('/master/update-customers', data) as unknown as Promise<{ success: boolean }>,
    delete: (ids: number[]) =>
      apiClient.delete<{ success: boolean }>('/master/delete-customers', { data: ids.map(id => ({ id })) }) as unknown as Promise<{ success: boolean }>,
  },
  points: {
    list: (params?: { page?: number; size?: number; customer_id?: number; type?: string; search?: string }) =>
      apiClient.get<PaginatedResponse<Point>>('/master/points', { params }) as unknown as Promise<PaginatedResponse<Point>>,
    create: (data: Partial<Point>) =>
      apiClient.post<{ success: boolean }>('/master/create-point', data) as unknown as Promise<{ success: boolean }>,
    update: (data: Partial<Point>[]) =>
      apiClient.put<{ success: boolean }>('/master/update-points', data) as unknown as Promise<{ success: boolean }>,
    delete: (ids: number[]) =>
      apiClient.delete<{ success: boolean }>('/master/delete-points', { data: ids.map(id => ({ id })) }) as unknown as Promise<{ success: boolean }>,
  },
  suppliers: {
    list: (params?: { page?: number; size?: number; category?: string; search?: string }) =>
      apiClient.get<PaginatedResponse<Supplier>>('/master/suppliers', { params }) as unknown as Promise<PaginatedResponse<Supplier>>,
    create: (data: Partial<Supplier>) =>
      apiClient.post<{ success: boolean }>('/master/create-supplier', data) as unknown as Promise<{ success: boolean }>,
    update: (data: Partial<Supplier>[]) =>
      apiClient.put<{ success: boolean }>('/master/update-suppliers', data) as unknown as Promise<{ success: boolean }>,
    delete: (ids: number[]) =>
      apiClient.delete<{ success: boolean }>('/master/delete-suppliers', { data: ids.map(id => ({ id })) }) as unknown as Promise<{ success: boolean }>,
  },
  skus: {
    list: (params?: { page?: number; size?: number; supplier_id?: number; search?: string }) =>
      apiClient.get<PaginatedResponse<SKU>>('/master/skus', { params }) as unknown as Promise<PaginatedResponse<SKU>>,
    create: (data: Partial<SKU>) =>
      apiClient.post<{ success: boolean }>('/master/create-sku', data) as unknown as Promise<{ success: boolean }>,
    update: (data: Partial<SKU>[]) =>
      apiClient.put<{ success: boolean }>('/master/update-skus', data) as unknown as Promise<{ success: boolean }>,
    delete: (ids: number[]) =>
      apiClient.delete<{ success: boolean }>('/master/delete-skus', { data: ids.map(id => ({ id })) }) as unknown as Promise<{ success: boolean }>,
  },
  partners: {
    list: (params?: { page?: number; size?: number; search?: string }) =>
      apiClient.get<PaginatedResponse<Partner>>('/master/partners', { params }) as unknown as Promise<PaginatedResponse<Partner>>,
    create: (data: Partial<Partner>) =>
      apiClient.post<{ success: boolean }>('/master/create-partner', data) as unknown as Promise<{ success: boolean }>,
    update: (data: Partial<Partner>[]) =>
      apiClient.put<{ success: boolean }>('/master/update-partners', data) as unknown as Promise<{ success: boolean }>,
    delete: (ids: number[]) =>
      apiClient.delete<{ success: boolean }>('/master/delete-partners', { data: ids.map(id => ({ id })) }) as unknown as Promise<{ success: boolean }>,
  },
  bankAccounts: {
    list: (params?: { page?: number; size?: number; owner_type?: string }) =>
      apiClient.get<BankAccount[]>('/master/bank-accounts', { params }) as unknown as Promise<BankAccount[]>,
    create: (data: { owner_type: string; account_info: { account_name: string; bank_name: string; account_no: string }; is_default?: boolean }) =>
      apiClient.post<{ success: boolean }>('/master/create-bank-account', data) as unknown as Promise<{ success: boolean }>,
    update: (data: { id: number; owner_type?: string; account_info?: { account_name?: string; bank_name?: string; account_no?: string }; is_default?: boolean }[]) =>
      apiClient.put<{ success: boolean }>('/master/update-bank-accounts', data) as unknown as Promise<{ success: boolean }>,
    delete: (ids: number[]) =>
      apiClient.delete<{ success: boolean }>('/master/delete-bank-accounts', { data: ids.map(id => ({ id })) }) as unknown as Promise<{ success: boolean }>,
  },
}
