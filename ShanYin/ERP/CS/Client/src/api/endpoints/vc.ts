import { apiClient } from '../client'

// Backend constants (Chinese)
export type VCStatus = '执行' | '完成' | '终止' | '取消'
export type VCSubjectStatus = '执行' | '发货' | '签收' | '完成'
export type VCCashStatus = '执行' | '预付' | '完成'
export type VCType =
  | '设备采购'
  | '库存采购'
  | '库存拨付'
  | '物料采购'
  | '物料供应'
  | '退货'

// 服务端实际返回的 VCElement
export interface VCElement {
  id?: string
  shipping_point_id: number
  receiving_point_id: number
  sku_id: number
  batch_no?: string
  qty: number
  price: number
  deposit: number
  subtotal: number
  sn_list?: string[]
  addon_business_ids?: number[]
  sku_name?: string
  shipping_point_name?: string
  receiving_point_name?: string
}

// 服务端返回的 elements 结构是包装过的
export interface VCElementsWrapper {
  elements: VCElement[]
  total_amount: number
  payment_terms?: {
    prepayment_ratio: number
    balance_period: number
    day_rule: string
    start_trigger: string
  }
}

export interface DepositInfo {
  expected_deposit: number
  actual_deposit: number
  total_amount: number
  should_receive: number
  prepayment_ratio: number
}

// 服务端实际返回的 VirtualContract
export interface VirtualContract {
  id: number
  business_id?: number
  supply_chain_id?: number
  related_vc_id?: number
  type: string
  status: string
  subject_status: string
  cash_status: string
  description: string
  elements: VCElementsWrapper
  deposit_info?: {
    prepayment_ratio?: number
    expected_deposit?: number
    actual_deposit?: number
    should_receive?: number
    offset_pool?: number
    paid_amount?: number
    balance?: number
  }
  total_amount?: number
  status_timestamp?: string
  status_logs?: VCStatusLog[]
  logistics?: LogisticsSummary[]
  cash_flows?: CashFlowItem[]
  created_at?: string
  updated_at?: string
  transaction_date?: string
  counterparty?: string
}

export interface VCStatusLog {
  id: number
  vc_id?: number
  category?: string
  status_name: string
  timestamp: string
  transaction_date?: string
  from_status?: string
  to_status?: string
  changed_field?: string
  operator?: string
  comment?: string
}

export interface VCListResponse {
  items: VirtualContract[]
  total: number
  page: number
  size: number
}

export interface VCDetailResponse extends VirtualContract {
  status_logs: VCStatusLog[]
  logistics: LogisticsSummary[]
  cash_flows: CashFlowItem[]
  // 可能从联表查询返回的额外字段
  business_name?: string
  supply_chain_name?: string
  // 物料供应 VC 关联的合作方关系（简化字段）
  partner_relation?: {
    id: number
    partner_id: number
    partner_name: string
    relation_type: string
  }
}

export interface LogisticsSummary {
  id: number
  virtual_contract_id?: number
  status: string
  timestamp: string
  express_orders: ExpressOrder[]
}

export interface ExpressOrder {
  id: number
  tracking_number: string
  status: string
  address_info: {
    收货点位Id: number
    收货点位名称: string
    收货地址: string
    收货联系电话: string | null
    发货点位Id: number
    发货点位名称: string
    发货地址: string
    发货联系电话: string | null
  }
  items: { sku_id: number; sku_name: string; qty: number }[]
}

export interface CashFlowItem {
  id: number
  type: string
  amount: number
  transaction_date: string
}

export interface CreateProcurementVC {
  business_id: number
  sc_id?: number
  elements: VCElement[]
  total_amt: number
  total_deposit: number
  payment: {
    prepayment_ratio: number
    balance_period: number
    day_rule: string
    start_trigger: string
  }
  description?: string
  created_date?: string
}

export interface CreateStockProcurementVC {
  sc_id: number
  elements: VCElement[]
  total_amt: number
  payment: {
    prepayment_ratio: number
    balance_period: number
    day_rule: string
    start_trigger: string
  }
  description?: string
  created_date?: string
}

export interface CreateMaterialSupplyVC {
  business_id: number
  elements: VCElement[]
  total_amt: number
  description?: string
  created_date?: string
}

export interface CreateMatProcurementVC {
  sc_id: number
  elements: VCElement[]
  total_amt: number
  payment: {
    prepayment_ratio: number
    balance_period: number
    day_rule: string
    start_trigger: string
  }
  description?: string
  created_date?: string
}

export interface CreateReturnVC {
  target_vc_id: number
  return_direction: 'CUSTOMER_TO_US' | 'US_TO_SUPPLIER'
  receiving_point_id: number
  elements: VCElement[]
  goods_amount: number
  deposit_amount: number
  logistics_cost: number
  logistics_bearer: string
  total_refund: number
  reason?: string
  description?: string
  created_date?: string
}

