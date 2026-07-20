import { apiClient } from '../client'

// API uses Chinese values — must match desktop constants exactly
export type RuleRelatedType = '业务' | '供应链' | '虚拟合同' | '物流'
export type RuleParty = '我方' | '客户' | '供应商'
export type RuleUnit = '自然日' | '工作日' | '小时'
export type RuleDirection = 'before' | 'after'
export type RuleInherit = 0 | 1 | 2
export type RuleStatus = '失效' | '模板' | '生效' | '有结果' | '结束'
export type WarningLevel = 'GREEN' | 'YELLOW' | 'ORANGE' | 'RED'
export type RuleResult = '合规' | '违规'

// Full event list matching desktop EventType hierarchy
// Keys = DB values (Chinese), Labels = display text
export const RULE_EVENTS: Record<string, string> = {
  // Special
  '绝对日期': '绝对日期',
  // ContractLevel
  '合同签订': '合同签订',
  '合同生效': '合同生效',
  '合同到期': '合同到期',
  '合同更新': '合同更新',
  '合同终止': '合同终止',
  // VCLevel
  '虚拟合同创建': '虚拟合同创建',
  '虚拟合同执行': '虚拟合同执行',
  '虚拟合同完成': '虚拟合同完成',
  '合同物流发货': '合同物流发货',
  '合同物流签收': '合同物流签收',
  '合同标的完成': '合同标的完成',
  '合同预付完成': '合同预付完成',
  '合同款项结清': '合同款项结清',
  '合同货款结清': '合同货款结清',
  '合同押金收齐': '合同押金收齐',
  '合同押金退还': '合同押金退还',
  '付款比例达到': '付款比例达到',
  // LogisticsLevel
  '物流创建': '物流创建',
  '物流待发货': '物流待发货',
  '物流已发货': '物流已发货',
  '物流已签收': '物流已签收',
  '物流完成': '物流完成',
  '快递单创建': '快递单创建',
  '快递发出': '快递发出',
  '快递签收': '快递签收',
}

export const ALL_EVENTS = Object.entries(RULE_EVENTS).map(([key, label]) => ({ key, label }))
export const VC_EVENTS = ALL_EVENTS.filter(item =>
  !['绝对日期', '合同签订', '合同生效', '合同到期', '合同更新', '合同终止'].includes(item.key)
)
export const LOGISTICS_EVENTS = ALL_EVENTS.filter(item =>
  ['物流创建', '物流待发货', '物流已发货', '物流已签收', '物流完成', '快递单创建', '快递发出', '快递签收'].includes(item.key)
)

export interface TimeRule {
  id: number
  related_id: number
  related_type: RuleRelatedType
  party: RuleParty
  trigger_event: string
  target_event: string
  offset: number
  unit: RuleUnit
  direction: RuleDirection
  inherit: RuleInherit
  status: RuleStatus
  tge_param1?: string
  tge_param2?: string
  trigger_time?: string
  tae_param1?: string
  tae_param2?: string
  target_time?: string
  flag_time?: string
  warning?: WarningLevel
  result?: RuleResult
  created_at: string
  updated_at: string
}

export interface TimeRuleListResponse {
  items: TimeRule[]
  total: number
  page: number
  size: number
}

export interface CreateTimeRuleSchema {
  id?: number
  related_id: number
  related_type: RuleRelatedType
  party: RuleParty
  trigger_event: string
  target_event: string
  offset: number
  unit: RuleUnit
  direction: RuleDirection
  inherit: RuleInherit
  status: RuleStatus
  tge_param1?: string
  tge_param2?: string
  tae_param1?: string
  tae_param2?: string
  flag_time?: string
}

export interface SystemEvent {
  id: number
  event_type: string
  description?: string
  timestamp?: string
  aggregate_type?: string
  aggregate_id?: number
  payload?: Record<string, any>
  created_at?: string
  related_type?: string
  related_id?: number
}

export interface SystemEventsResponse {
  items: SystemEvent[]
  total: number
  page: number
  size: number
}

export const rulesApi = {
  list: (params?: {
    ids?: number[]
    related_id?: number
    related_type?: RuleRelatedType
    status?: RuleStatus
    date_from?: string
    date_to?: string
    page?: number
    size?: number
  }) => apiClient.get<TimeRuleListResponse>('/rules/list', { params }) as unknown as Promise<TimeRuleListResponse>,

  getDetail: (ruleId: number) =>
    apiClient.get<TimeRule>(`/rules/${ruleId}`) as unknown as Promise<TimeRule>,

  save: (data: CreateTimeRuleSchema) =>
    apiClient.post<{ success: boolean; data?: { rule_id: number } }>('/rules/save', data) as unknown as Promise<{ success: boolean; data?: { rule_id: number } }>,

  delete: (ruleId: number) =>
    apiClient.delete<{ success: boolean }>('/rules/delete', { params: { rule_id: ruleId } }) as unknown as Promise<{ success: boolean }>,

  getRecentEvents: (page = 1, size = 20, eventType?: string, aggregateType?: string) =>
    apiClient.get<SystemEventsResponse>('/events/recent', {
      params: { page, size, event_type: eventType || undefined, aggregate_type: aggregateType || undefined }
    }) as unknown as Promise<SystemEventsResponse>,
}
