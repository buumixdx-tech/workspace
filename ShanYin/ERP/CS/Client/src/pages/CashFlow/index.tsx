import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, RefreshCw, Info } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DatePicker } from '@/components/ui/date-picker'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { financeApi, CashFlow, CashFlowType, CreateCashFlowSchema, CashFlowListResponse } from '@/api/endpoints/finance'
import { vcApi, VCStatus } from '@/api/endpoints/vc'
import { masterApi } from '@/api/endpoints/master'
import { formatCurrency, formatDate } from '@/lib/utils'

const CASHFLOW_TYPE_LABELS: Record<string, string> = {
  PREPAYMENT: '预付款',
  FULFILLMENT: '履约款',
  DEPOSIT: '押金',
  RETURN_DEPOSIT: '退还押金',
  PENALTY: '罚款',
  REFUND: '退款',
  OFFSET_INFLOW: '核销流入',
  OFFSET_OUTFLOW: '核销流出',
  DEPOSIT_OFFSET_IN: '押金核销',
  预付: '预付',
  履约: '履约',
  押金: '押金',
  退还押金: '退还押金',
  罚金: '罚金',
}

const CASHFLOW_TYPE_COLORS: Record<string, string> = {
  PREPAYMENT: 'bg-blue-100 text-blue-800',
  FULFILLMENT: 'bg-cyan-100 text-cyan-800',
  DEPOSIT: 'bg-purple-100 text-purple-800',
  RETURN_DEPOSIT: 'bg-orange-100 text-orange-800',
  PENALTY: 'bg-red-100 text-red-800',
  REFUND: 'bg-pink-100 text-pink-800',
  OFFSET_INFLOW: 'bg-green-100 text-green-800',
  OFFSET_OUTFLOW: 'bg-yellow-100 text-yellow-800',
  DEPOSIT_OFFSET_IN: 'bg-indigo-100 text-indigo-800',
  预付: 'bg-blue-100 text-blue-800',
  履约: 'bg-cyan-100 text-cyan-800',
  押金: 'bg-purple-100 text-purple-800',
  退还押金: 'bg-orange-100 text-orange-800',
  罚金: 'bg-red-100 text-red-800',
}

