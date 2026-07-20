import { apiClient } from '../client'

export type OperationalStatus = 'IN_STOCK' | 'IN_OPERATION' | 'DISPOSAL'
export type DeviceStatus = 'NORMAL' | 'MAINTENANCE' | 'DAMAGED' | 'FAULT' | 'MAINTENANCE_REQUIRED' | 'LOCKED'

// 服务端实际返回的设备库存
export interface EquipmentInventory {
  sn: string
  sku_id: number
  sku_name: string
  operational_status: OperationalStatus
  device_status: DeviceStatus
  vc_id?: number
  point_id?: number
  point_name?: string
  deposit_amount: number
  created_at: string
  updated_at: string
}

// 服务端实际返回的物料库存（按批次）
export interface MaterialInventory {
  id: number
  sku_id: number
  sku_name: string
  batch_no: string
  warehouse_point_id: number
  warehouse_point_name: string
  quantity: number
  average_price: number
  vc_id: number
  production_date?: string
  expiration_date?: string
  certificate_file?: string
}

export interface EquipmentListResponse {
  items: EquipmentInventory[]
  total: number
  page: number
  size: number
}

export interface MaterialListResponse {
  items: MaterialInventory[]
  total: number
  page: number
  size: number
}

// 有库存的物料 SKU
export interface MaterialSkuWithStock {
  sku_id: number
  sku_name: string
  batch_count: number
  total_qty: number
}

// 物料批次（仓库+批次组合）
export interface MaterialBatch {
  inventory_id: number
  batch_no: string
  warehouse_point_id: number
  warehouse_point_name: string
  quantity: number
  average_price: number
  production_date: string
  display: string
}

export const inventoryApi = {
  getEquipment: (params?: {
    vc_id?: number
    point_id?: number
    sku_id?: number
    operational_status?: OperationalStatus
    device_status?: DeviceStatus
    sn?: string
    deposit_amount_min?: number
    deposit_amount_max?: number
    page?: number
    size?: number
  }) => apiClient.get<EquipmentListResponse>('/inventory/equipment', { params }) as unknown as Promise<EquipmentListResponse>,

  getMaterial: (params?: {
    sku_id?: number
    warehouse_point_id?: number
    page?: number
    size?: number
  }) => apiClient.get<MaterialListResponse>('/inventory/material', { params }) as unknown as Promise<MaterialListResponse>,

  getMaterialSkusWithStock: () =>
    apiClient.get<MaterialSkuWithStock[]>('/inventory/material-skus-with-stock') as unknown as Promise<MaterialSkuWithStock[]>,

  getMaterialBatches: (skuId: number) =>
    apiClient.get<MaterialBatch[]>('/inventory/material-batches', { params: { sku_id: skuId } }) as unknown as Promise<MaterialBatch[]>,
}
