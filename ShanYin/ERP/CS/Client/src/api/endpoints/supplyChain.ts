import { apiClient } from '../client'

export type SupplyChainType = '设备' | '物料'

export interface SupplyChainItem {
  sku_id: number
  sku_name: string
  price: number
  deposit: number
  is_floating: boolean
}

export interface SupplyChain {
  id: number
  supplier_id: number
  supplier_name: string
  type: SupplyChainType
  items: SupplyChainItem[]
  payment_terms: PaymentTerms
  contract_num?: string
  status: string
  created_at: string
  updated_at: string
}

export interface PaymentTerms {
  prepayment_percent: number
  payment_days: number
  payment_method?: string
}

export interface SupplyChainListResponse {
  items: SupplyChain[]
  total: number
  page: number
  size: number
}

export interface SupplyChainDetail extends SupplyChain {
}

export interface CreateSupplyChainSchema {
  supplier_id: number
  supplier_name: string
  type: SupplyChainType
  items: { sku_id: number; price: number; is_floating?: boolean }[]
  payment_terms: PaymentTerms
  contract_num?: string
}

export interface UpdateSupplyChainSchema {
  id: number
  supplier_name: string
  type: SupplyChainType
  items: { sku_id: number; price: number; is_floating?: boolean }[]
  payment_terms: PaymentTerms
}

export const supplyChainApi = {
  list: (params?: {
    ids?: number[]
    supplier_id?: number
    status?: string
    type?: SupplyChainType
    date_from?: string
    date_to?: string
    supplier_name_kw?: string
    sku_name_kw?: string
    page?: number
    size?: number
  }) => apiClient.get<SupplyChainListResponse>('/supply-chain/list', { params }) as unknown as Promise<SupplyChainListResponse>,

  getDetail: (scId: number) =>
    apiClient.get<SupplyChainDetail>(`/supply-chain/${scId}`) as unknown as Promise<SupplyChainDetail>,

  create: (data: CreateSupplyChainSchema) =>
    apiClient.post<{ success: boolean; data?: SupplyChain }>('/supply-chain/create', data) as unknown as Promise<{ success: boolean; data?: SupplyChain }>,

  update: (data: UpdateSupplyChainSchema) =>
    apiClient.put<{ success: boolean }>(`/supply-chain/${data.id}`, data) as unknown as Promise<{ success: boolean }>,

  delete: (scId: number) =>
    apiClient.delete<{ success: boolean }>(`/supply-chain/${scId}`) as unknown as Promise<{ success: boolean }>,
}
