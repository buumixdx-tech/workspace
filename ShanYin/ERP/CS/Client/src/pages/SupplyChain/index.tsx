import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, RefreshCw, X, Pencil, Trash2, Eye, AlertTriangle } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { supplyChainApi, SupplyChain, SupplyChainType, SupplyChainItem, CreateSupplyChainSchema, UpdateSupplyChainSchema } from '@/api/endpoints/supplyChain'
import { masterApi } from '@/api/endpoints/master'
import { formatDate, formatCurrency } from '@/lib/utils'

const TYPE_COLORS: Record<SupplyChainType, string> = {
  '设备': 'bg-blue-100 text-blue-800',
  '物料': 'bg-orange-100 text-orange-800',
}

interface ItemFormRow {
  sku_id: string
  price: string
  is_floating: boolean
}

function CreateSupplyChainDialog({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)
  const [formData, setFormData] = useState({
    supplier_id: '',
    type: '设备' as SupplyChainType,
    prepayment_percent: '30',
    payment_days: '30',
    contract_num: '',
  })
  const [items, setItems] = useState<ItemFormRow[]>([])

  const { data: suppliers } = useQuery({
    queryKey: ['suppliers'],
    queryFn: () => masterApi.suppliers.list({ size: 100 }),
  })

  const { data: skus } = useQuery({
    queryKey: ['skus'],
    queryFn: () => masterApi.skus.list({ size: 100 }),
  })

  const createMutation = useMutation({
    mutationFn: () => {
      const supplier = suppliers?.items?.find(s => s.id === parseInt(formData.supplier_id))
      return supplyChainApi.create({
        supplier_id: parseInt(formData.supplier_id),
        supplier_name: supplier?.name || '',
        type: formData.type,
        items: items.filter(i => i.sku_id).map(item => ({
          sku_id: parseInt(item.sku_id),
          price: parseFloat(item.price) || 0,
          is_floating: item.is_floating ?? false,
        })),
        payment_terms: {
          prepayment_percent: parseInt(formData.prepayment_percent) || 30,
          payment_days: parseInt(formData.payment_days) || 30,
        },
        contract_num: formData.contract_num || undefined,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supplychain-list'] })
      setIsOpen(false)
      resetForm()
      onSuccess()
    },
  })

  const resetForm = () => {
    setFormData({
      supplier_id: '',
      type: '设备',
      prepayment_percent: '30',
      payment_days: '30',
      contract_num: '',
    })
    setItems([])
  }

  const addItem = () => {
    setItems([...items, { sku_id: '', price: '', is_floating: false }])
  }

  const updateItem = (index: number, field: keyof ItemFormRow, value: string | boolean) => {
    const updated = [...items]
    updated[index] = { ...updated[index], [field]: value }
    setItems(updated)
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { setIsOpen(open); if (!open) resetForm() }}>
      <DialogTrigger asChild>
        <Button><Plus className="mr-2 h-4 w-4" />新建供应链</Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>新建供应链协议</DialogTitle>
        </DialogHeader>
        <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate() }} className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>供应商</Label>
              <Select value={formData.supplier_id} onValueChange={(v) => setFormData({ ...formData, supplier_id: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="选择供应商" />
                </SelectTrigger>
                <SelectContent>
                  {suppliers?.items?.map(s => (
                    <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>协议类型</Label>
              <Select value={formData.type} onValueChange={(v) => setFormData({ ...formData, type: v as SupplyChainType })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="EQUIPMENT">设备</SelectItem>
                  <SelectItem value="MATERIAL">物料</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>预付比例 (%)</Label>
              <Input type="number" value={formData.prepayment_percent} onChange={(e) => setFormData({ ...formData, prepayment_percent: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>账期 (天)</Label>
              <Input type="number" value={formData.payment_days} onChange={(e) => setFormData({ ...formData, payment_days: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>合同号</Label>
              <Input value={formData.contract_num} onChange={(e) => setFormData({ ...formData, contract_num: e.target.value })} />
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>SKU定价</Label>
              <Button type="button" variant="outline" size="sm" onClick={addItem}>
                <Plus className="mr-2 h-4 w-4" />添加SKU
              </Button>
            </div>
            {items.map((item, idx) => (
              <Card key={idx}>
                <CardContent className="pt-4">
                  <div className="grid grid-cols-4 gap-3 items-end">
                    <div className="space-y-2">
                      <Label className="text-xs">SKU</Label>
                      <Select value={item.sku_id} onValueChange={(v) => updateItem(idx, 'sku_id', v)}>
                        <SelectTrigger><SelectValue placeholder="选择SKU" /></SelectTrigger>
                        <SelectContent>
                          {skus?.items?.map(s => (
                            <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">协议单价</Label>
                      <Input
                        type="number"
                        value={item.price}
                        onChange={(e) => updateItem(idx, 'price', e.target.value)}
                        disabled={item.is_floating}
                        placeholder={item.is_floating ? '浮动价' : ''}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">浮动定价</Label>
                      <div className="flex items-center gap-2 h-10">
                        <Switch
                          checked={item.is_floating}
                          onCheckedChange={(checked) => updateItem(idx, 'is_floating', checked)}
                        />
                        <span className="text-sm">{item.is_floating ? '是' : '否'}</span>
                      </div>
                    </div>
                    <div className="flex items-end">
                      <Button type="button" variant="ghost" onClick={() => setItems(items.filter((_, i) => i !== idx))}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {items.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">点击"添加SKU"来添加定价条目</p>
            )}
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setIsOpen(false)}>取消</Button>
            <Button type="submit" disabled={!formData.supplier_id || createMutation.isPending}>
              {createMutation.isPending ? '创建中...' : '创建'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function UpdateSupplyChainDialog({ supplyChain, onSuccess }: { supplyChain: SupplyChain; onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)
  const [formData, setFormData] = useState({
    prepayment_percent: '30',
    payment_days: '30',
  })
  const [items, setItems] = useState<ItemFormRow[]>([])

  const { data: skus } = useQuery({
    queryKey: ['skus'],
    queryFn: () => masterApi.skus.list({ size: 100 }),
  })

  const updateMutation = useMutation({
    mutationFn: () => {
      return supplyChainApi.update({
        id: supplyChain.id,
        supplier_name: supplyChain.supplier_name,
        type: supplyChain.type,
        items: items.filter(i => i.sku_id).map(item => ({
          sku_id: parseInt(item.sku_id),
          price: parseFloat(item.price) || 0,
          is_floating: item.is_floating ?? false,
        })),
        payment_terms: {
          prepayment_percent: parseInt(formData.prepayment_percent) || 30,
          payment_days: parseInt(formData.payment_days) || 30,
        },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supplychain-list'] }).then(() => {
        setIsOpen(false)
        onSuccess()
      }).catch(() => {
        setIsOpen(false)
        onSuccess()
      })
    },
    onError: (err: Error) => {
      alert('更新失败: ' + err.message)
    },
  })

  const openWithData = () => {
    setFormData({
      prepayment_percent: String(supplyChain.payment_terms?.prepayment_percent || 30),
      payment_days: String(supplyChain.payment_terms?.payment_days || 30),
    })
    setItems(supplyChain.items.map(i => ({
      sku_id: String(i.sku_id),
      price: String(i.price),
      is_floating: i.is_floating ?? false,
    })))
    setIsOpen(true)
  }

  const addItem = () => {
    setItems([...items, { sku_id: '', price: '', is_floating: false }])
  }

  const updateItem = (index: number, field: keyof ItemFormRow, value: string | boolean) => {
    const updated = [...items]
    updated[index] = { ...updated[index], [field]: value }
    setItems(updated)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" onClick={openWithData}><Pencil className="h-4 w-4" /></Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>编辑供应链协议</DialogTitle>
        </DialogHeader>
        <form onSubmit={(e) => { e.preventDefault(); updateMutation.mutate() }} className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>供应商</Label>
              <Input value={supplyChain.supplier_name} disabled />
            </div>
            <div className="space-y-2">
              <Label>协议类型</Label>
              <Input value={supplyChain.type === '设备' ? '设备' : '物料'} disabled />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>预付比例 (%)</Label>
              <Input type="number" value={formData.prepayment_percent} onChange={(e) => setFormData({ ...formData, prepayment_percent: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>账期 (天)</Label>
              <Input type="number" value={formData.payment_days} onChange={(e) => setFormData({ ...formData, payment_days: e.target.value })} />
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>SKU定价</Label>
              <Button type="button" variant="outline" size="sm" onClick={addItem}>
                <Plus className="mr-2 h-4 w-4" />添加SKU
              </Button>
            </div>
            {items.map((item, idx) => (
              <Card key={idx}>
                <CardContent className="pt-4">
                  <div className="grid grid-cols-4 gap-3 items-end">
                    <div className="space-y-2">
                      <Label className="text-xs">SKU</Label>
                      <Select value={item.sku_id} onValueChange={(v) => updateItem(idx, 'sku_id', v)}>
                        <SelectTrigger><SelectValue placeholder="选择SKU" /></SelectTrigger>
                        <SelectContent>
                          {skus?.items?.map(s => (
                            <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">协议单价</Label>
                      <Input
                        type="number"
                        value={item.price}
                        onChange={(e) => updateItem(idx, 'price', e.target.value)}
                        disabled={item.is_floating}
                        placeholder={item.is_floating ? '浮动价' : ''}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">浮动定价</Label>
                      <div className="flex items-center gap-2 h-10">
                        <Switch
                          checked={item.is_floating}
                          onCheckedChange={(checked) => updateItem(idx, 'is_floating', checked)}
                        />
                        <span className="text-sm">{item.is_floating ? '是' : '否'}</span>
                      </div>
                    </div>
                    <div className="flex items-end">
                      <Button type="button" variant="ghost" onClick={() => setItems(items.filter((_, i) => i !== idx))}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {items.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">点击"添加SKU"来添加定价条目</p>
            )}
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setIsOpen(false)}>取消</Button>
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? '保存中...' : '保存'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function DeleteSupplyChainDialog({ supplyChain, onSuccess }: { supplyChain: SupplyChain; onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)

  const deleteMutation = useMutation({
    mutationFn: () => supplyChainApi.delete(supplyChain.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supplychain-list'] })
      setIsOpen(false)
      onSuccess()
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm"><Trash2 className="h-4 w-4" /></Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>删除供应链协议</DialogTitle>
        </DialogHeader>
        <p>确定要删除供应链协议 SC-{supplyChain.id} ({supplyChain.supplier_name}) 吗？</p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setIsOpen(false)}>取消</Button>
          <Button variant="destructive" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
            {deleteMutation.isPending ? '删除中...' : '删除'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function SupplyChainDetailDialog({ supplyChain, onClose }: { supplyChain: SupplyChain; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState('pricing')

  const { data: detail, isLoading } = useQuery({
    queryKey: ['supplychain-detail', supplyChain.id],
    queryFn: () => supplyChainApi.getDetail(supplyChain.id),
    enabled: activeTab === 'pricing',
  })

  const { data: skus } = useQuery({
    queryKey: ['skus-for-sc-detail'],
    queryFn: () => masterApi.skus.list({ size: 100 }),
  })

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>供应链协议 SC-{supplyChain.id}</span>
            <Badge className={TYPE_COLORS[supplyChain.type]}>
              {supplyChain.type === '设备' ? '设备' : '物料'}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <Label className="text-muted-foreground">供应商</Label>
              <p className="font-medium">{supplyChain.supplier_name}</p>
            </div>
            <div>
              <Label className="text-muted-foreground">合同号</Label>
              <p>{supplyChain.contract_num || '-'}</p>
            </div>
            <div>
              <Label className="text-muted-foreground">预付比例</Label>
              <p>{supplyChain.payment_terms?.prepayment_percent || 0}%</p>
            </div>
            <div>
              <Label className="text-muted-foreground">账期</Label>
              <p>{supplyChain.payment_terms?.payment_days || 0}天</p>
            </div>
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="pricing">价格协议明细</TabsTrigger>
              <TabsTrigger value="items">全部SKU</TabsTrigger>
            </TabsList>

            <TabsContent value="pricing">
              {isLoading ? (
                <div className="text-center py-4">加载中...</div>
              ) : detail ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>SKU</TableHead>
                      <TableHead className="text-right">协议单价</TableHead>
                      <TableHead>定价模式</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {detail.items.map(item => (
                      <TableRow key={item.sku_id}>
                        <TableCell>{skus?.items?.find(s => s.id === item.sku_id)?.name || item.sku_name || `SKU-${item.sku_id}`}</TableCell>
                        <TableCell className="text-right">
                          {item.is_floating ? (
                            <span className="text-muted-foreground">浮动</span>
                          ) : (
                            formatCurrency(item.price)
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant={item.is_floating ? 'outline' : 'secondary'}>
                            {item.is_floating ? '浮动定价' : '固定协议价'}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                    {detail.items.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={3} className="text-center text-muted-foreground">暂无数据</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-4">无数据</div>
              )}
            </TabsContent>

            <TabsContent value="items">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>SKU ID</TableHead>
                    <TableHead>名称</TableHead>
                    <TableHead className="text-right">押金</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {supplyChain.items.map(item => (
                    <TableRow key={item.sku_id}>
                      <TableCell>{item.sku_id}</TableCell>
                      <TableCell>{skus?.items?.find(s => s.id === item.sku_id)?.name || item.sku_name || '-'}</TableCell>
                      <TableCell className="text-right">{formatCurrency(item.deposit)}</TableCell>
                    </TableRow>
                  ))}
                  {supplyChain.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center text-muted-foreground">暂无数据</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TabsContent>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function SupplyChainPage() {
  const [typeFilter, setTypeFilter] = useState<SupplyChainType | 'ALL'>('ALL')
  const [selectedSupplyChain, setSelectedSupplyChain] = useState<SupplyChain | null>(null)
  const [supplierNameKw, setSupplierNameKw] = useState('')
  const [skuNameKw, setSkuNameKw] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['supplychain-list', typeFilter, supplierNameKw, skuNameKw, page],
    queryFn: () => supplyChainApi.list({
      type: typeFilter !== 'ALL' ? typeFilter : undefined,
      supplier_name_kw: supplierNameKw || undefined,
      sku_name_kw: skuNameKw || undefined,
      page,
      size: pageSize,
    }),
  })

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1) }, [typeFilter, supplierNameKw, skuNameKw])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">供应链管理</h2>
        <CreateSupplyChainDialog onSuccess={() => refetch()} />
      </div>

      <div className="flex gap-4 flex-wrap">
        <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v as SupplyChainType | 'ALL')}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder="类型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">全部</SelectItem>
            <SelectItem value="EQUIPMENT">设备</SelectItem>
            <SelectItem value="MATERIAL">物料</SelectItem>
          </SelectContent>
        </Select>
        <Input
          placeholder="供应商名称"
          value={supplierNameKw}
          onChange={(e) => setSupplierNameKw(e.target.value)}
          className="w-40"
        />
        <Input
          placeholder="SKU名称"
          value={skuNameKw}
          onChange={(e) => setSkuNameKw(e.target.value)}
          className="w-40"
        />
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>供应商</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>预付比例</TableHead>
                <TableHead>账期</TableHead>
                <TableHead>合同号</TableHead>
                <TableHead>SKU数量</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items?.map(sc => (
                <TableRow key={sc.id}>
                  <TableCell className="font-medium">SC-{sc.id}</TableCell>
                  <TableCell>{sc.supplier_name}</TableCell>
                  <TableCell>
                    <Badge className={TYPE_COLORS[sc.type]}>{sc.type === '设备' ? '设备' : '物料'}</Badge>
                  </TableCell>
                  <TableCell>{sc.payment_terms?.prepayment_percent || 0}%</TableCell>
                  <TableCell>{sc.payment_terms?.payment_days || 0}天</TableCell>
                  <TableCell>{sc.contract_num || '-'}</TableCell>
                  <TableCell>{sc.items?.length || 0}</TableCell>
                  <TableCell>{formatDate(sc.created_at)}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setSelectedSupplyChain(sc)}>
                        <Eye className="h-4 w-4" />
                      </Button>
                      <UpdateSupplyChainDialog supplyChain={sc} onSuccess={() => refetch()} />
                      <DeleteSupplyChainDialog supplyChain={sc} onSuccess={() => refetch()} />
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!data?.items?.length && (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-muted-foreground">
                    {isLoading ? '加载中...' : '暂无数据'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t">
              <div className="text-sm text-muted-foreground">
                共 {data?.total || 0} 条，第 {page} / {totalPages} 页
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1}
                >
                  上一页
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                >
                  下一页
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {selectedSupplyChain && (
        <SupplyChainDetailDialog supplyChain={selectedSupplyChain} onClose={() => setSelectedSupplyChain(null)} />
      )}
    </div>
  )
}
