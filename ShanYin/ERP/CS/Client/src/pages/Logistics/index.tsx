import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { jsPDF } from 'jspdf'
import { Plus, Search, X, RefreshCw, Package, Check, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DatePicker } from '@/components/ui/date-picker'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import {
  logisticsApi, Logistics, LogisticsDetail, LogisticsStatus, ExpressStatus, ExpressOrder,
  CreateLogisticsPlanSchema, AddressInfo,
  ExpressOrderGlobalItem, ExpressOrderGlobalParams,
  LogisticsGlobalItem, LogisticsGlobalParams,
} from '@/api/endpoints/logistics'
import { vcApi, VCDetailResponse, VCElement } from '@/api/endpoints/vc'
import { masterApi } from '@/api/endpoints/master'
import { formatDate } from '@/lib/utils'

const STATUS_COLORS: Record<string, string> = {
  待发货: 'bg-yellow-100 text-yellow-800',
  在途: 'bg-blue-100 text-blue-800',
  签收: 'bg-green-100 text-green-800',
  完成: 'bg-gray-100 text-gray-800',
  取消: 'bg-red-100 text-red-800',
}

// =============================================================================
// Create Logistics Dialog
// =============================================================================
function CreateLogisticsDialog({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [step, setStep] = useState<1 | 2>(1)
  const [vcId, setVcId] = useState('')
  const [createdDate, setCreatedDate] = useState('')
  const [orders, setOrders] = useState<ExpressOrderDraft[]>([])
  const [isLoadingOrders, setIsLoadingOrders] = useState(false)

  const { data: vcs } = useQuery({
    queryKey: ['vcs-for-logistics'],
    queryFn: () => vcApi.list({ status: '执行', has_logistics: false, size: 100 }),
  })

  const { data: skus } = useQuery({
    queryKey: ['skus-for-logistics'],
    queryFn: () => masterApi.skus.list({ size: 100 }),
    enabled: isOpen,
  })

  const { data: points } = useQuery({
    queryKey: ['points-for-create-logistics'],
    queryFn: () => masterApi.points.list({ size: 500 }),
    enabled: isOpen,
  })

  const createMutation = useMutation({
    mutationFn: () => logisticsApi.createPlan({
      vc_id: parseInt(vcId),
      orders: orders.map(o => ({
        tracking_number: o.tracking_number,
        items: o.items.map(i => ({ sku_id: i.sku_id, qty: i.qty })),
        address_info: {
          发货点位Id: o.shipping_point_id,
          发货点位名称: o.shipping_point_name,
          发货地址: o.shipping_address,
          发货联系电话: o.shipping_phone,
          收货点位Id: o.receiving_point_id,
          收货点位名称: o.receiving_point_name,
          收货地址: o.receiving_address,
          收货联系电话: o.receiving_phone,
        },
      })),
      created_date: createdDate || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logistics-list'] })
      setIsOpen(false)
      setStep(1)
      setVcId('')
      setCreatedDate('')
      setOrders([])
      onSuccess()
    },
  })

  const handleVcSelect = (id: string) => {
    setVcId(id)
    setIsLoadingOrders(true)
    const vc = vcs?.items?.find(v => v.id === parseInt(id))
    if (!vc) { setIsLoadingOrders(false); return }
    Promise.all([
      vcApi.getDetail(parseInt(id)),
      masterApi.points.list({ size: 500 }),
    ]).then(([detail, pointsResult]) => {
      initializeAutoOrders(detail, pointsResult?.items || [])
      setCreatedDate(detail.created_at ? detail.created_at.slice(0, 10) : '')
      setStep(2)
    }).finally(() => setIsLoadingOrders(false))
  }

  const initializeAutoOrders = (detail: VCDetailResponse, pointsList: any[]) => {
    const elemList = detail.elements?.elements || detail.elements?.items
    if (!elemList?.length || !pointsList?.length) return
    const vcType = detail.type
    let grouped: Record<string, VCElement[]> = {}

    if (vcType === '物料供应' || vcType === '物料采购') {
      elemList.forEach(el => {
        const key = `${el.shipping_point_id}-${el.receiving_point_id}`
        if (!grouped[key]) grouped[key] = []
        grouped[key].push(el)
      })
    } else if (vcType === '退货') {
      elemList.forEach(el => {
        const key = `${el.shipping_point_name || '未知'}|${el.receiving_point_name || '默认'}`
        if (!grouped[key]) grouped[key] = []
        grouped[key].push(el)
      })
    } else {
      elemList.forEach(el => {
        const key = String(el.receiving_point_id)
        if (!grouped[key]) grouped[key] = []
        grouped[key].push(el)
      })
    }

    const prefix = vcType === '退货' ? 'RET' : 'EXP'
    const newOrders: ExpressOrderDraft[] = Object.entries(grouped).map(([groupKey, els], idx) => {
      let rpId = 0, rpName = '', rpAddr = '', rpPhone = ''
      let spId = 0, spName = '', spAddr = '', spPhone = ''

      if (vcType === '物料供应' || vcType === '物料采购') {
        const [sId, rId] = groupKey.split('-').map(Number)
        rpId = rId
        const rp = pointsList.find((p: any) => p.id === rpId)
        rpName = rp?.name || els[0].receiving_point_name || ''
        rpAddr = rp?.address || ''
        spId = sId
        const sp = pointsList.find((p: any) => p.id === spId)
        spName = sp?.name || els[0].shipping_point_name || ''
        spAddr = sp?.address || ''
      } else if (vcType === '退货') {
        const [sName, rName] = groupKey.split('|')
        spName = sName
        rpName = rName
        const sp = pointsList.find((p: any) => p.name === sName)
        const rp = pointsList.find((p: any) => p.name === rName)
        if (sp) { spId = sp.id; spAddr = sp.address || '' }
        if (rp) { rpId = rp.id; rpAddr = rp.address || '' }
      } else {
        rpId = parseInt(groupKey)
        const rp = pointsList.find((p: any) => p.id === rpId)
        rpName = rp?.name || els[0].receiving_point_name || ''
        rpAddr = rp?.address || ''
      }

      return {
        tracking_number: `${prefix}${Date.now().toString().slice(-6)}${idx}`,
        items: els.map(el => ({ sku_id: el.sku_id, sku_name: el.sku_name || `SKU-${el.sku_id}`, qty: el.qty })),
        receiving_point_id: rpId, receiving_point_name: rpName, receiving_address: rpAddr, receiving_phone: rpPhone,
        shipping_point_id: spId, shipping_point_name: spName, shipping_address: spAddr, shipping_phone: spPhone,
      }
    })
    setOrders(newOrders)
  }

  const updateOrderTracking = (idx: number, tracking: string) => {
    const updated = [...orders]
    updated[idx] = { ...updated[idx], tracking_number: tracking }
    setOrders(updated)
  }

  const deleteOrder = (idx: number) => {
    setOrders(orders.filter((_, i) => i !== idx))
  }

  const addOrder = () => {
    setOrders([...orders, {
      tracking_number: `EXP${Date.now().toString().slice(-6)}`,
      items: [],
      receiving_point_id: 0, receiving_point_name: '', receiving_address: '', receiving_phone: '',
      shipping_point_id: 0, shipping_point_name: '', shipping_address: '', shipping_phone: '',
    }])
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { setIsOpen(open); if (!open) { setStep(1); setVcId(''); setOrders([]); setCreatedDate('') } }}>
      <DialogTrigger asChild>
        <Button><Plus className="mr-2 h-4 w-4" />新建物流任务</Button>
      </DialogTrigger>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>新建物流任务</DialogTitle>
        </DialogHeader>

        {/* Step 1: VC selection only */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>关联虚拟合同</Label>
              {isLoadingOrders ? (
                <div className="text-sm text-muted-foreground py-2">加载中...</div>
              ) : (
                <Select value={vcId} onValueChange={handleVcSelect}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择合同" />
                  </SelectTrigger>
                  <SelectContent>
                    {vcs?.items?.map(vc => {
                      const els = (vc.elements as any)?.items || []
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
              )}
            </div>
          </div>
        )}

        {/* Step 2: Full form */}
        {step === 2 && (
          <div className="space-y-4">
            {/* Top bar: selected VC info + re-select */}
            <div className="flex items-center justify-between bg-muted rounded-md px-3 py-2">
              <div className="text-sm">
                已选择：<span className="font-medium">VC-{vcId}</span>
              </div>
              <Button type="button" variant="ghost" size="sm" onClick={() => { setStep(1); setVcId(''); setOrders([]); setCreatedDate('') }}>
                重选合同
              </Button>
            </div>

            <div className="space-y-2">
              <Label className="text-xs">物流创建日期</Label>
              <DatePicker
                value={createdDate}
                onChange={setCreatedDate}
              />
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-base">快递单列表（自动生成，可编辑）</Label>
                <Button type="button" variant="outline" size="sm" onClick={addOrder}>
                  <Plus className="h-4 w-4 mr-1" />添加快递单
                </Button>
              </div>
              {orders.map((order, idx) => (
                <Card key={idx}>
                  <CardContent className="pt-4">
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label className="text-base">快递单 #{idx + 1}</Label>
                        <Button type="button" variant="ghost" size="sm" onClick={() => deleteOrder(idx)}>
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs">快递单号</Label>
                          <Input
                            value={order.tracking_number}
                            onChange={(e) => updateOrderTracking(idx, e.target.value)}
                            placeholder="输入快递单号"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs">发货点位</Label>
                          <Input value={order.shipping_point_name || '（自动）'} disabled className="bg-muted" />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs">收货点位名称</Label>
                          <Input
                            value={order.receiving_point_name}
                            onChange={(e) => setOrders(orders.map((o, i) => i === idx ? { ...o, receiving_point_name: e.target.value } : o))}
                            placeholder="收货点位名称"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs">收货点位ID</Label>
                          <Input
                            type="number"
                            value={order.receiving_point_id || ''}
                            onChange={(e) => setOrders(orders.map((o, i) => i === idx ? { ...o, receiving_point_id: parseInt(e.target.value) || 0 } : o))}
                            placeholder="收货点位ID"
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs">收货地址</Label>
                          <Input value={order.receiving_address} onChange={(e) => setOrders(orders.map((o, i) => i === idx ? { ...o, receiving_address: e.target.value } : o))} placeholder="收货地址" />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs">联系电话</Label>
                          <Input value={order.receiving_phone} onChange={(e) => setOrders(orders.map((o, i) => i === idx ? { ...o, receiving_phone: e.target.value } : o))} placeholder="联系电话" />
                        </div>
                      </div>
                      {order.items.length > 0 && (
                        <div>
                          <Label className="text-xs mb-1 block">标的明细</Label>
                          <div className="bg-gray-50 dark:bg-gray-800 rounded-md p-2 text-sm space-y-1">
                            {order.items.map((item, i) => (
                              <div key={i} className="flex justify-between">
                                <span>{item.sku_name}</span>
                                <span className="text-muted-foreground">x{item.qty}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            <div className="flex justify-between">
              <Button type="button" variant="outline" onClick={() => setIsOpen(false)}>取消</Button>
              <div className="flex gap-2">
                {orders.length > 0 && (
                  <Button variant="outline" onClick={() => setOrders([])}>清空</Button>
                )}
                <Button
                  onClick={() => setConfirmOpen(true)}
                  disabled={orders.length === 0 || orders.every(o => !o.tracking_number) || createMutation.isPending}
                >
                  创建物流单 ({orders.filter(o => o.tracking_number).length}单)
                </Button>
              </div>
            </div>
            <ConfirmDialog
              open={confirmOpen}
              onOpenChange={setConfirmOpen}
              title="确认创建物流任务"
              description={`将为 VC-${vcId} 创建 ${orders.filter(o => o.tracking_number).length} 个快递单，确定继续？`}
              confirmLabel="创建"
              onConfirm={() => { setConfirmOpen(false); createMutation.mutate() }}
              isPending={createMutation.isPending}
            />
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

interface ExpressOrderDraft {
  tracking_number: string
  items: { sku_id: number; sku_name: string; qty: number }[]
  receiving_point_id: number; receiving_point_name: string; receiving_address: string; receiving_phone: string
  shipping_point_id: number; shipping_point_name: string; shipping_address: string; shipping_phone: string
}

// =============================================================================
// Bulk Progress Button
// =============================================================================
function BulkProgressButton({ logistics, expressOrders, onClose }: { logistics: Logistics; expressOrders: ExpressOrder[]; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [createdDate, setCreatedDate] = useState('')

  const statuses = expressOrders.map(o => o.status).filter((v, i, a) => a.indexOf(v) === i)
  const canProgress = statuses.length === 1 && statuses[0] !== '签收'

  const nextStatusMap: Record<string, ExpressStatus> = { 待发货: '在途', 在途: '签收' }

  const progressMutation = useMutation({
    mutationFn: () => logisticsApi.bulkProgress({
      order_ids: expressOrders.filter(o => o.status !== '签收').map(o => o.id),
      target_status: nextStatusMap[statuses[0]] || '在途',
      logistics_id: logistics.id,
      created_date: createdDate || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logistics-list'] })
      queryClient.invalidateQueries({ queryKey: ['logistics-detail', logistics.id] })
    },
  })

  if (!canProgress) return null

  const currentStatus = statuses[0]
  const targetStatus = nextStatusMap[currentStatus] || '在途'
  const nextStatusLabel: Record<string, string> = { 在途: '发货', 签收: '签收' }

  return (
    <>
      <Button size="sm" onClick={() => setConfirmOpen(true)} disabled={progressMutation.isPending}>
        批量{nextStatusLabel[nextStatusMap[currentStatus]]}
      </Button>
      <Dialog open={confirmOpen} onOpenChange={(open) => { setConfirmOpen(open); if (!open) setCreatedDate('') }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认批量{nextStatusLabel[nextStatusMap[currentStatus]]}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              将对 {expressOrders.filter(o => o.status !== '签收').length} 张快递单执行批量{nextStatusLabel[nextStatusMap[currentStatus]]}操作，状态将变更为"{targetStatus}"
            </p>
            <div className="space-y-2">
              <Label className="text-xs">业务发生日期</Label>
              <DatePicker
                value={createdDate}
                onChange={setCreatedDate}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => { setConfirmOpen(false); setCreatedDate('') }}>取消</Button>
              <Button
                disabled={progressMutation.isPending}
                onClick={() => {
                  setConfirmOpen(false)
                  setCreatedDate('')
                  onClose()
                  progressMutation.mutate()
                }}
              >
                确认
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

// =============================================================================
// Confirm Inbound Dialog
// =============================================================================
function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

async function convertImagesToPdf(files: File[], batchNo: string): Promise<File> {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  const pageWidth = doc.internal.pageSize.getWidth()
  const pageHeight = doc.internal.pageSize.getHeight()

  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    const dataUrl = await fileToDataUrl(file)
    const img = new Image()
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = reject
      img.src = dataUrl
    })
    const imgAspect = img.width / img.height
    const imgWidth = pageWidth
    const imgHeight = pageWidth / imgAspect
    if (i > 0) doc.addPage()
    doc.addImage(dataUrl, 'JPEG', 0, 0, imgWidth, imgHeight)
  }

  const pdfBlob = doc.output('blob')
  return new File([pdfBlob], `${batchNo}.pdf`, { type: 'application/pdf' })
}
function ConfirmInboundDialog({ logistics, onSuccess }: { logistics: Logistics & { vc_type?: string }; onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [snList, setSnList] = useState('')
  const [snError, setSnError] = useState('')
  const [batchItems, setBatchItems] = useState<{ sku_id: string; production_date: string; receiving_point_id: string; qty: string; certificate_files: File[] }[]>([])
  const [fileErrors, setFileErrors] = useState<Record<number, string>>({})
  const [productionDateErrors, setProductionDateErrors] = useState<Record<number, string>>({})
  const [createdDate, setCreatedDate] = useState('')

  // 生产日期校验：YYYYMMDD格式，必须合法，不能晚于今天，年份>=2026
  const validateProductionDate = (dateStr: string): string | null => {
    if (!dateStr) return null
    // 移除连字符后应为8位数字
    const digits = dateStr.replace(/-/g, '')
    if (!/^\d{8}$/.test(digits)) return '日期格式错误，应为YYYYMMDD'
    const year = parseInt(digits.substring(0, 4))
    const month = parseInt(digits.substring(4, 6))
    const day = parseInt(digits.substring(6, 8))
    // 检查年月日范围
    if (year < 2026) return '年份不能早于2026年'
    if (month < 1 || month > 12) return '月份无效'
    if (day < 1 || day > 31) return '日期无效'
    // 检查日期合法性（防止2月31日等情况）
    const d = new Date(year, month - 1, day)
    if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) return '日期不合法'
    // 不能晚于今天（即不能选今天及之后的日期）
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    if (d >= today) return '不能晚于今天'
    return null
  }

  const isMaterialProcurement = logistics.vc_type === '物料采购'
  const isMaterialSupply = logistics.vc_type === '物料供应'

  const { data: points } = useQuery({
    queryKey: ['points'],
    queryFn: () => masterApi.points.list({ size: 100 }),
    enabled: isMaterialProcurement && isOpen,
  })

  const { data: skus } = useQuery({
    queryKey: ['skus'],
    queryFn: () => masterApi.skus.list({ size: 100 }),
    enabled: isMaterialProcurement && isOpen,
  })

  const validateSnList = (input: string): string[] => {
    const sns = input.split(',').map(s => s.trim()).filter(Boolean)
    const duplicates = sns.filter((s, i) => sns.indexOf(s) !== i)
    if (duplicates.length > 0) return [`重复的序列号: ${[...new Set(duplicates)].join(', ')}`]
    return []
  }

  const confirmMutation = useMutation({
    mutationFn: () => {
      if (isMaterialProcurement) {
        // 构建 sku_id → model 映射
        const skuModelMap: Record<number, string> = {}
        ;(skus?.items || []).forEach(s => { skuModelMap[s.id] = s.model || '' })

        // 前置校验：生产日期格式和合法性
        for (const item of batchItems) {
          const err = validateProductionDate(item.production_date)
          if (err) throw new Error(err)
        }

        const validItems = batchItems.filter(i => i.sku_id)
        const batchItemsPayload = validItems.map(item => {
          const skuId = parseInt(item.sku_id)
          const model = skuModelMap[skuId] || ''
          const dateStr = item.production_date.replace(/-/g, '')
          const batchNo = model ? `${dateStr}-${model}` : `unknown_${skuId}_${dateStr}`
          return {
            sku_id: skuId,
            production_date: item.production_date,
            receiving_point_id: parseInt(item.receiving_point_id),
            qty: parseFloat(item.qty),
            certificate_filename: batchNo,
          }
        })
        // 收集所有文件打平提交
        const certFiles = validItems.flatMap(i => i.certificate_files)
        return logisticsApi.confirmInboundMaterial({
          log_id: logistics.id,
          sn_list: [],
          batch_items: batchItemsPayload,
          certificates: certFiles,
          created_date: createdDate || undefined,
        })
      } else {
        const sns = snList.split(',').map(s => s.trim()).filter(Boolean)
        return logisticsApi.confirmInbound({ log_id: logistics.id, sn_list: sns, created_date: createdDate || undefined })
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logistics-list'] })
      queryClient.invalidateQueries({ queryKey: ['logistics-detail', logistics.id] })
      setIsOpen(false)
      setSnList('')
      setSnError('')
      setBatchItems([])
      setProductionDateErrors({})
      onSuccess()
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { setIsOpen(open); if (!open) { setSnList(''); setSnError(''); setBatchItems([]); setFileErrors({}); setProductionDateErrors({}); setCreatedDate('') } }}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="text-green-600">
          <Check className="mr-2 h-4 w-4" />入库确认
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            入库确认
            {isMaterialProcurement ? '(物料采购)' : isMaterialSupply ? '(物料供应)' : '(设备/库存采购)'}
          </DialogTitle>
        </DialogHeader>

        {isMaterialSupply && (
          <div className="space-y-4">
            <div className="w-full space-y-2">
              <Label className="text-xs">入库日期</Label>
              <DatePicker value={createdDate} onChange={setCreatedDate} placeholder="选择日期" className="w-full" />
            </div>
            <div className="text-sm text-muted-foreground">物料供应无需序列号，确认后库存和财务凭证将被更新。</div>
            <div className="flex justify-end gap-2">
              <Button onClick={() => setConfirmOpen(true)} disabled={confirmMutation.isPending}>
                确认入库
              </Button>
            </div>
          </div>
        )}

        {!isMaterialProcurement && !isMaterialSupply && (
          <div className="space-y-4">
            <div className="w-full space-y-2">
              <Label className="text-xs">入库日期</Label>
              <DatePicker value={createdDate} onChange={setCreatedDate} placeholder="选择日期" className="w-full" />
            </div>
            <div className="space-y-2">
              <Label>设备序列号</Label>
              <Textarea
                placeholder="输入SN序列号，多个用逗号分隔"
                value={snList}
                onChange={(e) => { setSnList(e.target.value); setSnError(validateSnList(e.target.value)[0] || '') }}
              />
              {snError && <div className="flex items-center gap-2 text-sm text-red-600"><AlertCircle className="h-4 w-4" />{snError}</div>}
              <p className="text-sm text-muted-foreground">请输入设备序列号，每行一个或用逗号分隔</p>
            </div>
            <div className="flex justify-end gap-2">
              <Button onClick={() => setConfirmOpen(true)} disabled={!isMaterialSupply && (!snList.trim() || !!snError) || confirmMutation.isPending}>
                确认入库
              </Button>
            </div>
          </div>
        )}

        {isMaterialProcurement && (
          <div className="space-y-4">
            <div className="w-full space-y-2">
              <Label className="text-xs">入库日期</Label>
              <DatePicker value={createdDate} onChange={setCreatedDate} placeholder="选择日期" className="w-full" />
            </div>
            <div className="flex items-center justify-between">
              <Label>批次明细</Label>
              <Button type="button" size="sm" variant="outline" onClick={() => setBatchItems([...batchItems, { sku_id: '', production_date: '', receiving_point_id: '', qty: '', certificate_files: [] }])}>
                <Plus className="mr-2 h-4 w-4" />添加批次
              </Button>
            </div>
            {batchItems.map((item, idx) => (
              <Card key={idx}>
                <CardContent className="pt-4">
                  <div className="grid grid-cols-5 gap-3">
                    <div className="space-y-2">
                      <Label className="text-xs">SKU</Label>
                      <Select value={item.sku_id} onValueChange={(v) => { const u = [...batchItems]; u[idx] = { ...u[idx], sku_id: v }; setBatchItems(u) }}>
                        <SelectTrigger><SelectValue placeholder="选择SKU" /></SelectTrigger>
                        <SelectContent>
                          {skus?.items?.map(s => (<SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">生产日期</Label>
                      <DatePicker value={item.production_date} onChange={(v) => {
                        const u = [...batchItems]
                        u[idx] = { ...u[idx], production_date: v }
                        setBatchItems(u)
                        const errs = { ...productionDateErrors }
                        const err = validateProductionDate(v)
                        if (err) errs[idx] = err
                        else delete errs[idx]
                        setProductionDateErrors(errs)
                      }} />
                      {productionDateErrors[idx] && <p className="text-xs text-red-600">{productionDateErrors[idx]}</p>}
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">收货点</Label>
                      <Select value={item.receiving_point_id} onValueChange={(v) => { const u = [...batchItems]; u[idx] = { ...u[idx], receiving_point_id: v }; setBatchItems(u) }}>
                        <SelectTrigger><SelectValue placeholder="选择" /></SelectTrigger>
                        <SelectContent>
                          {points?.items?.map(p => (<SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">数量</Label>
                      <Input type="number" value={item.qty} onChange={(e) => { const u = [...batchItems]; u[idx] = { ...u[idx], qty: e.target.value }; setBatchItems(u) }} />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">质检报告</Label>
                      <Input
                        type="file"
                        accept=".pdf,.jpg,.jpeg,.png"
                        multiple
                        onChange={async (e) => {
                          const rawFiles = Array.from(e.target.files || [])
                          if (rawFiles.length === 0) {
                            const u = [...batchItems]; u[idx] = { ...u[idx], certificate_files: [] }; setBatchItems(u)
                            const errs = { ...fileErrors }; delete errs[idx]; setFileErrors(errs)
                            return
                          }
                          // 构建 batchNo
                          const skuId = parseInt(item.sku_id)
                          const sku = (skus?.items || []).find(s => s.id === skuId)
                          const model = sku?.model || ''
                          const dateStr = item.production_date.replace(/-/g, '')
                          const batchNo = model ? `${dateStr}-${model}` : `unknown_${skuId}_${dateStr}`
                          try {
                            let pdfFile: File
                            if (rawFiles.length === 1) {
                              const f = rawFiles[0]
                              if (f.type === 'application/pdf') {
                                // 单个 PDF：直接使用
                                pdfFile = f
                              } else {
                                // 单张图片：转 PDF
                                pdfFile = await convertImagesToPdf([f], batchNo)
                              }
                            } else {
                              // 多文件：必须是图片
                              const nonImage = rawFiles.find(f => !f.type.startsWith('image/'))
                              if (nonImage) {
                                const errs = { ...fileErrors, [idx]: '多文件时仅支持图片，不允许 PDF' }
                                setFileErrors(errs)
                                return
                              }
                              pdfFile = await convertImagesToPdf(rawFiles, batchNo)
                            }
                            const errs = { ...fileErrors }; delete errs[idx]; setFileErrors(errs)
                            const u = [...batchItems]; u[idx] = { ...u[idx], certificate_files: [pdfFile] }; setBatchItems(u)
                          } catch (err) {
                            console.error('PDF conversion error:', err)
                          }
                        }}
                      />
                      {fileErrors[idx] && (
                        <div className="flex items-center gap-1 text-xs text-red-600"><AlertCircle className="h-3 w-3" />{fileErrors[idx]}</div>
                      )}
                      {item.certificate_files.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {item.certificate_files.map((f, fi) => (
                            <span key={fi} className="text-xs bg-muted px-1 py-0.5 rounded truncate max-w-[120px]">{f.name}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex justify-end mt-2">
                    <Button type="button" variant="ghost" size="sm" onClick={() => setBatchItems(batchItems.filter((_, i) => i !== idx))}>
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
            {batchItems.length === 0 && <div className="text-center py-4 text-muted-foreground">点击"添加批次"添加物料批次</div>}
            <div className="flex justify-end gap-2">
              <Button onClick={() => setConfirmOpen(true)} disabled={batchItems.length === 0 || batchItems.some(i => !i.sku_id || !i.qty || !i.production_date) || Object.keys(productionDateErrors).length > 0 || confirmMutation.isPending}>
                确认入库
              </Button>
            </div>
          </div>
        )}

        <ConfirmDialog
          open={confirmOpen}
          onOpenChange={setConfirmOpen}
          title="确认入库"
          description={isMaterialProcurement
            ? `将入库 ${batchItems.length} 个物料批次，确认后库存和财务凭证将被更新，确定继续？`
            : isMaterialSupply
            ? '确认入库后库存和财务凭证将被更新，确定继续？'
            : `将入库设备 SN：${snList}，确认后库存和财务凭证将被更新，确定继续？`
          }
          confirmLabel="确认入库"
          onConfirm={() => { setConfirmOpen(false); confirmMutation.mutate() }}
          isPending={confirmMutation.isPending}
          destructive
        />
      </DialogContent>
    </Dialog>
  )
}

// =============================================================================
// Logistics Detail Dialog
// =============================================================================
function LogisticsDetailDialog({ logistics, onClose }: { logistics: Logistics; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('orders')
  const [editingOrder, setEditingOrder] = useState<ExpressOrder | null>(null)
  const [trackingNumber, setTrackingNumber] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pendingOrderId, setPendingOrderId] = useState<number | null>(null)
  const [pendingStatus, setPendingStatus] = useState<ExpressStatus | null>(null)
  const [statusChangeDate, setStatusChangeDate] = useState('')

  const { data: detail, isLoading } = useQuery({
    queryKey: ['logistics-detail', logistics.id],
    queryFn: () => logisticsApi.getDetail(logistics.id),
  })

  const updateStatusMutation = useMutation({
    mutationFn: ({ orderId, status, createdDate }: { orderId: number; status: ExpressStatus; createdDate?: string }) =>
      logisticsApi.updateExpressStatus({ order_id: orderId, target_status: status, logistics_id: logistics.id, created_date: createdDate }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logistics-detail', logistics.id] })
      queryClient.invalidateQueries({ queryKey: ['logistics-list'] })
    },
  })

  const updateTrackingMutation = useMutation({
    mutationFn: ({ orderId, tracking }: { orderId: number; tracking: string }) =>
      logisticsApi.updateExpressOrder({
        order_id: orderId, tracking_number: tracking,
        address_info: editingOrder?.address_info || { 收货点位Id: 0, 收货点位名称: '', 收货地址: '', 收货联系电话: '', 发货点位Id: 0, 发货点位名称: '', 发货地址: '', 发货联系电话: '' },
      }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['logistics-detail', logistics.id] }); setEditingOrder(null); setTrackingNumber('') },
  })

  const expressOrders = detail?.express_orders || []

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>物流任务-{logistics.id}</span>
            <Badge className={STATUS_COLORS[detail?.status || logistics.status]}>{detail?.status || logistics.status}</Badge>
          </DialogTitle>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="orders">快递单 ({expressOrders.length})</TabsTrigger>
            <TabsTrigger value="elements">合同明细</TabsTrigger>
          </TabsList>

          <TabsContent value="orders" className="space-y-4">
            {isLoading ? (<div className="text-center py-4">加载中...</div>) : expressOrders.length > 0 ? (
              <>
                <div className="flex justify-between items-center">
                  <BulkProgressButton logistics={logistics} expressOrders={expressOrders} onClose={onClose} />
                  {!isLoading && (detail?.status === '签收' || logistics.status === '签收') && (
                    <ConfirmInboundDialog
                      logistics={{ ...logistics, vc_type: detail?.vc_type }}
                      onSuccess={() => { queryClient.invalidateQueries({ queryKey: ['logistics-detail', logistics.id] }); queryClient.invalidateQueries({ queryKey: ['logistics-list'] }) }}
                    />
                  )}
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>快递单号</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>收货人</TableHead>
                      <TableHead>收货地址</TableHead>
                      <TableHead>标的</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {expressOrders.map(order => (
                      <TableRow key={order.id}>
                        <TableCell className="font-medium">
                          {editingOrder?.id === order.id ? (
                            <div className="flex gap-2">
                              <Input value={trackingNumber} onChange={(e) => setTrackingNumber(e.target.value)} className="w-40" />
                              <Button size="sm" onClick={() => updateTrackingMutation.mutate({ orderId: order.id, tracking: trackingNumber })}>保存</Button>
                            </div>
                          ) : order.tracking_number}
                        </TableCell>
                        <TableCell><Badge className={STATUS_COLORS[order.status]}>{order.status}</Badge></TableCell>
                        <TableCell>{order.address_info?.收货点位名称 || '-'}</TableCell>
                        <TableCell className="max-w-[200px] truncate">{order.address_info?.收货地址 || '-'}</TableCell>
                        <TableCell>
                          <div className="text-sm">
                            {order.items?.map((item, idx) => (<div key={idx}>{item.sku_name} x{item.qty}</div>))}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            {order.status === '待发货' && (
                              <Button variant="ghost" size="sm" onClick={() => { setEditingOrder(order); setTrackingNumber(order.tracking_number) }}>
                                编辑单号
                              </Button>
                            )}
                            {order.status === '待发货' && (
                              <Button variant="ghost" size="sm" onClick={() => { setPendingOrderId(order.id); setPendingStatus('在途'); setConfirmOpen(true) }}>
                                发货
                              </Button>
                            )}
                            {order.status === '在途' && (
                              <Button variant="ghost" size="sm" onClick={() => { setPendingOrderId(order.id); setPendingStatus('签收'); setConfirmOpen(true) }}>
                                签收
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </>
            ) : (<div className="text-center py-4 text-muted-foreground">暂无快递单</div>)}
          </TabsContent>

          <TabsContent value="elements" className="space-y-4">
            {detail?.elements && detail.elements.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>SKU</TableHead>
                    <TableHead>收货点</TableHead>
                    <TableHead className="text-right">数量</TableHead>
                    <TableHead className="text-right">单价</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detail.elements.map((el, idx) => (
                    <TableRow key={idx}>
                      <TableCell>{el.sku_name}</TableCell>
                      <TableCell>{el.receiving_point_name}</TableCell>
                      <TableCell className="text-right">{el.qty}</TableCell>
                      <TableCell className="text-right">{el.price}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (<div className="text-center py-4 text-muted-foreground">无明细数据</div>)}
          </TabsContent>
        </Tabs>

        <Dialog open={confirmOpen} onOpenChange={(open) => { setConfirmOpen(open); if (!open) { setPendingOrderId(null); setPendingStatus(null); setStatusChangeDate('') } }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>确认{pendingStatus === '在途' ? '发货' : '签收'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">快递单将变更为"{pendingStatus}"</p>
              <div className="space-y-2">
                <Label className="text-xs">业务发生日期</Label>
                <DatePicker
                  value={statusChangeDate}
                  onChange={setStatusChangeDate}
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => { setConfirmOpen(false); setPendingOrderId(null); setPendingStatus(null); setStatusChangeDate('') }}>取消</Button>
                <Button
                  disabled={updateStatusMutation.isPending}
                  onClick={() => {
                    if (pendingOrderId && pendingStatus) {
                      setConfirmOpen(false)
                      setPendingOrderId(null)
                      setPendingStatus(null)
                      setStatusChangeDate('')
                      onClose()
                      updateStatusMutation.mutate({ orderId: pendingOrderId, status: pendingStatus, createdDate: statusChangeDate || undefined })
                    }
                  }}
                >
                  确认
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </DialogContent>
    </Dialog>
  )
}

// =============================================================================
// Tab 1: 物流列表
// =============================================================================
function LogisticsListWithDetail() {
  const [statusFilter, setStatusFilter] = useState<LogisticsStatus | 'ALL' | '待处理'>('待处理')
  const [selectedLogistics, setSelectedLogistics] = useState<(Logistics & { vc_type?: string }) | null>(null)
  const [page, setPage] = useState(1)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['logistics-list', statusFilter, page],
    queryFn: () => logisticsApi.list({ status: statusFilter !== 'ALL' ? statusFilter : undefined, page, size: 20 }),
  })

  const { data: summary } = useQuery({
    queryKey: ['logistics-summary'],
    queryFn: () => logisticsApi.getDashboardSummary(),
  })

  useEffect(() => { setPage(1) }, [statusFilter])
  const totalPages = data ? Math.ceil(data.total / data.size) : 0

  return (
    <div className="space-y-4">
      {summary && (
        <div className="grid grid-cols-5 gap-4">
          <Card><CardContent className="pt-4"><div className="text-2xl font-bold">{summary.logistics_summary.total}</div><p className="text-sm text-muted-foreground">总任务</p></CardContent></Card>
          <Card><CardContent className="pt-4"><div className="text-2xl font-bold text-yellow-600">{summary.logistics_summary.pending}</div><p className="text-sm text-muted-foreground">待发货</p></CardContent></Card>
          <Card><CardContent className="pt-4"><div className="text-2xl font-bold text-blue-600">{summary.logistics_summary.transit}</div><p className="text-sm text-muted-foreground">在途</p></CardContent></Card>
          <Card><CardContent className="pt-4"><div className="text-2xl font-bold text-green-600">{summary.logistics_summary.signed}</div><p className="text-sm text-muted-foreground">已签收</p></CardContent></Card>
          <Card><CardContent className="pt-4"><div className="text-2xl font-bold text-gray-600">{summary.logistics_summary.finish}</div><p className="text-sm text-muted-foreground">已完成</p></CardContent></Card>
        </div>
      )}

      <div className="flex gap-4 flex-wrap">
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as typeof statusFilter)}>
          <SelectTrigger className="w-32"><SelectValue placeholder="状态" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="待处理">待处理</SelectItem>
            <SelectItem value="ALL">全部</SelectItem>
            <SelectItem value="待发货">待发货</SelectItem>
            <SelectItem value="在途">在途</SelectItem>
            <SelectItem value="签收">已签收</SelectItem>
            <SelectItem value="完成">已完成</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" onClick={() => refetch()}><RefreshCw className="h-4 w-4" /></Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>关联VC</TableHead>
                <TableHead>VC类型</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>快递单数量</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items?.map(log => (
                <LogisticsListRow key={log.id} log={log} onSelect={() => setSelectedLogistics(log as typeof log & { vc_type?: string })} onRefresh={() => refetch()} />
              ))}
              {!data?.items?.length && (
                <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">{isLoading ? '加载中...' : '暂无数据'}</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setPage(p => p - 1)} disabled={page <= 1}>上一页</Button>
          <span className="text-sm text-muted-foreground">第 {page} / {totalPages} 页，共 {data?.total} 条</span>
          <Button variant="outline" size="sm" onClick={() => setPage(p => p + 1)} disabled={page >= totalPages}>下一页</Button>
        </div>
      )}

      {selectedLogistics && (
        <LogisticsDetailDialog logistics={selectedLogistics} onClose={() => setSelectedLogistics(null)} />
      )}
    </div>
  )
}

function LogisticsListRow({ log, onSelect, onRefresh }: { log: Logistics; onSelect: () => void; onRefresh: () => void }) {
  const { data: detail } = useQuery({
    queryKey: ['logistics-detail', log.id],
    queryFn: () => logisticsApi.getDetail(log.id),
    enabled: true,
  })

  const hasExpressOrders = (detail?.express_orders?.length ?? 0) > 0

  return (
    <TableRow>
      <TableCell className="font-medium">LOG-{log.id}</TableCell>
      <TableCell><Badge variant="outline">VC-{log.virtual_contract_id}</Badge></TableCell>
      <TableCell>{detail?.vc_type || '-'}</TableCell>
      <TableCell><Badge className={STATUS_COLORS[log.status]}>{log.status}</Badge></TableCell>
      <TableCell>{log.express_orders_count || 0}</TableCell>
      <TableCell>{formatDate(log.created_at)}</TableCell>
      <TableCell>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={onSelect}>详情</Button>
          {(log.status === '待发货' || log.status === '在途') && hasExpressOrders && (
            <Button variant="outline" size="sm" onClick={onSelect}>
              {log.status === '待发货' ? '发货' : '批量签收'}
            </Button>
          )}
          {log.status === '签收' && <ConfirmInboundDialog logistics={{ ...log, vc_type: detail?.vc_type }} onSuccess={onRefresh} />}
        </div>
      </TableCell>
    </TableRow>
  )
}

// =============================================================================
// Tab 2: 快递单全局概览
// =============================================================================
function ExpressOrderGlobalTab() {
  const [params, setParams] = useState<ExpressOrderGlobalParams>({ page: 1, size: 20 })
  const [searchCount, setSearchCount] = useState(0)
  const [selected, setSelected] = useState<ExpressOrderGlobalItem | null>(null)

  const buildApiParams = (p: ExpressOrderGlobalParams) => {
    const numFields = ['ids', 'sku_id', 'shipping_point_id', 'receiving_point_id', 'vc_id', 'business_id', 'supply_chain_id']
    const result: Record<string, unknown> = { ...p, size: 20 }
    Object.entries(result).forEach(([k, v]) => {
      if (v === '' || v === undefined) { delete result[k]; return }
      if (numFields.includes(k) && typeof v === 'string') { result[k] = parseInt(v, 10) }
    })
    return result
  }

  const { data: results, isLoading: isSearching, error } = useQuery({
    queryKey: ['logistics-express-global', params, searchCount],
    enabled: searchCount > 0,
    queryFn: () => logisticsApi.getExpressOrdersGlobal(buildApiParams(params)),
  })

  const doSearch = () => { setSelected(null); setSearchCount(c => c + 1) }

  const clearSearch = () => {
    setParams({ page: 1, size: 20 })
    setSelected(null)
  }

  const setParam = (key: keyof ExpressOrderGlobalParams, value: string) => {
    setParams(p => ({ ...p, [key]: value || undefined }))
  }

  const totalPages = results ? Math.ceil(results.total / results.size) : 0

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-base">多条件搜索</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <div className="space-y-1"><Label className="text-xs">快递单号</Label><Input value={params.tracking_number || ''} onChange={e => setParam('tracking_number', e.target.value)} placeholder="模糊匹配" /></div>
            <div className="space-y-1"><Label className="text-xs">快递单ID</Label><Input type="number" value={params.ids || ''} onChange={e => setParam('ids', e.target.value)} placeholder="ID" /></div>
            <div className="space-y-1"><Label className="text-xs">快递单状态</Label>
              <Select value={params.status || 'ALL'} onValueChange={v => setParam('status', v === 'ALL' ? '' : v)}>
                <SelectTrigger><SelectValue placeholder="全部" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">全部</SelectItem>
                  <SelectItem value="待发货">待发货</SelectItem>
                  <SelectItem value="在途">在途</SelectItem>
                  <SelectItem value="签收">签收</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1"><Label className="text-xs">创建时间起</Label><DatePicker value={params.date_from || ''} onChange={v => setParam('date_from', v)} /></div>
            <div className="space-y-1"><Label className="text-xs">创建时间止</Label><DatePicker value={params.date_to || ''} onChange={v => setParam('date_to', v)} /></div>
            <div className="space-y-1"><Label className="text-xs">SKU ID</Label><Input type="number" value={params.sku_id || ''} onChange={e => setParam('sku_id', e.target.value)} placeholder="SKU ID" /></div>
            <div className="space-y-1"><Label className="text-xs">SKU名称</Label><Input value={params.sku_name_kw || ''} onChange={e => setParam('sku_name_kw', e.target.value)} placeholder="精确包含" /></div>
            <div className="space-y-1"><Label className="text-xs">发货点位ID</Label><Input type="number" value={params.shipping_point_id || ''} onChange={e => setParam('shipping_point_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">发货点位名称</Label><Input value={params.shipping_point_name_kw || ''} onChange={e => setParam('shipping_point_name_kw', e.target.value)} placeholder="精确包含" /></div>
            <div className="space-y-1"><Label className="text-xs">收货点位ID</Label><Input type="number" value={params.receiving_point_id || ''} onChange={e => setParam('receiving_point_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">收货点位名称</Label><Input value={params.receiving_point_name_kw || ''} onChange={e => setParam('receiving_point_name_kw', e.target.value)} placeholder="精确包含" /></div>
            <div className="space-y-1"><Label className="text-xs">关联VC ID</Label><Input type="number" value={params.vc_id || ''} onChange={e => setParam('vc_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">关联VC类型</Label>
              <Select value={params.vc_type || 'ALL'} onValueChange={v => setParam('vc_type', v === 'ALL' ? '' : v)}>
                <SelectTrigger><SelectValue placeholder="全部" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">全部</SelectItem>
                  <SelectItem value="设备采购">设备采购</SelectItem>
                  <SelectItem value="物料供应">物料供应</SelectItem>
                  <SelectItem value="物料采购">物料采购</SelectItem>
                  <SelectItem value="库存拨付">库存拨付</SelectItem>
                  <SelectItem value="退货">退货</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1"><Label className="text-xs">关联VC状态</Label>
              <Select
                value={(params.vc_status_type && params.vc_status_value) ? `${params.vc_status_type}-${params.vc_status_value}` : 'ALL'}
                onValueChange={v => {
                  if (v === 'ALL') {
                    setParams((p: any) => ({ ...p, vc_status_type: undefined, vc_status_value: undefined }))
                  } else {
                    const [type, val] = v.split('-')
                    setParams((p: any) => ({ ...p, vc_status_type: type, vc_status_value: val }))
                  }
                }}
              >
                <SelectTrigger><SelectValue placeholder="全部" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">全部</SelectItem>
                  <SelectItem value="主状态-执行">主状态-执行</SelectItem>
                  <SelectItem value="主状态-完成">主状态-完成</SelectItem>
                  <SelectItem value="主状态-终止">主状态-终止</SelectItem>
                  <SelectItem value="主状态-取消">主状态-取消</SelectItem>
                  <SelectItem value="合同状态-执行">合同状态-执行</SelectItem>
                  <SelectItem value="合同状态-发货">合同状态-发货</SelectItem>
                  <SelectItem value="合同状态-签收">合同状态-签收</SelectItem>
                  <SelectItem value="合同状态-完成">合同状态-完成</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1"><Label className="text-xs">Business ID</Label><Input type="number" value={params.business_id || ''} onChange={e => setParam('business_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">客户名称</Label><Input value={params.business_customer_name_kw || ''} onChange={e => setParam('business_customer_name_kw', e.target.value)} placeholder="精确包含" /></div>
            <div className="space-y-1"><Label className="text-xs">SupplyChain ID</Label><Input type="number" value={params.supply_chain_id || ''} onChange={e => setParam('supply_chain_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">供应商名称</Label><Input value={params.supply_chain_supplier_name_kw || ''} onChange={e => setParam('supply_chain_supplier_name_kw', e.target.value)} placeholder="精确包含" /></div>
          </div>
          <div className="flex gap-2 ml-auto">
            <Button variant="outline" onClick={clearSearch}>清空</Button>
            <Button onClick={doSearch} disabled={isSearching}>{isSearching ? '搜索中...' : '搜索'}</Button>
          </div>
          {error && <div className="text-sm text-red-600">{error.message}</div>}
        </CardContent>
      </Card>

      {error && !results && (
        <Card><CardContent className="py-4 text-center text-red-600">{typeof error === 'string' ? error : '加载失败'}</CardContent></Card>
      )}

      {results && (
        <>
          <div className="text-sm text-muted-foreground">共 {results.total} 条记录</div>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>快递单号</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead>SKU</TableHead>
                    <TableHead>发货点位</TableHead>
                    <TableHead>收货点位</TableHead>
                    <TableHead>物流单ID</TableHead>
                    <TableHead>VC ID</TableHead>
                    <TableHead>VC类型</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.items?.map(order => (
                    <TableRow key={order.id} className={selected?.id === order.id ? 'bg-muted' : ''} onClick={() => setSelected(order)}>
                      <TableCell className="font-medium">{order.tracking_number}</TableCell>
                      <TableCell><Badge className={STATUS_COLORS[order.status]}>{order.status}</Badge></TableCell>
                      <TableCell>{formatDate(order.created_at)}</TableCell>
                      <TableCell>{order.items?.map((item, idx) => (<div key={idx}>{item.sku_name} x{item.qty}</div>))}</TableCell>
                      <TableCell>{order.address_info?.发货点位名称 || '-'}</TableCell>
                      <TableCell>{order.address_info?.收货点位名称 || '-'}</TableCell>
                      <TableCell>LOG-{order.logistics_id}</TableCell>
                      <TableCell>{order.vc_id ? `VC-${order.vc_id}` : '-'}</TableCell>
                      <TableCell>{order.vc_type || '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setParams(p => ({ ...p, page: (p.page || 1) - 1 }))} disabled={(params.page || 1) <= 1}>上一页</Button>
              <span className="text-sm text-muted-foreground">第 {params.page} / {totalPages} 页</span>
              <Button variant="outline" size="sm" onClick={() => setParams(p => ({ ...p, page: (p.page || 1) + 1 }))} disabled={(params.page || 1) >= totalPages}>下一页</Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// =============================================================================
// Tab 3: 物流全局概览
// =============================================================================
function LogisticsGlobalTab() {
  const [params, setParams] = useState<LogisticsGlobalParams>({ page: 1, size: 20 })
  const [searchCount, setSearchCount] = useState(0)
  const [selected, setSelected] = useState<LogisticsGlobalItem | null>(null)
  const [detailLogistics, setDetailLogistics] = useState<(Logistics & { vc_type?: string }) | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const buildApiParams = (p: LogisticsGlobalParams) => {
    const numFields = ['ids', 'sku_id', 'shipping_point_id', 'receiving_point_id', 'vc_id', 'business_id', 'supply_chain_id', 'express_order_id']
    const result: Record<string, unknown> = { ...p, size: 20 }
    Object.entries(result).forEach(([k, v]) => {
      if (v === '' || v === undefined) { delete result[k]; return }
      if (numFields.includes(k) && typeof v === 'string') { result[k] = parseInt(v, 10) }
    })
    return result
  }

  const { data: results, isLoading: isSearching, error } = useQuery({
    queryKey: ['logistics-global', params, searchCount],
    enabled: searchCount > 0,
    queryFn: () => logisticsApi.getLogisticsGlobal(buildApiParams(params)),
  })

  const doSearch = () => { setSelected(null); setSearchCount(c => c + 1) }

  const clearSearch = () => {
    setParams({ page: 1, size: 20 })
    setSelected(null)
  }

  const setParam = (key: keyof LogisticsGlobalParams, value: string) => {
    setParams(p => ({ ...p, [key]: value || undefined }))
  }

  const totalPages = results ? Math.ceil(results.total / results.size) : 0

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-base">多条件搜索</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <div className="space-y-1"><Label className="text-xs">物流单ID</Label><Input type="number" value={params.ids || ''} onChange={e => setParam('ids', e.target.value)} placeholder="ID" /></div>
            <div className="space-y-1"><Label className="text-xs">物流单状态</Label>
              <Select value={params.status || 'ALL'} onValueChange={v => setParam('status', v === 'ALL' ? '' : v)}>
                <SelectTrigger><SelectValue placeholder="全部" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">全部</SelectItem>
                  <SelectItem value="待发货">待发货</SelectItem>
                  <SelectItem value="在途">在途</SelectItem>
                  <SelectItem value="签收">已签收</SelectItem>
                  <SelectItem value="完成">已完成</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1"><Label className="text-xs">创建时间起</Label><DatePicker value={params.date_from || ''} onChange={v => setParam('date_from', v)} /></div>
            <div className="space-y-1"><Label className="text-xs">创建时间止</Label><DatePicker value={params.date_to || ''} onChange={v => setParam('date_to', v)} /></div>
            <div className="space-y-1"><Label className="text-xs">快递单号</Label><Input value={params.tracking_number || ''} onChange={e => setParam('tracking_number', e.target.value)} placeholder="模糊匹配" /></div>
            <div className="space-y-1"><Label className="text-xs">快递单ID</Label><Input type="number" value={params.express_order_id || ''} onChange={e => setParam('express_order_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">SKU ID</Label><Input type="number" value={params.sku_id || ''} onChange={e => setParam('sku_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">SKU名称</Label><Input value={params.sku_name_kw || ''} onChange={e => setParam('sku_name_kw', e.target.value)} placeholder="精确包含" /></div>
            <div className="space-y-1"><Label className="text-xs">发货点位ID</Label><Input type="number" value={params.shipping_point_id || ''} onChange={e => setParam('shipping_point_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">发货点位名称</Label><Input value={params.shipping_point_name_kw || ''} onChange={e => setParam('shipping_point_name_kw', e.target.value)} placeholder="精确包含" /></div>
            <div className="space-y-1"><Label className="text-xs">收货点位ID</Label><Input type="number" value={params.receiving_point_id || ''} onChange={e => setParam('receiving_point_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">收货点位名称</Label><Input value={params.receiving_point_name_kw || ''} onChange={e => setParam('receiving_point_name_kw', e.target.value)} placeholder="精确包含" /></div>
            <div className="space-y-1"><Label className="text-xs">关联VC ID</Label><Input type="number" value={params.vc_id || ''} onChange={e => setParam('vc_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">关联VC类型</Label>
              <Select value={params.vc_type || 'ALL'} onValueChange={v => setParam('vc_type', v === 'ALL' ? '' : v)}>
                <SelectTrigger><SelectValue placeholder="全部" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">全部</SelectItem>
                  <SelectItem value="设备采购">设备采购</SelectItem>
                  <SelectItem value="物料供应">物料供应</SelectItem>
                  <SelectItem value="物料采购">物料采购</SelectItem>
                  <SelectItem value="库存拨付">库存拨付</SelectItem>
                  <SelectItem value="退货">退货</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1"><Label className="text-xs">关联VC状态</Label>
              <Select
                value={(params.vc_status_type && params.vc_status_value) ? `${params.vc_status_type}-${params.vc_status_value}` : 'ALL'}
                onValueChange={v => {
                  if (v === 'ALL') {
                    setParams((p: any) => ({ ...p, vc_status_type: undefined, vc_status_value: undefined }))
                  } else {
                    const [type, val] = v.split('-')
                    setParams((p: any) => ({ ...p, vc_status_type: type, vc_status_value: val }))
                  }
                }}
              >
                <SelectTrigger><SelectValue placeholder="全部" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">全部</SelectItem>
                  <SelectItem value="主状态-执行">主状态-执行</SelectItem>
                  <SelectItem value="主状态-完成">主状态-完成</SelectItem>
                  <SelectItem value="主状态-终止">主状态-终止</SelectItem>
                  <SelectItem value="主状态-取消">主状态-取消</SelectItem>
                  <SelectItem value="合同状态-执行">合同状态-执行</SelectItem>
                  <SelectItem value="合同状态-发货">合同状态-发货</SelectItem>
                  <SelectItem value="合同状态-签收">合同状态-签收</SelectItem>
                  <SelectItem value="合同状态-完成">合同状态-完成</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1"><Label className="text-xs">Business ID</Label><Input type="number" value={params.business_id || ''} onChange={e => setParam('business_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">客户名称</Label><Input value={params.business_customer_name_kw || ''} onChange={e => setParam('business_customer_name_kw', e.target.value)} placeholder="精确包含" /></div>
            <div className="space-y-1"><Label className="text-xs">SupplyChain ID</Label><Input type="number" value={params.supply_chain_id || ''} onChange={e => setParam('supply_chain_id', e.target.value)} /></div>
            <div className="space-y-1"><Label className="text-xs">供应商名称</Label><Input value={params.supply_chain_supplier_name_kw || ''} onChange={e => setParam('supply_chain_supplier_name_kw', e.target.value)} placeholder="精确包含" /></div>
          </div>
          <div className="flex gap-2 ml-auto">
            <Button variant="outline" onClick={clearSearch}>清空</Button>
            <Button onClick={doSearch} disabled={isSearching}>{isSearching ? '搜索中...' : '搜索'}</Button>
          </div>
          {error && <div className="text-sm text-red-600">{error.message}</div>}
        </CardContent>
      </Card>

      {error && !results && (
        <Card><CardContent className="py-4 text-center text-red-600">{typeof error === 'string' ? error : '加载失败'}</CardContent></Card>
      )}

      {results && (
        <>
          <div className="text-sm text-muted-foreground">共 {results.total} 条记录</div>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>关联VC</TableHead>
                    <TableHead>VC类型</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>快递单数量</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.items?.map(item => (
                    <TableRow key={item.id} className={selected?.id === item.id ? 'bg-muted' : ''}>
                      <TableCell className="font-medium">LOG-{item.id}</TableCell>
                      <TableCell><Badge variant="outline">VC-{item.virtual_contract_id}</Badge></TableCell>
                      <TableCell>{item.vc_type || '-'}</TableCell>
                      <TableCell><Badge className={STATUS_COLORS[item.status]}>{item.status}</Badge></TableCell>
                      <TableCell>{item.express_orders_count}</TableCell>
                      <TableCell>{formatDate(item.created_at)}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm" onClick={() => { setDetailLoading(true); logisticsApi.getDetail(item.id).then(d => { setDetailLogistics(d as Logistics & { vc_type?: string }); setDetailLoading(false) }).catch(() => setDetailLoading(false)) }} disabled={detailLoading}>
                          {detailLoading ? '...' : '详情'}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setParams(p => ({ ...p, page: (p.page || 1) - 1 }))} disabled={(params.page || 1) <= 1}>上一页</Button>
              <span className="text-sm text-muted-foreground">第 {params.page} / {totalPages} 页</span>
              <Button variant="outline" size="sm" onClick={() => setParams(p => ({ ...p, page: (p.page || 1) + 1 }))} disabled={(params.page || 1) >= totalPages}>下一页</Button>
            </div>
          )}
        </>
      )}

      {detailLogistics && (
        <LogisticsDetailDialog logistics={detailLogistics} onClose={() => setDetailLogistics(null)} />
      )}
    </div>
  )
}

// =============================================================================
// Main Logistics Page
// =============================================================================
export function LogisticsPage() {
  const [activeTab, setActiveTab] = useState<'list' | 'express-global' | 'logistics-global'>('list')

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">物流管理</h2>
        <CreateLogisticsDialog onSuccess={() => {}} />
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
        <TabsList>
          <TabsTrigger value="list">物流列表</TabsTrigger>
          <TabsTrigger value="express-global">快递单全局概览</TabsTrigger>
          <TabsTrigger value="logistics-global">物流全局概览</TabsTrigger>
        </TabsList>

        <TabsContent value="list"><LogisticsListWithDetail /></TabsContent>
        <TabsContent value="express-global"><ExpressOrderGlobalTab /></TabsContent>
        <TabsContent value="logistics-global"><LogisticsGlobalTab /></TabsContent>
      </Tabs>
    </div>
  )
}
