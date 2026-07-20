import { apiClient } from '../client'

export type CashFlowType =
  | '预付'
  | '履约'
  | '押金'
  | '退还押金'
  | '罚金'
  | '退款'
  | '冲抵支付'
  | '冲抵入金'
  | '押金冲抵入金'
export type CashFlowDirection = 'INFLOW' | 'OUTFLOW'

// 服务端实际返回的 CashFlow 结构
export interface CashFlow {
  id: number
  virtual_contract_id: number
  vc_type?: string
  type: string
  amount: number
  payer_account_id: number
  payee_account_id: number
  payer_owner_type?: string
  payee_owner_type?: string
  transaction_date: string
  description: string
  payer_account_name?: string
  payee_account_name?: string
  direction?: string
}

export interface CashFlowListResponse {
  items: CashFlow[]
  total: number
  page: number
  size: number
}

export interface CreateCashFlowSchema {
  vc_id: number
  type: CashFlowType
  amount: number
  payer_id?: number
  payee_id?: number
  transaction_date: string
  description?: string
}

export interface SuggestedParties {
  payer_type: string
  payer_id: number
  payee_type: string
  payee_id: number
}

export interface InternalTransferSchema {
  from_acc_id: number
  to_acc_id: number
  amount: number
  transaction_date: string
  description?: string
}

export interface ExternalFundSchema {
  account_id: number
  fund_type: string
  amount: number
  transaction_date: string
  external_entity: string
  description?: string
  is_inbound: boolean
}

// 服务端实际返回的银行账户结构
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

// Dashboard 返回的实际数据结构
export interface FinanceDashboardStats {
  db_mode: string
  total_customers: number
  total_points: number
  total_inventory_val: number
  total_cash: number
  monthly_revenue: number
  bank_balances: Array<{ 账户: string; 当前余额: number }>
  total_ar: number
  total_ap: number
}

export interface FinanceAccount {
  id: number
  category: string
  level1: string
  level2?: string
  direction: string
  direction_label: string
  balance: number
  display_balance: number
  balance_formatted: string
  full_name: string
}

export interface AccountingAccount {
  id: number
  category: string
  level1_name: string
  level2_name: string
  counterpart_type?: string
  direction: string
  balance?: number
}

export interface JournalEntry {
  voucher_no: string
  account_id: number
  account_name: string
  debit: number
  credit: number
  summary: string
  ref_type: string
  ref_id: number
  ref_vc_id?: number
  transaction_date: string
}

export interface FundHistoryItem {
  date: string
  voucher_no: string
  summary: string
  amount: number
  amount_formatted: string
}

export const financeApi = {
  listCashflows: (params?: {
    ids?: number[] | string
    vc_id?: number
    type?: string
    date_from?: string
    date_to?: string
    page?: number
    size?: number
  }) => apiClient.get<CashFlowListResponse>('/finance/cashflows/list', { params }) as unknown as Promise<CashFlowListResponse>,

  getCashflowsGlobal: (params?: {
    ids?: number[] | string
    cf_id?: number
    vc_id?: number
    vc_ids?: string
    type?: string
    payer_id?: number
    payee_id?: number
    date_from?: string
    date_to?: string
    amount_min?: number
    amount_max?: number
    business_ids?: string
    sc_ids?: string
    customer_kw?: string
    supplier_kw?: string
    payer_name_kw?: string
    payee_name_kw?: string
    page?: number
    size?: number
  }) => apiClient.get<CashFlowListResponse>('/finance/cashflows/global', { params }) as unknown as Promise<CashFlowListResponse>,

  createCashflow: (data: CreateCashFlowSchema) =>
    apiClient.post<{ success: boolean }>('/finance/create-cashflow', data) as unknown as Promise<{ success: boolean }>,

  getSuggestedParties: (vcId: number, cfType: string) =>
    apiClient.get<SuggestedParties>('/query/suggested-cashflow-parties', {
      params: { vc_id: vcId, cf_type: cfType },
    }) as unknown as Promise<SuggestedParties>,

  internalTransfer: (data: InternalTransferSchema) =>
    apiClient.post<{ success: boolean }>('/finance/internal-transfer', data) as unknown as Promise<{ success: boolean }>,

  externalFund: (data: ExternalFundSchema) =>
    apiClient.post<{ success: boolean }>('/finance/external-fund', data) as unknown as Promise<{ success: boolean }>,

  getBankAccounts: () =>
    apiClient.get<BankAccount[]>('/finance/bank-accounts') as unknown as Promise<BankAccount[]>,

  getBankAccountDetail: (accountId: number) =>
    apiClient.get<BankAccount>(`/finance/bank-accounts/${accountId}`) as unknown as Promise<BankAccount>,

  getJournals: (params?: {
    account_id?: number
    start_date?: string
    end_date?: string
    voucher_type?: string
    limit?: number
  }) => apiClient.get<JournalEntry[]>('/finance/journals', { params }) as unknown as Promise<JournalEntry[]>,

  getFundHistory: (limit = 50) =>
    apiClient.get<FundHistoryItem[]>('/finance/fund-history', { params: { limit } }) as unknown as Promise<FundHistoryItem[]>,

  getAccounts: (hasBalanceOnly = true) =>
    apiClient.get<FinanceAccount[]>('/finance/accounts', { params: { has_balance_only: hasBalanceOnly } }) as unknown as Promise<FinanceAccount[]>,

  getDashboard: () =>
    apiClient.get<FinanceDashboardStats>('/finance/dashboard') as unknown as Promise<FinanceDashboardStats>,

  uploadAttachment: (cfId: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post(`/finance/cashflows/${cfId}/attachment`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }) as unknown as Promise<{ success: boolean; data?: { path: string } }>
  },
}
