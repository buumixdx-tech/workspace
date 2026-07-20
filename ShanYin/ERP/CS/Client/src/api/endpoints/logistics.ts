import { apiClient } from '../client'

// Backend constants (Chinese)
export type LogisticsStatus = '待发货' | '在途' | '签收' | '完成' | '取消'
export type ExpressStatus = '待发货' | '在途' | '签收'

export interface ExpressItem {
  sku_id: number
  sku_name: string
  qty: number
}

// 服务端实际返回的地址信息（中文 key）
export interface AddressInfo {
  收货点位Id: number
  收货点位名称: string
  收货地址: string
  收货联系电话: string | null
  发货点位Id: number
  发货点位名称: string
  发货地址: string
  发货联系电话: string | null
}

export interface ExpressOrder {
  id: number
  tracking_number: string
  status: string
  address_info: AddressInfo
  items: ExpressItem[]
}

export interface Logistics {
  id: number
  virtual_contract_id: number
  status: string
  created_at: string
  express_orders_count: number
}

export interface LogisticsDetail extends Logistics {
  express_orders: ExpressOrder[]
  vc_type?: string
  transaction_date?: string
  elements?: Array<{
    shipping_point_id?: number
    shipping_point_name?: string
    receiving_point_id?: number
    receiving_point_name?: string
    sku_id: number
    sku_name: string
    qty: number
    price?: number
  }>
}

export interface LogisticsListResponse {
  items: Logistics[]
  total: number
  page: number
  size: number
}

export interface LogisticsDashboardSummary {
  logistics_summary: {
    total: number
    pending: number
    transit: number
    signed: number
    finish: number
    today_new: number
  }
  express_summary: {
    total: number
    pending: number
    transit: number
    signed: number
  }
}

export interface CreateLogisticsPlanSchema {
  vc_id: number
  orders: {
    tracking_number: string
    items: { sku_id: number; qty: number }[]
    address_info: AddressInfo
  }[]
  created_date?: string
}

export interface BatchItem {
  sku_id: number
  production_date: string
  receiving_point_id: number
  qty: number
  certificate_filename?: string
}

export interface ConfirmInboundSchema {
  log_id: number
  sn_list: string[]
  batch_items?: BatchItem[]
  created_date?: string
}

export interface ExpressOrderStatusSchema {
  order_id: number
  target_status: ExpressStatus
  logistics_id: number
  created_date?: string
}

export interface BatchItemWithFile extends BatchItem {
  certificate_file?: File
}

// Express Order Global Overview types
export interface ExpressOrderGlobalItem {
  id: number
  tracking_number: string
  status: ExpressStatus
  created_at: string
  transaction_date?: string
  logistics_id: number
  items: Array<{ sku_id: number; sku_name: string; qty: number }>
  address_info: AddressInfo
  vc_id: number | null
  vc_type: string | null
  vc_subject_status: string | null
}

export interface ExpressOrderGlobalResponse {
  items: ExpressOrderGlobalItem[]
  total: number
  page: number
  size: number
}

export interface ExpressOrderGlobalParams {
  ids?: number
  tracking_number?: string
  status?: ExpressStatus
  date_from?: string
  date_to?: string
  sku_id?: number
  sku_name_kw?: string
  shipping_point_id?: number
  shipping_point_name_kw?: string
  receiving_point_id?: number
  receiving_point_name_kw?: string
  vc_id?: number
  vc_type?: string
  vc_status_type?: '主状态' | '合同状态'
  vc_status_value?: string
  subject_status?: string
  business_id?: number
  business_customer_name_kw?: string
  supply_chain_id?: number
  supply_chain_supplier_name_kw?: string
  page?: number
  size?: number
}

// Logistics Global Overview types
export interface LogisticsGlobalItem {
  id: number
  virtual_contract_id: number
  status: LogisticsStatus
  created_at: string
  transaction_date?: string
  express_orders_count: number
  vc_type: string | null
}

export interface LogisticsGlobalResponse {
  items: LogisticsGlobalItem[]
  total: number
  page: number
  size: number
}

export interface LogisticsGlobalParams {
  ids?: number
  status?: LogisticsStatus
  date_from?: string
  date_to?: string
  tracking_number?: string
  express_order_id?: number
  sku_id?: number
  sku_name_kw?: string
  shipping_point_id?: number
  shipping_point_name_kw?: string
  receiving_point_id?: number
  receiving_point_name_kw?: string
  vc_id?: number
  vc_type?: string
  vc_status_type?: '主状态' | '合同状态'
  vc_status_value?: string
  subject_status?: string
  business_id?: number
  business_customer_name_kw?: string
  supply_chain_id?: number
  supply_chain_supplier_name_kw?: string
  page?: number
  size?: number
}

export const logisticsApi = {
  list: (params?: {
    ids?: number[]
    vc_id?: number
    status?: string
    date_from?: string
    date_to?: string
    tracking_number?: string
    page?: number
    size?: number
  }) => apiClient.get<LogisticsListResponse>('/logistics/list', { params }) as unknown as Promise<LogisticsListResponse>,

  getDetail: (logId: number) =>
    apiClient.get<LogisticsDetail>(`/logistics/${logId}`) as unknown as Promise<LogisticsDetail>,

  createPlan: (data: CreateLogisticsPlanSchema) =>
    apiClient.post<{ success: boolean }>('/logistics/create-plan', data) as unknown as Promise<{ success: boolean }>,

  confirmInbound: (data: ConfirmInboundSchema) =>
    apiClient.post<{ success: boolean }>('/logistics/confirm-inbound', data) as unknown as Promise<{ success: boolean }>,

  confirmInboundMaterial: (data: {
    log_id: number
    sn_list: string[]
    batch_items: BatchItem[]
    certificates: File[]
    created_date?: string
  }) => {
    const formData = new FormData()
    formData.append('log_id', String(data.log_id))
    formData.append('sn_list', JSON.stringify(data.sn_list))
    formData.append('batch_items_json', JSON.stringify(data.batch_items))
    if (data.created_date) formData.append('created_date', data.created_date)
    data.certificates.forEach((file) => formData.append('certificates', file))
    return apiClient.post('/logistics/confirm-inbound-material', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }) as unknown as Promise<{ success: boolean }>
  },

  updateExpressOrder: (data: {
    order_id: number
    tracking_number: string
    address_info: AddressInfo
  }) => apiClient.put<{ success: boolean }>('/logistics/update-express', data) as unknown as Promise<{ success: boolean }>,

  updateExpressStatus: (data: ExpressOrderStatusSchema) =>
    apiClient.post<{ success: boolean }>('/logistics/update-express-status', data) as unknown as Promise<{ success: boolean }>,

  bulkProgress: (data: {
    order_ids: number[]
    target_status: ExpressStatus
    logistics_id: number
    created_date?: string
  }) => apiClient.post<{ success: boolean }>('/logistics/bulk-progress', data) as unknown as Promise<{ success: boolean }>,

  getDashboardSummary: () =>
    apiClient.get<LogisticsDashboardSummary>('/logistics/dashboard/summary') as unknown as Promise<LogisticsDashboardSummary>,

  getExpressOrdersGlobal: (params: ExpressOrderGlobalParams) =>
    apiClient.get<ExpressOrderGlobalResponse>('/logistics/express-orders/global', { params }) as unknown as Promise<ExpressOrderGlobalResponse>,

  getLogisticsGlobal: (params: LogisticsGlobalParams) =>
    apiClient.get<LogisticsGlobalResponse>('/logistics/global', { params }) as unknown as Promise<LogisticsGlobalResponse>,
}
