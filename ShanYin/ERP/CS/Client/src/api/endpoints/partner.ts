import { apiClient } from '../client'

export interface PartnerRelation {
  id: number
  partner_id: number
  partner_name: string
  owner_type: 'business' | 'supply_chain' | 'ourselves'
  owner_id: number | null
  relation_type: string
  remark: string | null
  established_at: string | null
  ended_at: string | null
}

export const partnerApi = {
  relations: {
    list: (params?: { partner_id?: number; owner_type?: string; owner_id?: number; relation_type?: string }) =>
      apiClient.get<{ items: PartnerRelation[]; total: number }>('/partner-relations/list', { params }),
    create: (data: { partner_id: number; owner_type: string; owner_id?: number; relation_type: string; remark?: string }) =>
      apiClient.post('/partner-relations/create', data),
    delete: (ids: number[]) =>
      apiClient.delete('/partner-relations/delete', { data: ids.map(id => ({ id })) }),
  },
}