function CreateCashFlowDialog({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [attachmentFile, setAttachmentFile] = useState<File | null>(null)
  const [formData, setFormData] = useState({
    vc_id: '',
    type: '预付' as CashFlowType,
    amount: '',
    payer_id: '',
    payee_id: '',
    transaction_date: new Date().toISOString().split('T')[0],
    description: '',
  })
  const [cfTypes, setCfTypes] = useState<CashFlowType[]>(['预付', '履约', '押金', '退还押金', '罚金'])

  const { data: vcs } = useQuery({
    queryKey: ['vcs-for-cf'],
    queryFn: () => vcApi.list({ status: '执行', size: 100 }),
  })

  const { data: skus } = useQuery({
    queryKey: ['skus-for-cf'],
    queryFn: () => masterApi.skus.list({ size: 100 }),
  })

  const { data: bankAccounts } = useQuery({
    queryKey: ['bank-accounts'],
    queryFn: () => financeApi.getBankAccounts(),
  })

  const { data: suggestedParties } = useQuery({
    queryKey: ['suggested-parties', formData.vc_id, formData.type],
    queryFn: () => financeApi.getSuggestedParties(parseInt(formData.vc_id), formData.type),
    enabled: !!formData.vc_id && !!formData.type,
  })

  // 选VC后自动填充收付款方（根据 owner_type + owner_id 匹配银行账户）
  // 当 suggestedParties 变化时（款项类型改变），重新自动填充
  useEffect(() => {
    if (!suggestedParties || !bankAccounts) return
    const payerAcc = bankAccounts.find(a =>
      a.owner_type === suggestedParties.payer_type &&
      (suggestedParties.payer_type === 'ourselves' ? a.owner_id === null : a.owner_id === suggestedParties.payer_id)
    )
    const payeeAcc = bankAccounts.find(a =>
      a.owner_type === suggestedParties.payee_type &&
      (suggestedParties.payee_type === 'ourselves' ? a.owner_id === null : a.owner_id === suggestedParties.payee_id)
    )
    setFormData(prev => ({
      ...prev,
      payer_id: payerAcc ? String(payerAcc.id) : '',
      payee_id: payeeAcc ? String(payeeAcc.id) : '',
    }))
  }, [suggestedParties, bankAccounts])

  const { data: progress } = useQuery({
    queryKey: ['cf-progress', formData.vc_id],
    queryFn: () => vcApi.getCashflowProgress(parseInt(formData.vc_id)),
    enabled: !!formData.vc_id,
  })

  const createMutation = useMutation({
    mutationFn: async () => {
      const result = await financeApi.createCashflow({
        vc_id: parseInt(formData.vc_id),
        type: formData.type,
        amount: parseFloat(formData.amount) || 0,
        payer_id: formData.payer_id ? parseInt(formData.payer_id) : undefined,
        payee_id: formData.payee_id ? parseInt(formData.payee_id) : undefined,
        transaction_date: formData.transaction_date + 'T00:00:00',
        description: formData.description,
      })
      return result
    },
    onSuccess: async (data) => {
      // Upload attachment if file was selected
      // Server returns {cf_id: number} in data field
      const cfId = (data as { cf_id?: number })?.cf_id
      if (attachmentFile && cfId) {
        try {
          await financeApi.uploadAttachment(cfId, attachmentFile)
        } catch (e) {
          console.error('Failed to upload attachment:', e)
        }
      }
      queryClient.invalidateQueries({ queryKey: ['cashflow-list'] })
      setIsOpen(false)
      setShowConfirm(false)
      setAttachmentFile(null)
      onSuccess()
    },
    onError: (err: Error) => {
      alert('创建资金流失败: ' + err.message)
    },
  })

  const handleVCSelect = (vcId: string) => {
    const vc = vcs?.items?.find(v => v.id === parseInt(vcId))
    let defaultType: CashFlowType = '预付'
    if (vc) {
      if (vc.type === 'RETURN') {
        defaultType = '退款'
        setCfTypes(['退款', '退还押金'])
      } else {
        setCfTypes(['预付', '履约', '押金', '退还押金', '罚金'])
      }
    }
    setFormData({ ...formData, vc_id: vcId, type: defaultType, payer_id: '', payee_id: '' })
  }

  const selectedVC = vcs?.items?.find(v => v.id === parseInt(formData.vc_id))
  const payerAccount = bankAccounts?.find(a => a.id === parseInt(formData.payer_id))
  const payeeAccount = bankAccounts?.find(a => a.id === parseInt(formData.payee_id))

  const handleClose = (open: boolean) => {
    setIsOpen(open)
    if (!open) setShowConfirm(false)
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogTrigger asChild>
        <Button><Plus className="mr-2 h-4 w-4" />录入资金流</Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{showConfirm ? '确认资金流水' : '录入资金流'}</DialogTitle>
        </DialogHeader>

        {!showConfirm ? (
          <form onSubmit={(e) => { e.preventDefault(); setShowConfirm(true) }} className="space-y-6">
            <div className="space-y-2">
              <Label>关联虚拟合同</Label>
              <Select value={formData.vc_id} onValueChange={handleVCSelect}>
                <SelectTrigger>
                  <SelectValue placeholder="选择合同" />
                </SelectTrigger>
                <SelectContent>
                  {vcs?.items?.map(vc => {
                    const els = (vc.elements?.items || vc.elements?.elements || [])
                    const skuSummary = els.length > 0
                      ? els.map((e: any) => {
                          const sku = skus?.items?.find((s: any) => s.id === e.sku_id)
                          const name = sku?.name || e.sku_name || `SKU-${e.sku_id}`
                          return `${name}×${e.qty}`
                        }).join(', ')
                      : '无明细'
                    return (
                      <SelectItem key={vc.id} value={String(vc.id)} className="flex flex-col items-start gap-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">VC-{vc.id}</span>
                          <span className="text-xs bg-muted px-1 rounded">{vc.type}</span>
                        </div>
                        <div className="text-xs text-muted-foreground truncate max-w-[300px]">
                          {vc.counterparty || '无对手方'} · {skuSummary}
                        </div>
                      </SelectItem>
                    )
                  })}
                </SelectContent>
              </Select>
            </div>

            {progress && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">付款进度</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">应付总额: </span>
                      <span className="font-medium">{formatCurrency(progress.goods?.total ?? 0)}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">已付金额: </span>
                      <span className="font-medium text-green-600">{formatCurrency(progress.goods?.paid ?? 0)}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">未付余额: </span>
                      <span className="font-medium text-orange-600">{formatCurrency(progress.goods?.balance ?? 0)}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">应收押金: </span>
                      <span className="font-medium">{formatCurrency(progress.deposit?.should ?? 0)}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">实收押金: </span>
                      <span className="font-medium text-blue-600">{formatCurrency(progress.deposit?.received ?? 0)}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">核销池: </span>
                      <span className="font-medium">{formatCurrency(progress.goods?.pool ?? 0)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            <div className="space-y-2">
              <Label>款项类型</Label>
              <Select value={formData.type} onValueChange={(v) => setFormData({ ...formData, type: v as CashFlowType })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {cfTypes.map(type => (
                    <SelectItem key={type} value={type}>{CASHFLOW_TYPE_LABELS[type]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>金额</Label>
              <Input type="number" step="0.01" min="0" value={formData.amount} onChange={(e) => setFormData({ ...formData, amount: e.target.value })} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>付款方账户</Label>
                <Select value={formData.payer_id} onValueChange={(v) => setFormData({ ...formData, payer_id: v })}>
                  <SelectTrigger className="h-10">
                    <SelectValue placeholder="选择付款方" />
                  </SelectTrigger>
                  <SelectContent>
                    {bankAccounts?.map(acc => (
                      <SelectItem key={acc.id} value={String(acc.id)}>{acc.bank_name} ({acc.owner_name})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>收款方账户</Label>
                <Select value={formData.payee_id} onValueChange={(v) => setFormData({ ...formData, payee_id: v })}>
                  <SelectTrigger className="h-10">
                    <SelectValue placeholder="选择收款方" />
                  </SelectTrigger>
                  <SelectContent>
                    {bankAccounts?.map(acc => (
                      <SelectItem key={acc.id} value={String(acc.id)}>{acc.bank_name} ({acc.owner_name})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>交易日期</Label>
              <DatePicker value={formData.transaction_date} onChange={(v) => setFormData({ ...formData, transaction_date: v })} />
            </div>

            <div className="space-y-2">
              <Label>备注</Label>
              <Textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
            </div>

            <div className="space-y-2">
              <Label>附件（银行转账单据）</Label>
              <Input
                type="file"
                accept="image/*,.pdf"
                onChange={(e) => setAttachmentFile(e.target.files?.[0] || null)}
              />
              <p className="text-xs text-muted-foreground">支持 JPG、PNG、PDF 格式</p>
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setIsOpen(false)}>取消</Button>
              <Button type="submit" disabled={!formData.vc_id || !formData.amount || createMutation.isPending}>
                下一步
              </Button>
            </div>
          </form>
        ) : (
          <div className="space-y-6">
            <div className="bg-muted rounded-lg p-4 space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <Info className="h-4 w-4 text-muted-foreground" />
                <span className="text-muted-foreground">请从财务审核角度核对以下流水信息</span>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">关联VC: </span>
                  <span className="font-medium">{selectedVC?.description?.slice(0, 30) || `VC-${formData.vc_id}`}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">VC类型: </span>
                  <span className="font-medium">{selectedVC?.type || '-'}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">资金类型: </span>
                  <Badge className={CASHFLOW_TYPE_COLORS[formData.type]}>{CASHFLOW_TYPE_LABELS[formData.type]}</Badge>
                </div>
                <div>
                  <span className="text-muted-foreground">操作金额: </span>
                  <span className="font-medium text-lg">{formatCurrency(parseFloat(formData.amount) || 0)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">交易日期: </span>
                  <span className="font-medium">{formData.transaction_date}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">付款账户: </span>
                  <span className="font-medium">{payerAccount ? `${payerAccount.bank_name} (${payerAccount.owner_name})` : '未指定'}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">收款账户: </span>
                  <span className="font-medium">{payeeAccount ? `${payeeAccount.bank_name} (${payeeAccount.owner_name})` : '未指定'}</span>
                </div>
              </div>
              {formData.description && (
                <div className="text-sm">
                  <span className="text-muted-foreground">备注: </span>
                  <span>{formData.description}</span>
                </div>
              )}
              {attachmentFile && (
                <div className="text-sm">
                  <span className="text-muted-foreground">附件: </span>
                  <span>{attachmentFile.name}</span>
                </div>
              )}
            </div>

            <div className="flex justify-between">
              <Button type="button" variant="outline" onClick={() => setShowConfirm(false)}>
                返回修改
              </Button>
              <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
                {createMutation.isPending ? '提交中...' : '确认执行并记账'}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

export function CashFlowPage() {
  const [typeFilter, setTypeFilter] = useState<CashFlowType[]>([])
  const [selectedCF, setSelectedCF] = useState<CashFlow | null>(null)
  const [displayLimit, setDisplayLimit] = useState(10)
  const loadMoreRef = useRef<HTMLTableRowElement>(null)

  // 全局概览搜索状态
  const [searchParams, setSearchParams] = useState({
    cf_id: '', vc_id: '', business_ids: '', sc_ids: '',
    customer_kw: '', supplier_kw: '', payer_name_kw: '', payee_name_kw: '',
    amount_min: '', amount_max: '',
    type: '' as string,
    page: 1, size: 20,
  })
  const [searchCount, setSearchCount] = useState(0)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['cashflow-list', typeFilter],
    queryFn: () => financeApi.listCashflows({ size: 20 }),
  })

  // 获取银行账户，判断哪些是我们自己的
  const { data: bankAccounts } = useQuery({
    queryKey: ['bank-accounts-for-direction'],
    queryFn: () => financeApi.getBankAccounts(),
  })

  // 构建我们自己的账户 ID 集合
  const ourAccountIds = new Set(
    bankAccounts?.filter(a => a.owner_type === 'ourselves').map(a => a.id) || []
  )

  // 判断资金流方向
  const getDirection = (cf: CashFlow): 'INFLOW' | 'OUTFLOW' => {
    return ourAccountIds.has(cf.payee_account_id) ? 'INFLOW' : 'OUTFLOW'
  }

  const filteredItems = data?.items?.filter(cf => {
    if (typeFilter.length > 0 && !typeFilter.includes(cf.type as CashFlowType)) return false
    return true
  }) || []

  // 筛选条件变化时重置显示数量
  useEffect(() => {
    setDisplayLimit(10)
  }, [typeFilter])

  // 滚动加载更多
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && displayLimit < filteredItems.length) {
          setDisplayLimit(prev => Math.min(prev + 10, filteredItems.length))
        }
      },
      { threshold: 0.1 }
    )
    if (loadMoreRef.current) {
      observer.observe(loadMoreRef.current)
    }
    return () => observer.disconnect()
  }, [displayLimit, filteredItems.length])

  const displayedItems = filteredItems.slice(0, displayLimit)

  // 全局概览搜索
  const { data: globalSearchData, isLoading: isGlobalSearching } = useQuery({
    queryKey: ['cashflow-global', searchParams, searchCount],
    enabled: searchCount > 0,
    queryFn: () => {
      const p: Record<string, unknown> = { ...searchParams }
      const numFields = ['vc_id', 'payer_id', 'payee_id']
      Object.keys(p).forEach(k => {
        if (numFields.includes(k) && typeof p[k] === 'string' && (p[k] as string) !== '') {
          p[k] = Number(p[k])
        } else if (p[k] === '' || p[k] === undefined) {
          delete p[k]
        }
      })
      return financeApi.getCashflowsGlobal(p as Parameters<typeof financeApi.getCashflowsGlobal>[0]) as unknown as Promise<CashFlowListResponse>
    },
  })

  const doGlobalSearch = () => {
    setSelectedCF(null)
    setSearchCount(c => c + 1)
  }

  const clearSearch = () => {
    setSearchParams({
      cf_id: '', vc_id: '', business_ids: '', sc_ids: '',
      customer_kw: '', supplier_kw: '', payer_name_kw: '',
      payee_name_kw: '', amount_min: '', amount_max: '',
      type: '', page: 1, size: 20,
    })
    setSearchCount(0)
    setSelectedCF(null)
  }

  const globalFilteredItems = globalSearchData?.items || []
  const totalPages = globalSearchData ? Math.ceil(globalSearchData.total / (globalSearchData.size || 20)) : 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">资金流管理</h2>
        <CreateCashFlowDialog onSuccess={() => refetch()} />
      </div>

      <Tabs defaultValue="list" className="w-full">
        <TabsList>
          <TabsTrigger value="list">列表</TabsTrigger>
          <TabsTrigger value="global">全局概览</TabsTrigger>
        </TabsList>

        <TabsContent value="list" className="space-y-4">
          <div className="flex gap-4 flex-wrap">
            <Select value={typeFilter[0] || 'ALL'} onValueChange={(v) => setTypeFilter(v === 'ALL' ? [] : [v as CashFlowType])}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="资金类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部类型</SelectItem>
                {Object.entries(CASHFLOW_TYPE_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>

          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>流水ID</TableHead>
                    <TableHead>日期</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>金额</TableHead>
                    <TableHead>方向</TableHead>
                    <TableHead>付款方</TableHead>
                    <TableHead>收款方</TableHead>
                    <TableHead>关联VC</TableHead>
                    <TableHead>备注</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {displayedItems.map(cf => (
                    <TableRow
                      key={cf.id}
                      className={selectedCF?.id === cf.id ? 'bg-muted' : ''}
                      onClick={() => setSelectedCF(cf)}
                    >
                      <TableCell className="font-medium">CF-{cf.id}</TableCell>
                      <TableCell>{formatDate(cf.transaction_date)}</TableCell>
                      <TableCell><Badge className={CASHFLOW_TYPE_COLORS[cf.type]}>{CASHFLOW_TYPE_LABELS[cf.type]}</Badge></TableCell>
                      <TableCell className={`font-medium ${getDirection(cf) === 'INFLOW' ? 'text-green-600' : 'text-red-600'}`}>
                        {getDirection(cf) === 'INFLOW' ? '+' : '-'}{formatCurrency(cf.amount)}
                      </TableCell>
                      <TableCell><Badge variant="outline">{getDirection(cf) === 'INFLOW' ? '流入' : '流出'}</Badge></TableCell>
                      <TableCell className="text-sm">{cf.payer_account_name || '-'}</TableCell>
                      <TableCell className="text-sm">{cf.payee_account_name || '-'}</TableCell>
                      <TableCell className="text-sm">VC-{cf.virtual_contract_id}</TableCell>
                      <TableCell className="text-sm max-w-[150px] truncate">{cf.description || '-'}</TableCell>
                    </TableRow>
                  ))}
                  {!filteredItems.length ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center text-muted-foreground">
                        {isLoading ? '加载中...' : '暂无数据'}
                      </TableCell>
                    </TableRow>
                  ) : (
                    <TableRow ref={loadMoreRef}>
                      <TableCell colSpan={9} className="text-center py-2 text-sm text-muted-foreground">
                        {displayLimit >= filteredItems.length ? '已加载全部' : '滚动加载更多...'}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {selectedCF && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">资金流水详情 (ID: {selectedCF.id})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4 text-sm mb-4">
                  <div>
                    <span className="text-muted-foreground">交易金额: </span>
                    <span className="font-medium">{formatCurrency(selectedCF.amount)}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">资金类型: </span>
                    <Badge className={CASHFLOW_TYPE_COLORS[selectedCF.type]}>{CASHFLOW_TYPE_LABELS[selectedCF.type]}</Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">交易时间: </span>
                    <span className="font-medium">{formatDate(selectedCF.transaction_date)}</span>
                  </div>
                </div>
                <div className="bg-muted rounded-lg p-3 text-sm">
                  <div className="text-muted-foreground mb-1">资金收付链路</div>
                  <div className="flex items-center gap-2">
                    <span>{selectedCF.payer_account_name || '未指定'}</span>
                    <span className="text-muted-foreground">→</span>
                    <span>{selectedCF.payee_account_name || '未指定'}</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">关联VC: </span>
                    <span>VC-{selectedCF.virtual_contract_id}</span>
                    {selectedCF.vc_type && <span className="ml-2 text-muted-foreground">({selectedCF.vc_type})</span>}
                  </div>
                  <div>
                    <span className="text-muted-foreground">备注: </span>
                    <span>{selectedCF.description || '无'}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="global" className="space-y-4">
          {/* 搜索表单 */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">多条件搜索</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs">CF ID</Label>
                  <Input value={searchParams.cf_id} onChange={e => setSearchParams(p => ({ ...p, cf_id: e.target.value }))} placeholder="如 1,2,3" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">VC ID</Label>
                  <Input value={searchParams.vc_id} onChange={e => setSearchParams(p => ({ ...p, vc_id: e.target.value }))} placeholder="如 1,2,3" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Business ID</Label>
                  <Input value={searchParams.business_ids} onChange={e => setSearchParams(p => ({ ...p, business_ids: e.target.value }))} placeholder="如 1,2,3" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">供应链 ID</Label>
                  <Input value={searchParams.sc_ids} onChange={e => setSearchParams(p => ({ ...p, sc_ids: e.target.value }))} placeholder="如 1,2,3" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">客户名称</Label>
                  <Input value={searchParams.customer_kw} onChange={e => setSearchParams(p => ({ ...p, customer_kw: e.target.value }))} placeholder="精确包含" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">供应商名称</Label>
                  <Input value={searchParams.supplier_kw} onChange={e => setSearchParams(p => ({ ...p, supplier_kw: e.target.value }))} placeholder="精确包含" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">付款账户名称</Label>
                  <Input value={searchParams.payer_name_kw} onChange={e => setSearchParams(p => ({ ...p, payer_name_kw: e.target.value }))} placeholder="精确包含" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">收款账户名称</Label>
                  <Input value={searchParams.payee_name_kw} onChange={e => setSearchParams(p => ({ ...p, payee_name_kw: e.target.value }))} placeholder="精确包含" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">金额范围</Label>
                  <div className="flex gap-1 items-center">
                    <Input type="number" value={searchParams.amount_min} onChange={e => setSearchParams(p => ({ ...p, amount_min: e.target.value }))} placeholder="最小" className="w-full" />
                    <span className="text-muted-foreground">~</span>
                    <Input type="number" value={searchParams.amount_max} onChange={e => setSearchParams(p => ({ ...p, amount_max: e.target.value }))} placeholder="最大" className="w-full" />
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <Select value={searchParams.type || 'ALL'} onValueChange={(v) => setSearchParams(p => ({ ...p, type: v === 'ALL' ? '' : v }))}>
                  <SelectTrigger className="w-36">
                    <SelectValue placeholder="资金类型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ALL">全部类型</SelectItem>
                    {Object.entries(CASHFLOW_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="flex gap-2 ml-auto">
                  <Button variant="outline" onClick={clearSearch}>清空</Button>
                  <Button onClick={doGlobalSearch} disabled={isGlobalSearching}>
                    {isGlobalSearching ? '搜索中...' : '搜索'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 搜索结果 */}
          {globalSearchData && (
            <>
              <div className="text-sm text-muted-foreground">
                共 {globalSearchData.total} 条记录
              </div>
              <Card>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>流水ID</TableHead>
                        <TableHead>日期</TableHead>
                        <TableHead>类型</TableHead>
                        <TableHead>金额</TableHead>
                        <TableHead>方向</TableHead>
                        <TableHead>付款方</TableHead>
                        <TableHead>收款方</TableHead>
                        <TableHead>关联VC</TableHead>
                        <TableHead>备注</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {globalFilteredItems.map(cf => (
                        <TableRow
                          key={cf.id}
                          className={selectedCF?.id === cf.id ? 'bg-muted' : ''}
                          onClick={() => setSelectedCF(cf)}
                        >
                          <TableCell className="font-medium">CF-{cf.id}</TableCell>
                          <TableCell>{formatDate(cf.transaction_date)}</TableCell>
                          <TableCell><Badge className={CASHFLOW_TYPE_COLORS[cf.type]}>{CASHFLOW_TYPE_LABELS[cf.type]}</Badge></TableCell>
                          <TableCell className={`font-medium ${getDirection(cf) === 'INFLOW' ? 'text-green-600' : 'text-red-600'}`}>
                            {getDirection(cf) === 'INFLOW' ? '+' : '-'}{formatCurrency(cf.amount)}
                          </TableCell>
                          <TableCell><Badge variant="outline">{getDirection(cf) === 'INFLOW' ? '流入' : '流出'}</Badge></TableCell>
                          <TableCell className="text-sm">{cf.payer_account_name || '-'}</TableCell>
                          <TableCell className="text-sm">{cf.payee_account_name || '-'}</TableCell>
                          <TableCell className="text-sm">VC-{cf.virtual_contract_id}</TableCell>
                          <TableCell className="text-sm max-w-[150px] truncate">{cf.description || '-'}</TableCell>
                        </TableRow>
                      ))}
                      {!globalFilteredItems.length && (
                        <TableRow>
                          <TableCell colSpan={9} className="text-center text-muted-foreground">
                            未找到匹配记录
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {/* 分页 */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => setSearchParams(p => ({ ...p, page: p.page - 1 }))} disabled={searchParams.page <= 1}>
                    上一页
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    第 {searchParams.page} / {totalPages} 页
                  </span>
                  <Button variant="outline" size="sm" onClick={() => setSearchParams(p => ({ ...p, page: p.page + 1 }))} disabled={searchParams.page >= totalPages}>
                    下一页
                  </Button>
                </div>
              )}

              {/* 详情 */}
              {selectedCF && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">资金流水详情 (ID: {selectedCF.id})</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-3 gap-4 text-sm mb-4">
                      <div>
                        <span className="text-muted-foreground">交易金额: </span>
                        <span className="font-medium">{formatCurrency(selectedCF.amount)}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">资金类型: </span>
                        <Badge className={CASHFLOW_TYPE_COLORS[selectedCF.type]}>{CASHFLOW_TYPE_LABELS[selectedCF.type]}</Badge>
                      </div>
                      <div>
                        <span className="text-muted-foreground">交易时间: </span>
                        <span className="font-medium">{formatDate(selectedCF.transaction_date)}</span>
                      </div>
                    </div>
                    <div className="bg-muted rounded-lg p-3 text-sm">
                      <div className="text-muted-foreground mb-1">资金收付链路</div>
                      <div className="flex items-center gap-2">
                        <span>{selectedCF.payer_account_name || '未指定'}</span>
                        <span className="text-muted-foreground">→</span>
                        <span>{selectedCF.payee_account_name || '未指定'}</span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
                      <div>
                        <span className="text-muted-foreground">关联VC: </span>
                        <span>VC-{selectedCF.virtual_contract_id}</span>
                        {selectedCF.vc_type && <span className="ml-2 text-muted-foreground">({selectedCF.vc_type})</span>}
                      </div>
                      <div>
                        <span className="text-muted-foreground">备注: </span>
                        <span>{selectedCF.description || '无'}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
