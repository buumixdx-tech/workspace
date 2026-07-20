import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw, Package, Cog, ArrowUpDown, ArrowUp, ArrowDown, ArrowRight, Warehouse, Layers, ChevronDown } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { inventoryApi, EquipmentInventory, MaterialInventory, OperationalStatus, DeviceStatus } from '@/api/endpoints/inventory'
import { formatCurrency, formatDate } from '@/lib/utils'

const OPERATIONAL_STATUS_LABELS: Record<OperationalStatus, string> = {
  IN_STOCK: '库存',
  IN_OPERATION: '运营中',
  DISPOSAL: '已处置',
}

const DEVICE_STATUS_LABELS: Record<DeviceStatus, string> = {
  NORMAL: '正常',
  MAINTENANCE: '维护中',
  DAMAGED: '损坏',
  FAULT: '故障',
  MAINTENANCE_REQUIRED: '需要维护',
  LOCKED: '已锁定',
}

const DEVICE_STATUS_COLORS: Record<string, string> = {
  NORMAL: 'bg-green-100 text-green-800',
  MAINTENANCE: 'bg-yellow-100 text-yellow-800',
  DAMAGED: 'bg-red-100 text-red-800',
  FAULT: 'bg-red-100 text-red-800',
  MAINTENANCE_REQUIRED: 'bg-orange-100 text-orange-800',
  LOCKED: 'bg-gray-100 text-gray-800',
}

