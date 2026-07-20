import { apiClient } from '../client'

// Backend constants (Chinese) — must match DB column business.status
export type BusinessStatus =
  | '前期接洽'
  | '业务评估'
  | '客户反馈'
  | '合作落地'
  | '业务开展'
  | '业务暂缓'
  | '业务终止'
  | '业务完成'

export interface Business {
  id: number
  customer_id: number
  status: string
  details: BusinessDetails
  timestamp: string
  virtual_contracts?: VirtualContractSummary[]
  // UI 需要的额外字段（服务器可能返回）
  customer_name?: string
  created_at?: string
}

export interface VirtualContractSummary {
  id: number
  type: string
  status: string
  total_amount?: number
}

export interface BusinessDetails {
  history?: StageTransition[]
  notes?: string
  pricing?: Record<string, { price: number; deposit: number }>
  payment_terms?: PaymentTerms
  contract_num?: string
  contracts?: Array<{ id: number; is_primary?: boolean }>
}

export interface StageTransition {
  from: string | null
  to: string
  time: string
  comment?: string
}

export interface PaymentTerms {
  prepayment_ratio: number
  balance_period: number
  day_rule: string
  start_trigger: string
}

export interface BusinessListResponse {
  items: Business[]
  total: number
  page: number
  size: number
}

export interface BusinessDetail extends Business {
  rules?: TimeRule[]
  partners?: BusinessPartnerRelation[]
}

export interface BusinessPartnerRelation {
  id: number
  partner_id: number
  partner_name: string
  owner_type: string
  owner_id: number | null
  relation_type: string
  remark: string
  established_at: string
  ended_at: string | null
  is_active: boolean
}

export interface TimeRule {
  id: number
  related_id: number
  related_type: string
  party: string
  trigger_event: string
  target_event: string
  offset: number
  unit: string
  direction: string
  inherit: number
  status: string
  warning?: string
  result?: string
}

export interface CreateBusinessSchema {
  customer_id: number
}

export interface AdvanceBusinessStageSchema {
  business_id: number
  next_status: string
  comment?: string
  pricing?: Record<string, { price: number; deposit: number }>
  payment_terms?: PaymentTerms
  contract_num?: string
}

// Addon Business — AddonType uses English keys, AddonStatus uses Chinese
export type AddonType = 'PRICE_ADJUST' | 'NEW_SKU' | 'PAYMENT_TERMS'
export type AddonStatus = '生效' | '失效' | '过期'

export interface AddonBusiness {
  id: number
  business_id: number
  business_name?: string
  customer_name?: string
  addon_type: string
  status: string
  sku_id?: number
  sku_name?: string
  override_price?: number
  override_deposit?: number
  start_date: string
  end_date?: string
  remark?: string
}

// 业务SKU协议价格表项（来自 details.pricing 或 NEW_SKU addon，addon 优先）
export interface SkuPriceItem {
  sku_id: number
  sku_name: string
  price: number
  deposit: number
  source: 'addon' | 'business_pricing'
}

export interface CreateAddonSchema {
  business_id: number
  addon_type: string
  sku_id?: number
  override_price?: number
  override_deposit?: number
  start_date: string
  end_date?: string
  remark?: string
}

export interface UpdateAddonSchema {
  addon_id: number
  start_date?: string
  end_date?: string
  override_price?: number
  override_deposit?: number
  status?: AddonStatus
  remark?: string
}

export const businessApi = {
  list: (params?: {
    ids?: number[]
    customer_id?: number
    status?: string
    date_from?: string
    date_to?: string
    customer_name_kw?: string
    sku_name_kw?: string
    page?: number
    size?: number
  }) => apiClient.get<BusinessListResponse>('/business/list', { params }) as unknown as Promise<BusinessListResponse>,

  getDetail: (bid: number) =>
    apiClient.get<BusinessDetail>(`/business/${bid}`) as unknown as Promise<BusinessDetail>,

  create: (data: CreateBusinessSchema) =>
    apiClient.post<{ success: boolean }>('/business/create', data) as unknown as Promise<{ success: boolean }>,

  delete: (businessId: number) =>
    apiClient.delete<{ success: boolean }>('/business/delete', { params: { business_id: businessId } }) as unknown as Promise<{ success: boolean }>,

  updateStatus: (data: { business_id: number; status: string; details?: BusinessDetails }) =>
    apiClient.post<{ success: boolean }>('/business/update-status', data) as unknown as Promise<{ success: boolean }>,

  advanceStage: (data: AdvanceBusinessStageSchema) =>
    apiClient.post<{ success: boolean }>('/business/advance-stage', data) as unknown as Promise<{ success: boolean }>,

  listAddons: (businessId: number, includeExpired = false) =>
    apiClient.get<AddonBusiness[]>(`/business/addons/list/${businessId}`, {
      params: { include_expired: includeExpired },
    }) as unknown as Promise<AddonBusiness[]>,

  listActiveAddons: (businessId: number) =>
    apiClient.get<AddonBusiness[]>(`/business/addons/active/${businessId}`) as unknown as Promise<AddonBusiness[]>,

  listAddonsGlobal: (params?: {
    business_id?: number
    customer_name_kw?: string
    sku_name_kw?: string
    status?: string
    page?: number
    size?: number
  }) =>
    apiClient.get<{ items: AddonBusiness[]; total: number; page: number; size: number }>(
      '/business/addons/global',
      { params }
    ) as unknown as Promise<{ items: AddonBusiness[]; total: number; page: number; size: number }>,

  getAddonDetail: (addonId: number) =>
    apiClient.get<AddonBusiness>(`/business/addons/detail/${addonId}`) as unknown as Promise<AddonBusiness>,

  getSkuPriceTable: (bid: number, includeEquipment?: boolean) => {
    console.log('[DEBUG] getSkuPriceTable called:', { bid, includeEquipment })
    return apiClient.get<SkuPriceItem[]>(`/business/${bid}/sku-price-table`, includeEquipment ? { params: { include_equipment: true } } : undefined) as unknown as Promise<SkuPriceItem[]>
  },

  createAddon: (data: CreateAddonSchema) =>
    apiClient.post<{ success: boolean }>('/business/addons/create', data) as unknown as Promise<{ success: boolean }>,

  updateAddon: (data: UpdateAddonSchema) =>
    apiClient.put<{ success: boolean }>('/business/addons/update', data) as unknown as Promise<{ success: boolean }>,

  deactivateAddon: (addonId: number) =>
    apiClient.post<{ success: boolean }>('/business/addons/deactivate', undefined, { params: { addon_id: addonId } }) as unknown as Promise<{ success: boolean }>,
}