export interface AllocateInventoryVC {
  business_id: number
  elements: VCElement[]
  description?: string
  created_date?: string
}

export interface ReturnableItem {
  vc_element_id: string
  sku_id: number
  sku_name: string
  original_vc_id: number
  original_vc_type: string
  returnable_qty: number
  sn_list: string[]
  batch_no?: string
  price: number
  deposit: number
}

export interface CashflowProgress {
  is_return: boolean
  goods: {
    total: number
    paid: number
    balance: number
    pool: number
    due: number
    label: string
    paid_label: string
    balance_label: string
  }
  deposit: {
    should: number
    received: number
    remaining: number
  }
  payment_terms: Record<string, unknown>
}

export interface VCGlobalSearchParams {
  vc_id?: number
  vc_type?: string
  vc_status?: string
  vc_subject_status?: string
  vc_cash_status?: string
  business_id?: number
  business_customer_name_kw?: string
  supply_chain_id?: number
  supply_chain_supplier_name_kw?: string
  sku_id?: number
  sku_name_kw?: string
  shipping_point_id?: number
  shipping_point_name_kw?: string
  receiving_point_id?: number
  receiving_point_name_kw?: string
  tracking_number?: string
  vc_date_from?: string
  vc_date_to?: string
  batch_no?: string
  page?: number
  size?: number
}

export const vcApi = {
  list: (params?: {
    ids?: number[]
    business_id?: number
    type?: string
    status?: string
    cash_status?: string
    subject_status?: string
    date_from?: string
    date_to?: string
    search?: string
    has_logistics?: boolean
    page?: number
    size?: number
  }) => apiClient.get<VCListResponse>('/vc/list', { params }) as unknown as Promise<VCListResponse>,

  getDetail: (vcId: number) =>
    apiClient.get<VCDetailResponse>(`/vc/${vcId}`) as unknown as Promise<VCDetailResponse>,

  getGlobalOverview: (params?: VCGlobalSearchParams) =>
    apiClient.get<VCListResponse>('/vc/global', { params }) as unknown as Promise<VCListResponse>,

  getReturnable: (params?: { status?: string; subject_status?: string }) =>
    apiClient.get<VCListResponse>('/vc/returnable', { params }) as unknown as Promise<VCListResponse>,

  createProcurement: (data: CreateProcurementVC, draftRules?: unknown[]) =>
    apiClient.post<VirtualContract>('/vc/create-procurement', { vc: data, draft_rules: draftRules }) as unknown as Promise<VirtualContract>,

  createStockProcurement: (data: CreateStockProcurementVC, draftRules?: unknown[]) =>
    apiClient.post<VirtualContract>('/vc/create-stock-procurement', { vc: data, draft_rules: draftRules }) as unknown as Promise<VirtualContract>,

  createMaterialSupply: (data: CreateMaterialSupplyVC, draftRules?: unknown[]) =>
    apiClient.post<VirtualContract>('/vc/create-material-supply', { vc: data, draft_rules: draftRules }) as unknown as Promise<VirtualContract>,

  createMatProcurement: (data: CreateMatProcurementVC, draftRules?: unknown[]) =>
    apiClient.post<VirtualContract>('/vc/create-mat-procurement', { vc: data, draft_rules: draftRules }) as unknown as Promise<VirtualContract>,

  createReturn: (data: CreateReturnVC, draftRules?: unknown[]) =>
    apiClient.post<VirtualContract>('/vc/create-return', { vc: data, draft_rules: draftRules }) as unknown as Promise<VirtualContract>,

  allocateInventory: (data: AllocateInventoryVC) =>
    apiClient.post<{ success: boolean }>('/vc/create-allocate-inventory', data) as unknown as Promise<{ success: boolean }>,

  update: (data: { vc_id: number; description?: string; elements?: VCElement[]; deposit_info?: DepositInfo }) =>
    apiClient.put<{ success: boolean }>('/vc/update', data) as unknown as Promise<{ success: boolean }>,

  delete: (vcId: number) =>
    apiClient.delete<{ success: boolean }>('/vc/delete', { params: { vc_id: vcId } }) as unknown as Promise<{ success: boolean }>,

  getReturnableItems: (vcId: number, direction: string) =>
    apiClient.get<ReturnableItem[]>('/query/returnable-items', { params: { vc_id: vcId, direction } }) as unknown as Promise<ReturnableItem[]>,

  getCashflowProgress: (vcId: number) =>
    apiClient.get<CashflowProgress>('/query/cashflow-progress', { params: { vc_id: vcId } }) as unknown as Promise<CashflowProgress>,
}