function EquipmentDetailDialog({ equipment }: { equipment: EquipmentInventory }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label className="text-muted-foreground">序列号</Label>
          <p className="font-mono font-medium">{equipment.sn}</p>
        </div>
        <div>
          <Label className="text-muted-foreground">SKU</Label>
          <p>{equipment.sku_name}</p>
        </div>
        <div>
          <Label className="text-muted-foreground">运营状态</Label>
          <p>{OPERATIONAL_STATUS_LABELS[equipment.operational_status]}</p>
        </div>
        <div>
          <Label className="text-muted-foreground">设备状态</Label>
          <Badge className={DEVICE_STATUS_COLORS[equipment.device_status]}>
            {DEVICE_STATUS_LABELS[equipment.device_status]}
          </Badge>
        </div>
        <div>
          <Label className="text-muted-foreground">押金</Label>
          <p>{formatCurrency(equipment.deposit_amount)}</p>
        </div>
        <div>
          <Label className="text-muted-foreground">点位</Label>
          <p>{equipment.point_name || '-'}</p>
        </div>
        {equipment.vc_id && (
          <div>
            <Label className="text-muted-foreground">关联合同</Label>
            <Badge variant="outline">VC-{equipment.vc_id}</Badge>
          </div>
        )}
        <div>
          <Label className="text-muted-foreground">创建时间</Label>
          <p>{formatDate(equipment.created_at)}</p>
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// Tab 1: 批次列表（可排序）
// =============================================================================
type SortField = 'sku_name' | 'batch_no' | 'warehouse_point_name' | 'quantity' | 'average_price' | 'production_date'
type SortDir = 'asc' | 'desc'

function SortHeader({ field, current, direction, onClick, children }: { field: SortField; current: SortField; direction: SortDir; onClick: (f: SortField) => void; children: React.ReactNode }) {
  const active = current === field
  return (
    <TableHead className="cursor-pointer select-none" onClick={() => onClick(field)}>
      <div className="flex items-center gap-1">
        {children}
        {active ? (direction === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />) : <ArrowUpDown className="h-3 w-3 opacity-40" />}
      </div>
    </TableHead>
  )
}

function MaterialBatchTable({ items, loading }: { items: MaterialInventory[]; loading: boolean }) {
  const [sortField, setSortField] = useState<SortField>('sku_name')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const sorted = useMemo(() => {
    return [...items].sort((a, b) => {
      let av: any, bv: any
      switch (sortField) {
        case 'sku_name': av = a.sku_name; bv = b.sku_name; break
        case 'batch_no': av = a.batch_no; bv = b.batch_no; break
        case 'warehouse_point_name': av = a.warehouse_point_name; bv = b.warehouse_point_name; break
        case 'quantity': av = a.quantity; bv = b.quantity; break
        case 'average_price': av = a.average_price; bv = b.average_price; break
        case 'production_date': av = a.production_date || ''; bv = b.production_date || ''; break
        default: return 0
      }
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
  }, [items, sortField, sortDir])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('asc')
    }
  }

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <SortHeader field="sku_name" current={sortField} direction={sortDir} onClick={handleSort}>SKU</SortHeader>
              <SortHeader field="batch_no" current={sortField} direction={sortDir} onClick={handleSort}>批次号</SortHeader>
              <SortHeader field="warehouse_point_name" current={sortField} direction={sortDir} onClick={handleSort}>仓库</SortHeader>
              <SortHeader field="quantity" current={sortField} direction={sortDir} onClick={handleSort}>数量</SortHeader>
              <SortHeader field="average_price" current={sortField} direction={sortDir} onClick={handleSort}>单价</SortHeader>
              <SortHeader field="production_date" current={sortField} direction={sortDir} onClick={handleSort}>生产日期</SortHeader>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">加载中...</TableCell></TableRow>
            ) : sorted.length === 0 ? (
              <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">暂无数据</TableCell></TableRow>
            ) : sorted.map(m => (
              <TableRow key={m.id}>
                <TableCell className="font-medium">{m.sku_name}</TableCell>
                <TableCell className="font-mono text-sm">{m.batch_no}</TableCell>
                <TableCell>{m.warehouse_point_name}</TableCell>
                <TableCell className="text-right">{m.quantity.toFixed(2)}</TableCell>
                <TableCell className="text-right">{formatCurrency(m.average_price)}</TableCell>
                <TableCell className="text-sm">{m.production_date ? formatDate(m.production_date) : '-'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

// =============================================================================
// Tab 2: 按SKU聚合
// =============================================================================
function MaterialBySkuTab({ items }: { items: MaterialInventory[] }) {
  const [openSkus, setOpenSkus] = useState<Set<number>>(new Set())

  const skuGroups = useMemo(() => {
    const map = new Map<number, { sku_id: number; sku_name: string; batches: MaterialInventory[]; total_qty: number }>()
    items.forEach(m => {
      if (!map.has(m.sku_id)) {
        map.set(m.sku_id, { sku_id: m.sku_id, sku_name: m.sku_name, batches: [], total_qty: 0 })
      }
      const g = map.get(m.sku_id)!
      g.batches.push(m)
      g.total_qty += m.quantity
    })
    return Array.from(map.values()).sort((a, b) => b.total_qty - a.total_qty)
  }, [items])

  const toggle = (sku_id: number) => {
    setOpenSkus(s => { const n = new Set(s); n.has(sku_id) ? n.delete(sku_id) : n.add(sku_id); return n })
  }

  if (items.length === 0) return <div className="text-center py-8 text-muted-foreground">暂无数据</div>

  return (
    <div className="grid grid-cols-1 gap-4">
      {skuGroups.map(sku => (
        <Card key={sku.sku_id}>
          <CardHeader className="flex flex-row items-center justify-between pb-2 pt-4">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" className="p-0 h-6 w-6" onClick={() => toggle(sku.sku_id)}>
                <ChevronDown className={`h-4 w-4 transition-transform ${openSkus.has(sku.sku_id) ? '' : '-rotate-90'}`} />
              </Button>
              <CardTitle className="text-base">{sku.sku_name}</CardTitle>
              <Badge variant="outline">{sku.batches.length} 批次</Badge>
            </div>
            <div className="flex items-center gap-4 mr-4">
              <span className="text-sm text-muted-foreground">总数量</span>
              <span className="font-bold text-lg">{sku.total_qty.toFixed(2)}</span>
            </div>
          </CardHeader>
          {openSkus.has(sku.sku_id) && (
            <CardContent className="pt-0 pl-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>批次号</TableHead>
                    <TableHead>仓库</TableHead>
                    <TableHead className="text-right">数量</TableHead>
                    <TableHead className="text-right">单价</TableHead>
                    <TableHead>生产日期</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sku.batches.map(b => (
                    <TableRow key={b.id}>
                      <TableCell className="font-mono text-sm">{b.batch_no}</TableCell>
                      <TableCell>{b.warehouse_point_name}</TableCell>
                      <TableCell className="text-right">{b.quantity.toFixed(2)}</TableCell>
                      <TableCell className="text-right">{formatCurrency(b.average_price)}</TableCell>
                      <TableCell className="text-sm">{b.production_date ? formatDate(b.production_date) : '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          )}
        </Card>
      ))}
    </div>
  )
}

// =============================================================================
// Tab 3: 按仓库聚合
// =============================================================================
function MaterialByWarehouseTab({ items }: { items: MaterialInventory[] }) {
  const [openPoints, setOpenPoints] = useState<Set<number>>(new Set())

  const pointGroups = useMemo(() => {
    const map = new Map<number, { point_id: number; point_name: string; skus: { sku_id: number; sku_name: string; total_qty: number }[] }>()
    items.forEach(m => {
      if (!map.has(m.warehouse_point_id)) {
        map.set(m.warehouse_point_id, { point_id: m.warehouse_point_id, point_name: m.warehouse_point_name, skus: [] })
      }
      const g = map.get(m.warehouse_point_id)!
      const existing = g.skus.find(s => s.sku_id === m.sku_id)
      if (existing) {
        existing.total_qty += m.quantity
      } else {
        g.skus.push({ sku_id: m.sku_id, sku_name: m.sku_name, total_qty: m.quantity })
      }
    })
    return Array.from(map.values()).sort((a, b) => b.skus.length - a.skus.length)
  }, [items])

  const toggle = (point_id: number) => {
    setOpenPoints(s => { const n = new Set(s); n.has(point_id) ? n.delete(point_id) : n.add(point_id); return n })
  }

  if (items.length === 0) return <div className="text-center py-8 text-muted-foreground">暂无数据</div>

  return (
    <div className="grid grid-cols-1 gap-4">
      {pointGroups.map(p => (
        <Card key={p.point_id}>
          <CardHeader className="flex flex-row items-center justify-between pb-2 pt-4">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" className="p-0 h-6 w-6" onClick={() => toggle(p.point_id)}>
                <ChevronDown className={`h-4 w-4 transition-transform ${openPoints.has(p.point_id) ? '' : '-rotate-90'}`} />
              </Button>
              <Warehouse className="h-4 w-4" />
              <CardTitle className="text-base">{p.point_name}</CardTitle>
              <Badge variant="outline">{p.skus.length} 个SKU</Badge>
            </div>
          </CardHeader>
          {openPoints.has(p.point_id) && (
            <CardContent className="pt-0 pl-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>SKU</TableHead>
                    <TableHead className="text-right">库存总量</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {p.skus.map(s => (
                    <TableRow key={s.sku_id}>
                      <TableCell className="font-medium">{s.sku_name}</TableCell>
                      <TableCell className="text-right font-medium">{s.total_qty.toFixed(2)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          )}
        </Card>
      ))}
    </div>
  )
}

export function InventoryPage() {
  const [selectedEquipment, setSelectedEquipment] = useState<EquipmentInventory | null>(null)

  const { data: equipment, isLoading: eqLoading, refetch: eqRefetch } = useQuery({
    queryKey: ['equipment-list'],
    queryFn: () => inventoryApi.getEquipment({ size: 100 }),
  })

  const { data: material, isLoading: matLoading, refetch: matRefetch, error: matError } = useQuery({
    queryKey: ['material-list'],
    queryFn: () => inventoryApi.getMaterial({ size: 100 }),
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">库存看板</h2>
      </div>

      <Tabs defaultValue="equipment">
        <TabsList>
          <TabsTrigger value="equipment">
            <Cog className="mr-2 h-4 w-4" />设备库存
          </TabsTrigger>
          <TabsTrigger value="material">
            <Package className="mr-2 h-4 w-4" />物料库存
          </TabsTrigger>
        </TabsList>

        <TabsContent value="equipment" className="space-y-4">
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => eqRefetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>

          {/* Summary */}
          <div className="grid grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-4">
                <div className="text-2xl font-bold">{equipment?.total || 0}</div>
                <p className="text-sm text-muted-foreground">设备总数</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="text-2xl font-bold text-green-600">
                  {equipment?.items?.filter(e => e.operational_status === 'IN_OPERATION').length || 0}
                </div>
                <p className="text-sm text-muted-foreground">运营中</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="text-2xl font-bold text-blue-600">
                  {equipment?.items?.filter(e => e.operational_status === 'IN_STOCK').length || 0}
                </div>
                <p className="text-sm text-muted-foreground">库存</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="text-2xl font-bold text-red-600">
                  {equipment?.items?.filter(e => e.device_status === 'FAULT' || e.device_status === 'DAMAGED').length || 0}
                </div>
                <p className="text-sm text-muted-foreground">异常</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>序列号</TableHead>
                    <TableHead>SKU</TableHead>
                    <TableHead>运营状态</TableHead>
                    <TableHead>设备状态</TableHead>
                    <TableHead>押金</TableHead>
                    <TableHead>点位</TableHead>
                    <TableHead>关联合同</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {equipment?.items?.map(eq => (
                    <TableRow key={eq.sn} className="cursor-pointer" onClick={() => setSelectedEquipment(eq)}>
                      <TableCell className="font-mono font-medium">{eq.sn}</TableCell>
                      <TableCell>{eq.sku_name}</TableCell>
                      <TableCell>{OPERATIONAL_STATUS_LABELS[eq.operational_status]}</TableCell>
                      <TableCell>
                        <Badge className={DEVICE_STATUS_COLORS[eq.device_status]}>
                          {DEVICE_STATUS_LABELS[eq.device_status]}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">{formatCurrency(eq.deposit_amount)}</TableCell>
                      <TableCell>{eq.point_name || '-'}</TableCell>
                      <TableCell>
                        {eq.vc_id && <Badge variant="outline">VC-{eq.vc_id}</Badge>}
                      </TableCell>
                    </TableRow>
                  ))}
                  {!equipment?.items?.length && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground">
                        {eqLoading ? '加载中...' : '暂无数据'}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="material" className="space-y-4">
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => matRefetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>

          {/* Summary */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-4">
                <div className="text-2xl font-bold">{material?.total || 0}</div>
                <p className="text-sm text-muted-foreground">批次总数</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="text-2xl font-bold">
                  {material?.items?.reduce((sum, m) => sum + m.quantity, 0) || 0}
                </div>
                <p className="text-sm text-muted-foreground">物料总量</p>
              </CardContent>
            </Card>
          </div>

          {/* 3-sub-tab structure */}
          <Tabs defaultValue="batch-list">
            <TabsList className="mb-4">
              <TabsTrigger value="batch-list">批次列表</TabsTrigger>
              <TabsTrigger value="by-sku"><Layers className="mr-1 h-3 w-3" />按SKU聚合</TabsTrigger>
              <TabsTrigger value="by-warehouse"><Warehouse className="mr-1 h-3 w-3" />按仓库聚合</TabsTrigger>
            </TabsList>

            {/* ===== Tab 1: 批次列表（可排序） ===== */}
            <TabsContent value="batch-list">
              <MaterialBatchTable items={material?.items || []} loading={matLoading} />
            </TabsContent>

            {/* ===== Tab 2: 按SKU聚合 ===== */}
            <TabsContent value="by-sku">
              <MaterialBySkuTab items={material?.items || []} />
            </TabsContent>

            {/* ===== Tab 3: 按仓库聚合 ===== */}
            <TabsContent value="by-warehouse">
              <MaterialByWarehouseTab items={material?.items || []} />
            </TabsContent>
          </Tabs>
        </TabsContent>
      </Tabs>

      {selectedEquipment && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-lg mx-4">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>设备详情</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => setSelectedEquipment(null)}>关闭</Button>
            </CardHeader>
            <CardContent>
              <EquipmentDetailDialog equipment={selectedEquipment} />
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
