// 合作方关系类型 PartnerRelationType
export const PARTNER_RELATION_TYPES = {
  LOGISTICS: '物流服务',
  OPERATION: '运维服务',
  CUSTOMER_SERVICE: '客服服务',
  TECHNICAL: '技术服务',
  CONSULTING: '咨询服务',
  PROCUREMENT: '采购执行',
  MARKETING: '营销推广',
  INVESTMENT: '投资关联',
  OTHER: '其他',
} as const

// 外部合作方类型 ExternalPartnerType
export const EXTERNAL_PARTNER_TYPES = {
  SUPPLY_CHAIN_COMPANY: '供应链公司',
  OPERATION_OUTSOURCING: '运维外包公司',
  CUSTOMER_SERVICE_OUTSOURCING: '客服外包公司',
  TECHNICAL_SERVICE: '技术服务公司',
  CONSULTING_SERVICE: '咨询服务公司',
  LOGISTICS_COMPANY: '物流公司',
  RELATED_COMPANY: '关联公司',
} as const

// 账户所有者类型 AccountOwnerType
export const ACCOUNT_OWNER_TYPES = {
  OURSELVES: 'Ourselves',
  CUSTOMER: 'Customer',
  SUPPLIER: 'Supplier',
  PARTNER: 'Partner',
} as const

// 点位类型
export const POINT_TYPES = {
  OPERATING: '运营点位',
  CUSTOMER_WAREHOUSE: '客户仓',
  OWN_WAREHOUSE: '自有仓',
  SUPPLIER_WAREHOUSE: '供应商仓',
  TRANSIT_WAREHOUSE: '转运仓',
} as const

// 所有者类型（用于 PartnerRelation.owner_type）
export const OWNER_TYPES = {
  BUSINESS: 'business',
  SUPPLY_CHAIN: 'supply_chain',
  OURSELVES: 'ourselves',
} as const
