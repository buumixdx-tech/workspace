import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { DatePicker } from '@/components/ui/date-picker'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { financeApi, FinanceAccount, FundHistoryItem } from '@/api/endpoints/finance'
import { formatCurrency, formatDate } from '@/lib/utils'
import { AlertCircle, CheckCircle2 } from 'lucide-react'

const FUND_IN_TYPES = ['实收资本', '其他应付款', '短期借款', '长期借款', '其他']
const FUND_OUT_TYPES = ['日常办公开支', '税费支出', '银行手续费', '借款还款', '其他']

function AccountLedgerTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['finance-accounts-ledger'],
    queryFn: () => financeApi.getAccounts(true),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>银行/往来账户核算表</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>科目</TableHead>
              <TableHead>详细名称</TableHead>
              <TableHead>余额方向</TableHead>
              <TableHead className="text-right">当前余额</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.map((acc) => (
              <TableRow key={acc.id}>
                <TableCell className="font-medium">{acc.level1}</TableCell>
                <TableCell>{acc.full_name}</TableCell>
                <TableCell>
                  <span className={`text-sm ${acc.direction === 'Debit' ? 'text-blue-600' : 'text-orange-600'}`}>
                    {acc.direction_label}
                  </span>
                </TableCell>
                <TableCell className="text-right">
                  <span className={acc.display_balance >= 0 ? 'text-green-600' : 'text-red-600'}>
                    {formatCurrency(Math.abs(acc.display_balance))}
                  </span>
                </TableCell>
              </TableRow>
            ))}
            {!data?.length && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  {isLoading ? '加载中...' : '当前无活动余额数据'}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function TransferTab() {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<'internal' | 'external-in' | 'external-out'>('internal')
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [formData, setFormData] = useState({
    from_acc_id: '',
    to_acc_id: '',
    amount: '',
    transaction_date: new Date().toISOString().split('T')[0],
    description: '',
    account_id: '',
    fund_type: '',
    external_entity: '',
  })

  const { data: bankAccounts } = useQuery({
    queryKey: ['bank-accounts'],
    queryFn: () => financeApi.getBankAccounts(),
  })

  const { data: fundHistory } = useQuery({
    queryKey: ['fund-history'],
    queryFn: () => financeApi.getFundHistory(50),
  })

  const internalTransferMutation = useMutation({
    mutationFn: () =>
      financeApi.internalTransfer({
        from_acc_id: parseInt(formData.from_acc_id),
        to_acc_id: parseInt(formData.to_acc_id),
        amount: parseFloat(formData.amount) || 0,
        transaction_date: formData.transaction_date + 'T00:00:00',
        description: formData.description,
      }),
    onSuccess: (res) => {
      if (res.success) {
        setSuccessMsg('内部划拨成功')
        setError('')
        setFormData({ ...formData, from_acc_id: '', to_acc_id: '', amount: '', description: '' })
        queryClient.invalidateQueries({ queryKey: ['fund-history'] })
      } else {
        setError(res.success ? '' : (res as unknown as { error?: string }).error || '操作失败')
        setSuccessMsg('')
      }
    },
  })

  const externalFundMutation = useMutation({
    mutationFn: () =>
      financeApi.externalFund({
        account_id: parseInt(formData.account_id),
        fund_type: formData.fund_type,
        amount: parseFloat(formData.amount) || 0,
        transaction_date: formData.transaction_date + 'T00:00:00',
        external_entity: formData.external_entity,
        description: formData.description,
        is_inbound: mode === 'external-in',
      }),
    onSuccess: (res) => {
      if (res.success) {
        setSuccessMsg(mode === 'external-in' ? '外部入金成功' : '外部出金成功')
        setError('')
        setFormData({ ...formData, account_id: '', fund_type: '', external_entity: '', amount: '', description: '' })
        queryClient.invalidateQueries({ queryKey: ['fund-history'] })
      } else {
        setError(res.success ? '' : (res as unknown as { error?: string }).error || '操作失败')
        setSuccessMsg('')
      }
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccessMsg('')

    if (mode === 'internal') {
      if (!formData.from_acc_id || !formData.to_acc_id) {
        setError('请选择转出和转入账户')
        return
      }
      if (formData.from_acc_id === formData.to_acc_id) {
        setError('转出与转入账户不能相同')
        return
      }
      if (!formData.amount || parseFloat(formData.amount) <= 0) {
        setError('金额必须大于0')
        return
      }
      internalTransferMutation.mutate()
    } else {
      if (!formData.account_id) {
        setError('请选择账户')
        return
      }
      if (!formData.fund_type) {
        setError('请选择资金类型')
        return
      }
      if (!formData.external_entity.trim()) {
        setError(mode === 'external-in' ? '请填写外部来源名称' : '请填写外部去向名称')
        return
      }
      if (!formData.amount || parseFloat(formData.amount) <= 0) {
        setError('金额必须大于0')
        return
      }
      externalFundMutation.mutate()
    }
  }

  const isPending = internalTransferMutation.isPending || externalFundMutation.isPending

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>资金流入流出管理</CardTitle>
          <p className="text-sm text-muted-foreground">
            本操作用于记录账户对调、外部增资注入、借款往来或日常行政开支。
          </p>
        </CardHeader>
        <CardContent>
          <RadioGroup
            value={mode}
            onValueChange={(v) => {
              setMode(v as typeof mode)
              setError('')
              setSuccessMsg('')
            }}
            className="mb-6"
          >
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="internal" id="internal" />
              <Label htmlFor="internal">内部划拨</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="external-in" id="external-in" />
              <Label htmlFor="external-in">外部入金</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="external-out" id="external-out" />
              <Label htmlFor="external-out">外部出金</Label>
            </div>
          </RadioGroup>

          {error && (
            <div className="mb-4 p-3 bg-red-50 text-red-800 rounded flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}

          {successMsg && (
            <div className="mb-4 p-3 bg-green-50 text-green-800 rounded flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              {successMsg}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'internal' ? (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>转出账户 (付款方)</Label>
                    <Select
                      value={formData.from_acc_id}
                      onValueChange={(v) => setFormData({ ...formData, from_acc_id: v })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="选择转出账户" />
                      </SelectTrigger>
                      <SelectContent>
                        {bankAccounts?.map((acc) => (
                          <SelectItem key={acc.id} value={String(acc.id)}>
                            {acc.owner_name} ({acc.bank_name})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>转入账户 (收款方)</Label>
                    <Select
                      value={formData.to_acc_id}
                      onValueChange={(v) => setFormData({ ...formData, to_acc_id: v })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="选择转入账户" />
                      </SelectTrigger>
                      <SelectContent>
                        {bankAccounts?.map((acc) => (
                          <SelectItem key={acc.id} value={String(acc.id)}>
                            {acc.owner_name} ({acc.bank_name})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>{mode === 'external-in' ? '公司收款账户' : '公司付款账户'}</Label>
                    <Select
                      value={formData.account_id}
                      onValueChange={(v) => setFormData({ ...formData, account_id: v })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="选择账户" />
                      </SelectTrigger>
                      <SelectContent>
                        {bankAccounts?.map((acc) => (
                          <SelectItem key={acc.id} value={String(acc.id)}>
                            {acc.owner_name} ({acc.bank_name})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>{mode === 'external-in' ? '资金性质' : '款项用途'}</Label>
                    <Select
                      value={formData.fund_type}
                      onValueChange={(v) => setFormData({ ...formData, fund_type: v })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="选择类型" />
                      </SelectTrigger>
                      <SelectContent>
                        {(mode === 'external-in' ? FUND_IN_TYPES : FUND_OUT_TYPES).map((type) => (
                          <SelectItem key={type} value={type}>
                            {type}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>{mode === 'external-in' ? '外部来源名称' : '外部去向名称'}</Label>
                  <Input
                    value={formData.external_entity}
                    onChange={(e) => setFormData({ ...formData, external_entity: e.target.value })}
                    placeholder={mode === 'external-in' ? '例如：股东张三、XX信贷机构' : '例如：XX物业公司、员工王五'}
                  />
                </div>
              </>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>划拨金额</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={formData.amount}
                  onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                  placeholder="0.00"
                />
              </div>
              <div className="space-y-2">
                <Label>操作日期</Label>
                <DatePicker
                  value={formData.transaction_date}
                  onChange={(v) => setFormData({ ...formData, transaction_date: v })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>备注</Label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="例如：日常经营资金调拔"
              />
            </div>

            <Button type="submit" disabled={isPending}>
              {isPending ? '处理中...' : '确认划拨'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">资金账户历史流水</CardTitle>
        </CardHeader>
        <CardContent>
          {fundHistory && fundHistory.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>日期</TableHead>
                  <TableHead>流水号</TableHead>
                  <TableHead>摘要</TableHead>
                  <TableHead className="text-right">总额</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {fundHistory.map((item: FundHistoryItem) => (
                  <TableRow key={item.voucher_no}>
                    <TableCell className="text-sm">{item.date}</TableCell>
                    <TableCell className="font-mono text-sm">{item.voucher_no}</TableCell>
                    <TableCell className="text-sm">{item.summary || '-'}</TableCell>
                    <TableCell className="text-right font-medium">
                      {formatCurrency(item.amount)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-4 text-muted-foreground">暂无历史流水</div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function VouchersTab() {
  const [limit, setLimit] = useState(100)

  const { data, isLoading } = useQuery({
    queryKey: ['journals', limit],
    queryFn: () => financeApi.getJournals({ limit }),
  })

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>财务凭证</CardTitle>
        <Select value={String(limit)} onValueChange={(v) => setLimit(parseInt(v))}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="50">50条</SelectItem>
            <SelectItem value="100">100条</SelectItem>
            <SelectItem value="200">200条</SelectItem>
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>凭证号</TableHead>
              <TableHead>日期</TableHead>
              <TableHead>会计科目</TableHead>
              <TableHead className="text-right">借方</TableHead>
              <TableHead className="text-right">贷方</TableHead>
              <TableHead>摘要</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.map((entry, idx) => (
              <TableRow key={idx}>
                <TableCell className="font-mono text-sm">{entry.voucher_no}</TableCell>
                <TableCell className="text-sm">{formatDate(entry.transaction_date)}</TableCell>
                <TableCell>{entry.account_name}</TableCell>
                <TableCell className="text-right text-red-600">
                  {entry.debit > 0 ? formatCurrency(entry.debit) : '-'}
                </TableCell>
                <TableCell className="text-right text-green-600">
                  {entry.credit > 0 ? formatCurrency(entry.credit) : '-'}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{entry.summary}</TableCell>
              </TableRow>
            ))}
            {!data?.length && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground">
                  {isLoading ? '加载中...' : '尚无分录记录'}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function AccountsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['finance-accounts-list'],
    queryFn: () => financeApi.getAccounts(false),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>会计科目表</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>分类</TableHead>
              <TableHead>一级科目</TableHead>
              <TableHead>二级科目</TableHead>
              <TableHead>方向</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.map((acc: FinanceAccount) => (
              <TableRow key={acc.id}>
                <TableCell>
                  <span className="text-xs bg-gray-100 px-2 py-1 rounded">{acc.category}</span>
                </TableCell>
                <TableCell className="font-medium">{acc.level1}</TableCell>
                <TableCell>{acc.level2 || '-'}</TableCell>
                <TableCell>
                  <span className={`text-sm ${acc.direction === 'Debit' ? 'text-blue-600' : 'text-orange-600'}`}>
                    {acc.direction === 'Debit' ? '借' : '贷'}
                  </span>
                </TableCell>
              </TableRow>
            ))}
            {!data?.length && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  {isLoading ? '加载中...' : '暂无科目数据'}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

export function FinancePage() {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">财务管理</h2>

      <Tabs defaultValue="ledger">
        <TabsList>
          <TabsTrigger value="ledger">资金往来明细</TabsTrigger>
          <TabsTrigger value="transfer">资金调拨与往来</TabsTrigger>
          <TabsTrigger value="vouchers">财务凭证</TabsTrigger>
          <TabsTrigger value="accounts">会计科目</TabsTrigger>
        </TabsList>

        <TabsContent value="ledger">
          <AccountLedgerTab />
        </TabsContent>
        <TabsContent value="transfer">
          <TransferTab />
        </TabsContent>
        <TabsContent value="vouchers">
          <VouchersTab />
        </TabsContent>
        <TabsContent value="accounts">
          <AccountsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
