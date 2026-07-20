import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Users, MapPin, Package, Banknote, TrendingUp, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { financeApi, FinanceDashboardStats, BankAccount as FinanceBankAccount } from '@/api/endpoints/finance'
import { formatCurrency } from '@/lib/utils'

interface DashboardStats {
  customer_count: number
  point_count: number
  inventory_value: number
  cash_balance: number
  monthly_revenue: number
}

interface ARAPSummary {
  ar_total: number
  ap_total: number
  ar_details: { customer: string; amount: number }[]
  ap_details: { supplier: string; amount: number }[]
}

function StatCard({ title, value, icon: Icon, subtext }: {
  title: string
  value: string | number
  icon: React.ElementType
  subtext?: string
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {subtext && <p className="text-xs text-muted-foreground">{subtext}</p>}
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const [isProd, setIsProd] = useState(true)

  const { data: stats, isLoading: statsLoading, refetch } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => financeApi.getDashboard(),
  })

  const { data: bankAccounts, isLoading: accountsLoading } = useQuery<FinanceBankAccount[]>({
    queryKey: ['bank-accounts'],
    queryFn: () => financeApi.getBankAccounts(),
  })

  const { data: arapData } = useQuery({
    queryKey: ['arap-summary'],
    queryFn: async () => {
      // Would call a dedicated endpoint if available
      // For now, return mock data
      return {
        ar_total: stats?.total_ar || 0,
        ap_total: stats?.total_ap || 0,
        ar_details: [],
        ap_details: [],
      } as ARAPSummary
    },
  })

  const cashBalance = stats?.total_cash || 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">运行看板</h2>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">测试环境</span>
            <Switch checked={isProd} onCheckedChange={setIsProd} />
            <span className="text-sm text-muted-foreground">生产环境</span>
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            刷新
          </Button>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <StatCard
          title="服务客户"
          value={stats?.total_customers ?? '-'}
          icon={Users}
        />
        <StatCard
          title="点位数量"
          value={stats?.total_points ?? '-'}
          icon={MapPin}
        />
        <StatCard
          title="固定资产及库存"
          value={formatCurrency(stats?.total_inventory_val ?? 0)}
          icon={Package}
        />
        <StatCard
          title="货币资金"
          value={formatCurrency(cashBalance)}
          icon={Banknote}
        />
        <StatCard
          title="本月营收预估"
          value={formatCurrency(stats?.monthly_revenue ?? 0)}
          icon={TrendingUp}
        />
      </div>

      {/* Tabs */}
      <Tabs defaultValue="bank-accounts">
        <TabsList>
          <TabsTrigger value="bank-accounts">银行账户余额</TabsTrigger>
          <TabsTrigger value="ar-ap">应收应付账款</TabsTrigger>
        </TabsList>

        <TabsContent value="bank-accounts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>银行账户余额</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>账户名称</TableHead>
                    <TableHead>开户行</TableHead>
                    <TableHead>账号</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {bankAccounts?.map((account) => (
                    <TableRow key={account.id}>
                      <TableCell className="font-medium">{account.owner_name}</TableCell>
                      <TableCell>{account.bank_name}</TableCell>
                      <TableCell>{account.account_no}</TableCell>
                    </TableRow>
                  ))}
                  {bankAccounts?.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center text-muted-foreground">
                        暂无数据
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ar-ap">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>应收账款</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-green-600 mb-4">
                  {formatCurrency(arapData?.ar_total || 0)}
                </div>
                {arapData?.ar_details && arapData.ar_details.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>客户</TableHead>
                        <TableHead className="text-right">金额</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {arapData.ar_details.map((item, idx) => (
                        <TableRow key={idx}>
                          <TableCell>{item.customer}</TableCell>
                          <TableCell className="text-right text-green-600">{formatCurrency(item.amount)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <p className="text-muted-foreground">暂无应收账款</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>应付账款</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-red-600 mb-4">
                  {formatCurrency(arapData?.ap_total || 0)}
                </div>
                {arapData?.ap_details && arapData.ap_details.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>供应商</TableHead>
                        <TableHead className="text-right">金额</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {arapData.ap_details.map((item, idx) => (
                        <TableRow key={idx}>
                          <TableCell>{item.supplier}</TableCell>
                          <TableCell className="text-right text-red-600">{formatCurrency(item.amount)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <p className="text-muted-foreground">暂无应付账款</p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
