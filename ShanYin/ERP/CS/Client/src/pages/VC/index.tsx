import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, X, ChevronRight, Package, Truck, RotateCcw, RefreshCw, Pencil, Trash2, Download } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { DatePicker } from '@/components/ui/date-picker'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { PointSelect, PointOption } from '@/components/ui/point-select'
import { vcApi, VCType, VCStatus, VirtualContract, VCDetailResponse, CashflowProgress, VCListResponse, VCGlobalSearchParams } from '@/api/endpoints/vc'
import { businessApi } from '@/api/endpoints/business'
import { masterApi, Point, SKU } from '@/api/endpoints/master'
import { supplyChainApi } from '@/api/endpoints/supplyChain'
import { inventoryApi, MaterialBatch } from '@/api/endpoints/inventory'
import { formatCurrency, formatDate, exportToExcel } from '@/lib/utils'

const VC_TYPE_LABELS: Record<string, string> = {
  设备采购: '设备采购',
  库存采购: '库存采购',
  物料采购: '物料采购',
  物料供应: '物料供应',
  库存拨付: '库存拨付',
  退货: '退货',
}

const VC_TYPE_COLORS: Record<string, string> = {
  设备采购: 'bg-blue-100 text-blue-800',
  库存采购: 'bg-indigo-100 text-indigo-800',
  物料供应: 'bg-green-100 text-green-800',
  物料采购: 'bg-orange-100 text-orange-800',
  库存拨付: 'bg-purple-100 text-purple-800',
  退货: 'bg-red-100 text-red-800',
}

const STATUS_COLORS: Record<string, string> = {
  // 通用状态
  执行: 'bg-blue-100 text-blue-800',   // 进行中 - 蓝色
  完成: 'bg-green-100 text-green-800', // 完成 - 绿色
  终止: 'bg-red-100 text-red-800',     // 终止 - 红色
  取消: 'bg-gray-100 text-gray-800',    // 取消 - 灰色
  // 主体状态
  发货: 'bg-orange-100 text-orange-800', // 发货 - 橙色
  签收: 'bg-teal-100 text-teal-800',     // 签收 - 青色
  // 资金状态
  预付: 'bg-yellow-100 text-yellow-800',  // 预付 - 黄色
}

type ElementFormState = {
  sku_id: string
  batch_inventory_id: string   // material_inventory.id（物料供应用）
  warehouse_point_id: string   // 发货仓库（物料供应时从批次自动填充）
  batch_no: string            // 批次号（物料供应用）
  shipping_point_id: string   // 发货点（供应链类型用）
  receiving_point_id: string
  qty: string
  price: string
  deposit: string
  sn_list: string
  qty_error?: string   // 超库存错误提示
}

function VCCreateDialog({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)
  const [selectedType, setSelectedType] = useState<VCType | null>(null)
  const [formData, setFormData] = useState({
    business_id: '',
    sc_id: '',
    description: '',
    total_amt: '',
    total_deposit: '',
    prepayment_ratio: '0.3',
    balance_period: '30',
    day_rule: '自然日',
    start_trigger: '入库日',
  })
  const [elements, setElements] = useState<ElementFormState[]>([])
  // 选中供应链后，该供应链约定的 SKU 列表（用于物料采购时过滤 SKU）
  const [scSkuIds, setScSkuIds] = useState<number[]>([])
  // 选中供应链后，默认发货仓库（供应商的仓，id 最小的）
  const [defaultShippingPointId, setDefaultShippingPointId] = useState<string>('')
  // 物料供应时，每个 element 的可用批次（key = element index）
  const [materialBatchesMap, setMaterialBatchesMap] = useState<Record<number, MaterialBatch[]>>({})
  const [returnFormData, setReturnFormData] = useState({
    target_vc_id: '',
    return_direction: 'CUSTOMER_TO_US',
    receiving_point_id: '',
    goods_amount: '',
    deposit_amount: '',
    logistics_cost: '',
    logistics_bearer: 'SENDER',
    total_refund: '',
    reason: '',
    description: '',
  })
  const [returnElements, setReturnElements] = useState<{
    original_element_id: string
    sku_id: string
    qty: string
    sn_list: string
  }[]>([])
  const [createdDate, setCreatedDate] = useState('')
  // 业务SKU协议价格表（物料供应/库存拨付时使用）：来自 details.pricing + NEW_SKU addon，addon 价格优先
  const { data: skuPriceTable, isLoading: skuPriceTableLoading } = useQuery({
    queryKey: ['business-sku-price-table', formData.business_id, selectedType],
    queryFn: () => businessApi.getSkuPriceTable(parseInt(formData.business_id), selectedType === '设备采购'),
    enabled: !!formData.business_id && (selectedType === '物料供应' || selectedType === '库存拨付' || selectedType === '设备采购'),
  })
  // 有库存的物料 SKU 列表（用于物料供应 VC 过滤 SKU 下拉）
  const { data: materialSkusWithStock } = useQuery({
    queryKey: ['material-skus-with-stock'],
    queryFn: () => inventoryApi.getMaterialSkusWithStock(),
  })

  // 当 skuPriceTable 加载完成后，自动填充押金（针对已选SKU但无押金的情况）
  useEffect(() => {
    if (!skuPriceTable || elements.length === 0) return
    if (selectedType !== '设备采购' && selectedType !== '物料供应' && selectedType !== '库存拨付') return
    console.log('[DEBUG] useEffect skuPriceTable loaded:', { selectedType, elements, skuPriceTable })
    let changed = false
    const updated = elements.map(el => {
      if (el.sku_id && !el.deposit) {
        const tableItem = skuPriceTable.find(item => item.sku_id === parseInt(el.sku_id))
        console.log('[DEBUG] useEffect matching:', { skuId: el.sku_id, tableItem })
        if (tableItem && tableItem.deposit > 0) {
          changed = true
          return { ...el, deposit: String(tableItem.deposit) }
        }
      }
      return el
    })
    if (changed) {
      setElements(updated)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skuPriceTable, selectedType])

  const { data: businesses } = useQuery({
    queryKey: ['businesses-for-vc'],
    queryFn: async () => {
      try {
        return await businessApi.list({ status: '业务开展', size: 100 })
      } catch (err) {
        // 认证失败时降级：用 masterApi.customers.list（返回 Customer[]，需要映射为 Business 格式）
        const customers = await masterApi.customers.list({ size: 100 })
        return {
          items: customers.items.map(c => ({ id: c.id, customer_id: c.id, status: '业务开展', customer_name: c.name, details: {} })),
          total: customers.total,
          page: customers.page,
          size: customers.size,
        }
      }
    },
  })

  const { data: supplyChains } = useQuery({
    queryKey: ['supply-chains-for-vc'],
    queryFn: () => supplyChainApi.list({ size: 100 }),
  })

  const { data: points } = useQuery({
    queryKey: ['points-for-vc'],
    queryFn: () => masterApi.points.list({ size: 100 }),
  })

  // 当前业务关联客户的点位列表（用于物料供应收货点过滤）
  const customerPoints = (() => {
    if (!formData.business_id || !businesses?.items || !points?.items) return []
    const biz = businesses.items.find(b => String(b.id) === String(formData.business_id))
    if (!biz?.customer_id) return points.items
    return points.items.filter((p: Point) => String(p.customer_id) === String(biz.customer_id))
  })()

  // 物料采购：供应链供应商的点位列表
  const supplierPoints = (() => {
    if (!formData.sc_id || !supplyChains?.items || !points?.items) return []
    const sc = supplyChains.items.find(s => String(s.id) === String(formData.sc_id))
    if (!sc?.supplier_id) return []
    return points.items.filter((p: Point) => String(p.supplier_id) === String(sc.supplier_id))
  })()

  // 当 supplierPoints 加载出来后，同步更新已有元素的发货点位
  useEffect(() => {
    if (!formData.sc_id || !supplierPoints.length) return
    const validIds = new Set(supplierPoints.map(p => String(p.id)))
    setElements(prev => prev.map(el => {
      if (el.shipping_point_id && validIds.has(el.shipping_point_id)) return el
      // 如果当前值不在有效列表中，或为空，则用第一个供应商仓
      return { ...el, shipping_point_id: String(supplierPoints[0].id) }
    }))
  }, [supplierPoints])

  // 物料采购/设备采购：有效的收货仓库（客户所有点位 + 我们所有点位 + 供应商所有点位）
  const matOrEquipProcurementReceivingPoints = (() => {
    if ((selectedType !== '物料采购' && selectedType !== '设备采购') || !points?.items) return []
    const sc = supplyChains?.items?.find(s => String(s.id) === String(formData.sc_id))
    const ourPoints = points.items.filter((p: Point) => !p.supplier_id && !p.customer_id)
    const supWh = sc?.supplier_id ? points.items.filter((p: Point) => String(p.supplier_id) === String(sc.supplier_id)) : []
    return [...customerPoints, ...ourPoints, ...supWh]
  })()

  // 库存采购：有效的收货仓库（我们所有点位 + 供应商所有点位）
  const stockProcurementReceivingPoints = (() => {
    if (selectedType !== '库存采购' || !points?.items) return []
    const sc = supplyChains?.items?.find(s => String(s.id) === String(formData.sc_id))
    const ourPoints = points.items.filter((p: Point) => !p.supplier_id && !p.customer_id)
    const supWh = sc?.supplier_id ? points.items.filter((p: Point) => String(p.supplier_id) === String(sc.supplier_id)) : []
    return [...ourPoints, ...supWh]
  })()


  const { data: skus } = useQuery({
    queryKey: ['skus-for-vc'],
    queryFn: () => masterApi.skus.list({ size: 100 }),
  })

  const { data: vcsForReturn } = useQuery({
    queryKey: ['vcs-for-return'],
    queryFn: () => vcApi.getReturnable({ status: '执行', subject_status: '完成,签收' }),
  })

  // 退货收货点：CUSTOMER_TO_US=我方仓库；US_TO_SUPPLIER=目标VC的供应商仓库
  const returnReceivingPoints = (() => {
    if (!points?.items) return []
    if (returnFormData.return_direction === 'CUSTOMER_TO_US') {
      return points.items.filter((p: Point) => !p.owner_type)
    } else {
      if (!returnFormData.target_vc_id) return []
      const targetVc = vcsForReturn?.items?.find(v => String(v.id) === String(returnFormData.target_vc_id))
      const sc = supplyChains?.items?.find(s => String(s.id) === String(targetVc?.supply_chain_id))
      if (!sc?.supplier_id) return points.items.filter((p: Point) => p.supplier_id)
      return points.items.filter((p: Point) => p.supplier_id === sc.supplier_id)
    }
  })()

  const createMutation = useMutation({
    mutationFn: async () => {
      const totalDeposit = elements.reduce((sum, el) => sum + (parseFloat(el.deposit) || 0), 0)
      const payment = {
        prepayment_ratio: parseFloat(formData.prepayment_ratio) || 0,
        balance_period: parseInt(formData.balance_period) || 30,
        day_rule: formData.day_rule,
        start_trigger: formData.start_trigger,
      }

      const vcElements = elements.map(el => ({
        shipping_point_id: parseInt(el.warehouse_point_id) || parseInt(el.shipping_point_id) || 0,
        receiving_point_id: parseInt(el.receiving_point_id) || 0,
        sku_id: parseInt(el.sku_id),
        batch_no: el.batch_no || undefined,
        qty: parseFloat(el.qty) || 0,
        price: parseFloat(el.price) || 0,
        deposit: parseFloat(el.deposit) || 0,
        subtotal: (parseFloat(el.qty) || 0) * (parseFloat(el.price) || 0),
        sn_list: el.sn_list ? el.sn_list.split(',').map(s => s.trim()).filter(Boolean) : undefined,
      }))

      switch (selectedType) {
        case '设备采购':
          return vcApi.createProcurement({
            business_id: parseInt(formData.business_id),
            sc_id: formData.sc_id ? parseInt(formData.sc_id) : undefined,
            elements: vcElements,
            total_amt: totalAmount,
            total_deposit: totalDeposit,
            payment,
            description: formData.description,
            created_date: createdDate || undefined,
          })
        case '库存采购':
          return vcApi.createStockProcurement({
            sc_id: parseInt(formData.sc_id),
            elements: vcElements,
            total_amt: totalAmount,
            payment,
            description: formData.description,
            created_date: createdDate || undefined,
          })
        case '物料供应':
          return vcApi.createMaterialSupply({
            business_id: parseInt(formData.business_id),
            elements: vcElements,
            total_amt: totalAmount,
            description: formData.description,
            created_date: createdDate || undefined,
          })
        case '物料采购':
          return vcApi.createMatProcurement({
            sc_id: parseInt(formData.sc_id),
            elements: vcElements,
            total_amt: totalAmount,
            payment,
            description: formData.description,
            created_date: createdDate || undefined,
          })
        case '库存拨付':
          return vcApi.allocateInventory({
            business_id: parseInt(formData.business_id),
            elements: vcElements.map(el => ({
              ...el,
              deposit: 0,
            })),
            description: formData.description,
            created_date: createdDate || undefined,
          })
        case '退货':
          return vcApi.createReturn({
            target_vc_id: parseInt(returnFormData.target_vc_id),
            return_direction: returnFormData.return_direction as 'CUSTOMER_TO_US' | 'US_TO_SUPPLIER',
            receiving_point_id: parseInt(returnFormData.receiving_point_id) || 0,
            elements: returnElements.map(el => ({
              shipping_point_id: 0,
              receiving_point_id: parseInt(returnFormData.receiving_point_id) || 0,
              sku_id: parseInt(el.sku_id),
              qty: parseFloat(el.qty),
              price: 0,
              deposit: 0,
              subtotal: 0,
              sn_list: el.sn_list ? el.sn_list.split(',').map(s => s.trim()).filter(Boolean) : [],
            })),
            goods_amount: parseFloat(returnFormData.goods_amount) || 0,
            deposit_amount: parseFloat(returnFormData.deposit_amount) || 0,
            logistics_cost: parseFloat(returnFormData.logistics_cost) || 0,
            logistics_bearer: returnFormData.logistics_bearer,
            total_refund: parseFloat(returnFormData.total_refund) || 0,
            reason: returnFormData.reason,
            description: returnFormData.description,
            created_date: createdDate || undefined,
          })
        default:
          throw new Error('Unsupported VC type')
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vc-list'] })
      setIsOpen(false)
      setSelectedType(null)
      onSuccess()
    },
    onError: (err: Error) => {
      alert('创建失败: ' + err.message)
    },
  })

  const addElement = () => {
    const isSupplyChainType = formData.sc_id && (selectedType === '设备采购' || selectedType === '库存采购' || selectedType === '物料采购')
    const defaultPoint = supplierPoints.length > 0 ? String(supplierPoints[0].id) : ''
    setElements([...elements, {
      sku_id: '', batch_inventory_id: '', warehouse_point_id: '',
      batch_no: '',
      shipping_point_id: isSupplyChainType ? defaultPoint : '',
      receiving_point_id: '', qty: '', price: '', deposit: '', sn_list: ''
    }])
  }

  const updateElement = (index: number, field: keyof ElementFormState, value: string) => {
    const updated = [...elements]
    updated[index] = { ...updated[index], [field]: value }

    // 物料供应：选择 SKU 后清空批次相关字段，并拉取可用批次
    if (field === 'sku_id' && !formData.sc_id && (selectedType === '物料供应' || selectedType === '库存拨付')) {
      updated[index].batch_inventory_id = ''
      updated[index].warehouse_point_id = ''
      updated[index].batch_no = ''
      updated[index].price = ''
      // 清空该 index 的批次缓存
      const newMap = { ...materialBatchesMap }
      delete newMap[index]
      setMaterialBatchesMap(newMap)
      // 拉取新 SKU 的批次
      if (value) {
        inventoryApi.getMaterialBatches(parseInt(value)).then(batches => {
          setMaterialBatchesMap(prev => ({ ...prev, [index]: batches }))
        }).catch(() => {})
      }
    }

    // 设备采购/库存采购：选择 SKU 后，自动填充供应商仓库（单仓锁定，多仓预选第一个）
    if (field === 'sku_id' && formData.sc_id && (selectedType === '设备采购' || selectedType === '库存采购')) {
      if (supplierPoints.length > 0) {
        updated[index].shipping_point_id = String(supplierPoints[0].id)
      }
    }

    // 物料供应：选择批次后自动填充发货点、批次号
    if (field === 'batch_inventory_id' && !formData.sc_id && selectedType === '物料供应') {
      const batches = materialBatchesMap[index] || []
      const batch = batches.find(b => b.inventory_id === parseInt(value))
      if (batch) {
        updated[index].warehouse_point_id = String(batch.warehouse_point_id)
        updated[index].batch_no = batch.batch_no
      }
      // 校验当前数量是否超过批次库存
      const curQty = parseFloat(updated[index].qty) || 0
      const curBatch = batches.find(b => b.inventory_id === parseInt(value))
      if (curQty > 0 && curBatch && curQty > curBatch.quantity) {
        updated[index].qty_error = `不能超过批次库存 (${curBatch.quantity}件)`
      } else {
        updated[index].qty_error = undefined
      }
    }

    // 物料供应：精确批次维度聚合校验
    // 同 batch_inventory_id（即同一 material_inventory 记录）的所有 element 合计不能超过该批次库存
    if (!formData.sc_id && selectedType === '物料供应') {
      // 先清除所有 qty_error
      for (let i = 0; i < updated.length; i++) {
        updated[i].qty_error = undefined
      }
      // 按 batch_inventory_id 聚合
      type BatchGroup = { total: number; indices: number[]; batchQuantity: number }
      const batchQtyMap: Record<string, BatchGroup> = {}
      for (let i = 0; i < updated.length; i++) {
        const el = updated[i]
        const bid = el.batch_inventory_id
        if (!bid) continue
        if (!batchQtyMap[bid]) {
          batchQtyMap[bid] = { total: 0, indices: [], batchQuantity: 0 }
          // 从任意一个拥有该 batch 的 element 处获取批次库存量
          for (let j = 0; j < updated.length; j++) {
            const batches = materialBatchesMap[j] || []
            const batch = batches.find(b => String(b.inventory_id) === bid)
            if (batch) {
              batchQtyMap[bid].batchQuantity = batch.quantity
              break
            }
          }
        }
        batchQtyMap[bid].total += parseFloat(el.qty) || 0
        batchQtyMap[bid].indices.push(i)
      }
      // 检查每个批次的合计是否超量
      for (const info of Object.values(batchQtyMap)) {
        if (info.batchQuantity <= 0) continue
        if (info.total > info.batchQuantity) {
          for (const i of info.indices) {
            updated[i].qty_error = `合计${info.total}超库存${info.batchQuantity}`
          }
        }
      }
    }

    // Auto-fill price from supply chain when SKU is selected (for 物料采购/设备采购)
    if (field === 'sku_id' && formData.sc_id) {
      const sc = supplyChains?.items?.find(s => s.id === parseInt(formData.sc_id))
      const skuItem = sc?.items?.find((i: any) => i.sku_id === parseInt(value))
      if (skuItem?.price !== undefined) {
        updated[index].price = String(skuItem.price)
      }
      // 设备采购：同时从业务定价表填充押金
      if (selectedType === '设备采购' && skuPriceTable) {
        const tableItem = skuPriceTable.find(item => item.sku_id === parseInt(value))
        console.log('[DEBUG] 设备采购 deposit lookup:', { skuId: value, tableItem, deposit: tableItem?.deposit, skuPriceTableLength: skuPriceTable.length })
        if (tableItem) {
          updated[index].deposit = String(tableItem.deposit || 0)
        }
      }
    }

    // Auto-fill price/deposit from skuPriceTable (for 物料供应/库存拨付/设备采购 without batch)
    if (field === 'sku_id' && !formData.sc_id && (selectedType === '物料供应' || selectedType === '库存拨付' || selectedType === '设备采购') && !updated[index].batch_inventory_id) {
      const tableItem = skuPriceTable?.find(item => item.sku_id === parseInt(value))
      if (tableItem) {
        updated[index].price = String(tableItem.price)
        updated[index].deposit = String(tableItem.deposit || 0)
      }
    }

    setElements(updated)
  }

  const removeElement = (index: number) => {
    setElements(elements.filter((_, i) => i !== index))
  }

  const addReturnElement = () => {
    setReturnElements([...returnElements, { original_element_id: '', sku_id: '', qty: '', sn_list: '' }])
  }

  const updateReturnElement = (index: number, field: string, value: string) => {
    const updated = [...returnElements]
    updated[index] = { ...updated[index], [field]: value }
    setReturnElements(updated)
  }

  const removeReturnElement = (index: number) => {
    setReturnElements(returnElements.filter((_, i) => i !== index))
  }

  const totalAmount = elements.reduce((sum, el) => {
    return sum + (parseFloat(el.qty) || 0) * (parseFloat(el.price) || 0)
  }, 0)

  const isEquipment = selectedType === '设备采购' || selectedType === '库存采购'

  const resetForm = () => {
    setSelectedType(null)
    setFormData({
      business_id: '',
      sc_id: '',
      description: '',
      total_amt: '',
      total_deposit: '',
      prepayment_ratio: '0.3',
      balance_period: '30',
      day_rule: '自然日',
      start_trigger: '入库日',
    })
    setElements([])
    setScSkuIds([])
    setDefaultShippingPointId('')
    setCreatedDate('')
    setMaterialBatchesMap({})
  }

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open)
    if (open) {
      setCreatedDate(new Date().toISOString().slice(0, 10))
    } else {
      resetForm()
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          新建虚拟合同
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {selectedType ? `新建${VC_TYPE_LABELS[selectedType]}` : '选择合同类型'}
          </DialogTitle>
        </DialogHeader>

        {!selectedType ? (
          <div className="grid grid-cols-2 gap-4 py-4">
            {Object.entries(VC_TYPE_LABELS).map(([type, label]) => (
              <Button
                key={type}
                variant="outline"
                className="h-20 text-lg"
                onClick={() => setSelectedType(type as VCType)}
              >
                {label}
              </Button>
            ))}
          </div>
        ) : selectedType === '退货' ? (
          <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate() }} className="space-y-6">
            <div className="space-y-2">
              <Label>原虚拟合同</Label>
              <Select value={returnFormData.target_vc_id} onValueChange={(v) => {
                const selectedVC = vcsForReturn?.items?.find(vc => String(vc.id) === v)
                const isEquipmentReturn = selectedVC?.type === '设备采购'
                setReturnFormData({
                  ...returnFormData,
                  target_vc_id: v,
                  receiving_point_id: '',
                  return_direction: isEquipmentReturn ? returnFormData.return_direction : 'CUSTOMER_TO_US'
                })
              }}>
                <SelectTrigger><SelectValue placeholder="选择原合同" /></SelectTrigger>
                <SelectContent>
                  {vcsForReturn?.items?.map(vc => {
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

            {(() => {
              const selectedVC = vcsForReturn?.items?.find(vc => String(vc.id) === returnFormData.target_vc_id)
              const isEquipmentReturn = selectedVC?.type === '设备采购'
              if (!isEquipmentReturn) return null
              return (
                <div className="space-y-2">
                  <Label>退货方向</Label>
                  <Select value={returnFormData.return_direction} onValueChange={(v) => setReturnFormData({ ...returnFormData, return_direction: v, receiving_point_id: '' })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="CUSTOMER_TO_US">客户退货给我方</SelectItem>
                      <SelectItem value="US_TO_SUPPLIER">我方退货给供应商</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )
            })()}

            <div className="space-y-2">
              <Label>收货点位</Label>
              <PointSelect
                value={returnFormData.receiving_point_id}
                onValueChange={(v) => setReturnFormData({ ...returnFormData, receiving_point_id: v })}
                options={returnReceivingPoints as PointOption[]}
                placeholder="选择收货点位"
              />
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>货款金额</Label>
                <Input type="number" value={returnFormData.goods_amount} onChange={(e) => setReturnFormData({ ...returnFormData, goods_amount: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>押金金额</Label>
                <Input type="number" value={returnFormData.deposit_amount} onChange={(e) => setReturnFormData({ ...returnFormData, deposit_amount: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>物流费用</Label>
                <Input type="number" value={returnFormData.logistics_cost} onChange={(e) => setReturnFormData({ ...returnFormData, logistics_cost: e.target.value })} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>物流承担方</Label>
                <Select value={returnFormData.logistics_bearer} onValueChange={(v) => setReturnFormData({ ...returnFormData, logistics_bearer: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="SENDER">发货方</SelectItem>
                    <SelectItem value="RECEIVER">收货方</SelectItem>
                    <SelectItem value="BUYER">买方</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>退款总额</Label>
                <Input type="number" value={returnFormData.total_refund} onChange={(e) => setReturnFormData({ ...returnFormData, total_refund: e.target.value })} />
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label>退货明细</Label>
                <Button type="button" variant="outline" size="sm" onClick={addReturnElement}>
                  <Plus className="mr-2 h-4 w-4" />添加
                </Button>
              </div>
              {returnElements.map((el, idx) => (
                <Card key={idx}>
                  <CardContent className="pt-4">
                    <div className="grid grid-cols-4 gap-3">
                      <div className="space-y-2">
                        <Label className="text-xs">SKU</Label>
                        <Select value={el.sku_id} onValueChange={(v) => updateReturnElement(idx, 'sku_id', v)}>
                          <SelectTrigger><SelectValue placeholder="选择SKU" /></SelectTrigger>
                          <SelectContent>
                            {skus?.items?.map(s => (
                              <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-xs">数量</Label>
                        <Input type="number" value={el.qty} onChange={(e) => updateReturnElement(idx, 'qty', e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-xs">SN列表</Label>
                        <Input placeholder="SN1,SN2" value={el.sn_list} onChange={(e) => updateReturnElement(idx, 'sn_list', e.target.value)} />
                      </div>
                      <div className="flex items-end">
                        <Button type="button" variant="ghost" onClick={() => removeReturnElement(idx)}>
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {returnElements.length === 0 && <div className="text-center py-4 text-muted-foreground">点击添加退货明细</div>}
            </div>

            <div className="space-y-2">
              <Label>退货原因</Label>
              <Input value={returnFormData.reason} onChange={(e) => setReturnFormData({ ...returnFormData, reason: e.target.value })} />
            </div>

            <div className="space-y-2">
              <Label>备注</Label>
              <Textarea value={returnFormData.description} onChange={(e) => setReturnFormData({ ...returnFormData, description: e.target.value })} />
            </div>

            <div className="space-y-2">
              <Label className="text-xs">业务发生日期</Label>
              <DatePicker value={createdDate} onChange={setCreatedDate} />
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setSelectedType(null)}>返回</Button>
              <Button type="submit" disabled={createMutation.isPending || !returnFormData.target_vc_id}>
                {createMutation.isPending ? '创建中...' : '创建'}
              </Button>
            </div>
          </form>
        ) : (
        <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate() }} className="space-y-6">
          {/* Business/Supply Chain Selection */}
          {(selectedType === '设备采购' || selectedType === '物料供应' || selectedType === '库存拨付') && (
            <div className="space-y-2">
              <Label>关联业务</Label>
              <Select value={formData.business_id} onValueChange={(v) => setFormData({ ...formData, business_id: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="选择业务" />
                </SelectTrigger>
                <SelectContent>
                  {businesses?.items?.map(b => (
                    <SelectItem key={b.id} value={String(b.id)}>{b.customer_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {(selectedType === '设备采购' || selectedType === '库存采购' || selectedType === '物料采购') && (
            <div className="space-y-2">
              <Label>供应链协议</Label>
              <Select value={formData.sc_id} onValueChange={(v) => {
                setFormData({ ...formData, sc_id: v })
                setElements([]) // 清空已有明细，因为 SKU 列表可能变化
                const sc = supplyChains?.items?.find(s => s.id === parseInt(v))
                if (sc?.items) {
                  const skuIds = sc.items.map((i: any) => i.sku_id)
                  setScSkuIds(skuIds)
                } else {
                  setScSkuIds([])
                }
                // 找到供应商的仓库点（id 最小的）
                const supplierPoints = points?.items?.filter(p => p.supplier_id === sc?.supplier_id) || []
                const defaultPoint = supplierPoints.sort((a, b) => a.id - b.id)[0]
                setDefaultShippingPointId(defaultPoint ? String(defaultPoint.id) : '')
              }}>
                <SelectTrigger>
                  <SelectValue placeholder="选择供应链" />
                </SelectTrigger>
                <SelectContent>
                  {supplyChains?.items?.filter(sc => {
                    if (selectedType === '物料采购') return sc.type === '物料'
                    if (selectedType === '设备采购' || selectedType === '库存采购') return sc.type === '设备'
                    return false
                  }).map(sc => (
                    <SelectItem key={sc.id} value={String(sc.id)}>
                      <div className="flex flex-col gap-0.5">
                        <span>{sc.supplier_name || `供应商${sc.supplier_id}`} ({sc.type === '设备' ? '设备' : sc.type === '物料' ? '物料' : sc.type})</span>
                        <span className="text-xs text-muted-foreground">
                          SKU {sc.items?.length || 0} 种 {sc.contract_num ? `| 合同号: ${sc.contract_num}` : ''}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Payment Terms */}
          {(selectedType === '设备采购' || selectedType === '库存采购' || selectedType === '物料采购') && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label className="text-xs">预付款比例</Label>
                <Input type="number" step="0.01" min="0" max="1"
                  value={formData.prepayment_ratio}
                  onChange={(e) => setFormData({ ...formData, prepayment_ratio: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">账期(天)</Label>
                <Input type="number"
                  value={formData.balance_period}
                  onChange={(e) => setFormData({ ...formData, balance_period: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">日期规则</Label>
                <Select value={formData.day_rule} onValueChange={(v) => setFormData({ ...formData, day_rule: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="自然日">自然日</SelectItem>
                    <SelectItem value="工作日">工作日</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs">起算触发</Label>
                <Select value={formData.start_trigger} onValueChange={(v) => setFormData({ ...formData, start_trigger: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="入库日">入库日</SelectItem>
                    <SelectItem value="签收日">签收日</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {/* Elements */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>明细项目</Label>
              <Button type="button" variant="outline" size="sm" onClick={addElement} disabled={(selectedType === '物料供应' || selectedType === '库存拨付') && !formData.business_id || (selectedType === '物料采购' || selectedType === '设备采购' || selectedType === '库存采购') && !formData.sc_id}>
                <Plus className="mr-2 h-4 w-4" />添加项目
              </Button>
            </div>

            {elements.map((el, index) => (
              <Card key={index}>
                <CardContent className="pt-4 space-y-3">
                  {/* 第一行：SKU | 批次/仓库 | 发货点位 */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="space-y-2">
                      <Label className="text-xs">SKU</Label>
                      <Select value={el.sku_id} onValueChange={(v) => updateElement(index, 'sku_id', v)}>
                        <SelectTrigger><SelectValue placeholder="选择SKU" /></SelectTrigger>
                        <SelectContent>
                          {(() => {
                            return skus?.items?.filter(s => {
                              // 物料供应：从 skuPriceTable（定价+addon，addon价优先）中选择，且必须有库存
                              if (!formData.sc_id && selectedType === '物料供应' && formData.business_id) {
                                // skuPriceTable 加载中时，降级显示所有物料 SKU
                                if (skuPriceTableLoading || skuPriceTable === undefined) {
                                  const stockSkuIds = materialSkusWithStock?.map(st => st.sku_id) || []
                                  if (stockSkuIds.length > 0 && !stockSkuIds.includes(s.id)) return false
                                  return s.type_level1 === '物料'
                                }
                                const isInTable = skuPriceTable?.some(item => item.sku_id === s.id)
                                if (!isInTable) return false
                                const stockSkuIds = materialSkusWithStock?.map(st => st.sku_id) || []
                                if (stockSkuIds.length > 0 && !stockSkuIds.includes(s.id)) return false
                                return true
                              }
                              // 库存拨付：从 skuPriceTable 中选择（不需要检查库存）
                              if (!formData.sc_id && selectedType === '库存拨付' && formData.business_id) {
                                if (skuPriceTableLoading || skuPriceTable === undefined) return false
                                return skuPriceTable?.some(item => item.sku_id === s.id) ?? false
                              }
                              // 设备采购无供应链时：从业务定价中选择
                              if (!formData.sc_id && selectedType === '设备采购' && formData.business_id) {
                                if (skuPriceTableLoading || skuPriceTable === undefined) return false
                                return skuPriceTable?.some(item => item.sku_id === s.id) ?? false
                              }
                              // 物料采购/设备采购：从供应链中选择
                              return scSkuIds.length === 0 || scSkuIds.includes(s.id)
                            }).map(s => (
                              <SelectItem key={s.id} value={String(s.id)} className="truncate">{s.name}</SelectItem>
                            ))
                          })()}
                        </SelectContent>
                      </Select>
                    </div>
                    {/* 物料供应：批次/仓库选择 */}
                    {selectedType === '物料供应' && (
                      <div className="space-y-2">
                        <Label className="text-xs">批次/仓库</Label>
                        <Select
                          value={el.batch_inventory_id}
                          onValueChange={(v) => updateElement(index, 'batch_inventory_id', v)}
                          disabled={!el.sku_id}
                        >
                          <SelectTrigger><SelectValue placeholder={el.sku_id ? "选择批次" : "先选SKU"} /></SelectTrigger>
                          <SelectContent>
                            {(materialBatchesMap[index] || []).map(b => (
                              <SelectItem key={b.inventory_id} value={String(b.inventory_id)} className="truncate">
                                {b.display}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                    <div className="space-y-2">
                      <Label className="text-xs">发货点位</Label>
                      <PointSelect
                        value={el.warehouse_point_id || el.shipping_point_id}
                        onValueChange={(v) => updateElement(index, 'shipping_point_id', v)}
                        options={(selectedType === '物料采购' || selectedType === '设备采购' || selectedType === '库存采购') ? (supplierPoints as PointOption[]) : (points?.items || []) as PointOption[]}
                        placeholder="发货点位"
                        disabled={selectedType === '物料供应' || ((selectedType === '物料采购' || selectedType === '设备采购' || selectedType === '库存采购') && (supplierPoints.length === 1))}
                      />
                    </div>
                  </div>
                  {/* 第二行：收货点位 | 数量 | 单价 | 押金(设备) | 删除 */}
                  <div className="grid grid-cols-3 md:grid-cols-6 gap-3 items-end">
                    <div className="space-y-2">
                      <Label className="text-xs">收货点位</Label>
                      <PointSelect
                        value={el.receiving_point_id}
                        onValueChange={(v) => updateElement(index, 'receiving_point_id', v)}
                        options={(selectedType === '物料供应' || selectedType === '库存拨付') ? (customerPoints as PointOption[]) : selectedType === '物料采购' || selectedType === '设备采购' ? (matOrEquipProcurementReceivingPoints as PointOption[]) : selectedType === '库存采购' ? (stockProcurementReceivingPoints as PointOption[]) : (points?.items || []) as PointOption[]}
                        placeholder="收货点位"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">数量</Label>
                      <Input
                        type="number"
                        value={el.qty}
                        onChange={(e) => updateElement(index, 'qty', e.target.value)}
                        className={el.qty_error ? 'border-red-500 focus:ring-red-500' : ''}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">单价</Label>
                      <Input type="number" value={el.price} onChange={(e) => updateElement(index, 'price', e.target.value)} />
                    </div>
                    {isEquipment && (
                      <div className="space-y-2">
                        <Label className="text-xs">押金</Label>
                        <Input type="number" value={el.deposit} onChange={(e) => updateElement(index, 'deposit', e.target.value)} />
                      </div>
                    )}
                    <div className="flex items-end">
                      <Button type="button" variant="ghost" size="icon" onClick={() => removeElement(index)}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="text-right text-sm text-muted-foreground">
                    小计: {formatCurrency((parseFloat(el.qty) || 0) * (parseFloat(el.price) || 0))}
                  </div>
                </CardContent>
              </Card>
            ))}

            {elements.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                点击"添加项目"添加明细
              </div>
            )}
          </div>

          {/* Total */}
          <div className="flex justify-between items-center text-lg">
            <span>总金额:</span>
            <span className="font-bold">{formatCurrency(totalAmount)}</span>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label>备注</Label>
            <Textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
          </div>

          <div className="space-y-2">
            <Label className="text-xs">业务发生日期</Label>
            <DatePicker value={createdDate} onChange={setCreatedDate} />
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setSelectedType(null)}>返回</Button>
            <Button type="submit" disabled={createMutation.isPending || elements.length === 0 || totalAmount <= 0 || elements.some(el => el.qty_error)}>
              {createMutation.isPending ? '创建中...' : '创建'}
            </Button>
          </div>
        </form>
        )}
      </DialogContent>
    </Dialog>
  )
}

function AllocateInventoryDialog({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)
  const [formData, setFormData] = useState({ business_id: '', description: '' })
  const [elements, setElements] = useState<ElementFormState[]>([])
  const [businessPricing, setBusinessPricing] = useState<Record<string, { price: number; deposit: number }>>({})
  const [addonSkus, setAddonSkus] = useState<{ sku_id: number; override_price?: number; override_deposit?: number }[]>([])
  const [businessPricingFailed, setBusinessPricingFailed] = useState(false)

  const { data: businesses } = useQuery({
    queryKey: ['businesses-for-allocate'],
    queryFn: async () => {
      try {
        return await businessApi.list({ status: '业务开展', size: 100 })
      } catch {
        const customers = await masterApi.customers.list({ size: 100 })
        return {
          items: customers.items.map(c => ({ id: c.id, customer_id: c.id, status: '业务开展', customer_name: c.name, details: {} })),
          total: customers.total,
          page: customers.page,
          size: customers.size,
        }
      }
    },
  })

  const { data: points } = useQuery({
    queryKey: ['points-for-allocate'],
    queryFn: () => masterApi.points.list({ size: 100 }),
  })

  const { data: skus } = useQuery({
    queryKey: ['skus-for-allocate'],
    queryFn: () => masterApi.skus.list({ size: 100 }),
  })

  useEffect(() => {
    if (!formData.business_id) {
      setBusinessPricing({})
      setAddonSkus([])
      setBusinessPricingFailed(false)
      return
    }
    const bid = parseInt(formData.business_id)
    Promise.all([
      businessApi.getDetail(bid),
      businessApi.listActiveAddons(bid),
    ]).then(([bizDetail, addons]) => {
      setBusinessPricing((bizDetail.details as any)?.pricing || {})
      setBusinessPricingFailed(false)
      const newSkuAddons = (addons || []).filter((a: any) => a.addon_type === 'NEW_SKU' && a.sku_id)
      setAddonSkus(newSkuAddons.map((a: any) => ({
        sku_id: a.sku_id,
        override_price: a.override_price,
        override_deposit: a.override_deposit,
      })))
    }).catch(() => {
      setBusinessPricing({})
      setAddonSkus([])
      setBusinessPricingFailed(true)
    })
  }, [formData.business_id])

  const createMutation = useMutation({
    mutationFn: () => vcApi.allocateInventory({
      business_id: parseInt(formData.business_id),
      elements: elements.map(el => ({
        shipping_point_id: parseInt(el.shipping_point_id) || 0,
        receiving_point_id: parseInt(el.receiving_point_id) || 0,
        sku_id: parseInt(el.sku_id),
        qty: parseFloat(el.qty) || 0,
        price: parseFloat(el.price) || 0,
        deposit: 0,
        subtotal: (parseFloat(el.qty) || 0) * (parseFloat(el.price) || 0),
      })),
      description: formData.description,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vc-list'] })
      setIsOpen(false)
      setBusinessPricing({})
      setAddonSkus([])
      setBusinessPricingFailed(false)
      onSuccess()
    },
  })

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open)
    if (!open) {
      setBusinessPricing({})
      setAddonSkus([])
      setBusinessPricingFailed(false)
    }
  }

  const addElement = () => {
    setElements([...elements, { sku_id: '', batch_inventory_id: '', warehouse_point_id: '', batch_no: '', shipping_point_id: '', receiving_point_id: '', qty: '', price: '', deposit: '', sn_list: '' }])
  }

  const updateElement = (index: number, field: keyof ElementFormState, value: string) => {
    const updated = [...elements]
    updated[index] = { ...updated[index], [field]: value }

    // Auto-fill price from business pricing / addon override
    if (field === 'sku_id' && formData.business_id) {
      const skuId = String(value)
      const addonSku = addonSkus.find(a => a.sku_id === parseInt(skuId))
      if (addonSku?.override_price !== undefined && addonSku.override_price !== null) {
        updated[index].price = String(addonSku.override_price)
      } else if (businessPricing[skuId]) {
        updated[index].price = String(businessPricing[skuId].price)
      }
    }

    setElements(updated)
  }

  const pricingSkuCount = Object.keys(businessPricing).length
  const addonSkuCount = addonSkus.length

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <Plus className="mr-2 h-4 w-4" />库存拨付
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>库存拨付</DialogTitle>
        </DialogHeader>
        <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate() }} className="space-y-6">
          <div className="space-y-2">
            <Label>业务（客户）</Label>
            <Select value={formData.business_id} onValueChange={(v) => setFormData({ ...formData, business_id: v })}>
              <SelectTrigger><SelectValue placeholder="选择业务" /></SelectTrigger>
              <SelectContent>
                {businesses?.items?.map(b => (
                  <SelectItem key={b.id} value={String(b.id)}>{b.customer_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>拨付明细</Label>
              <Button type="button" variant="outline" size="sm" onClick={addElement}>
                <Plus className="mr-2 h-4 w-4" />添加
              </Button>
            </div>
            {elements.map((el, idx) => (
              <Card key={idx}>
                <CardContent className="pt-4">
                  <div className="grid grid-cols-5 gap-3">
                    <div className="space-y-2">
                      <Label className="text-xs">SKU{formData.business_id && (pricingSkuCount > 0 || addonSkuCount > 0) ? ` (${pricingSkuCount}${addonSkuCount > 0 ? `+${addonSkuCount}` : ''})` : ''}{businessPricingFailed ? ' ⚠️' : ''}</Label>
                      <Select value={el.sku_id} onValueChange={(v) => updateElement(idx, 'sku_id', v)}>
                        <SelectTrigger><SelectValue placeholder="选择SKU" /></SelectTrigger>
                        <SelectContent>
                          {skus?.items?.filter(s => {
                            if (!formData.business_id) return s.type_level1 === '物料'
                            if (businessPricingFailed) return s.type_level1 === '物料'
                            const businessSkuIds = Object.keys(businessPricing).map(Number)
                            const addonSkuIds = addonSkus.map(a => a.sku_id)
                            return (businessSkuIds.includes(s.id) || addonSkuIds.includes(s.id)) && s.type_level1 === '物料'
                          }).map(s => (
                            <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">发货点位</Label>
                      <PointSelect
                        value={el.shipping_point_id}
                        onValueChange={(v) => updateElement(idx, 'shipping_point_id', v)}
                        options={(points?.items || []) as PointOption[]}
                        placeholder="发货点位"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">收货点位</Label>
                      <PointSelect
                        value={el.receiving_point_id}
                        onValueChange={(v) => updateElement(idx, 'receiving_point_id', v)}
                        options={(() => {
                          if (!formData.business_id || !businesses?.items || !points?.items) return points?.items || []
                          const biz = businesses.items.find(b => String(b.id) === String(formData.business_id))
                          if (!biz?.customer_id) return points.items
                          return points.items.filter((p: Point) => String(p.customer_id) === String(biz.customer_id))
                        })() as PointOption[]}
                        placeholder="收货点位"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">数量</Label>
                      <Input type="number" value={el.qty} onChange={(e) => updateElement(idx, 'qty', e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">单价</Label>
                      <Input type="number" value={el.price} onChange={(e) => updateElement(idx, 'price', e.target.value)} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {elements.length === 0 && <div className="text-center py-4 text-muted-foreground">点击添加拨付明细</div>}
          </div>

          <div className="space-y-2">
            <Label>备注</Label>
            <Textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>取消</Button>
            <Button type="submit" disabled={!formData.business_id || elements.length === 0 || createMutation.isPending}>
              {createMutation.isPending ? '创建中...' : '创建'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function VCUpdateDialog({ vc, onSuccess }: { vc: VirtualContract; onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)
  const [formData, setFormData] = useState({ description: vc.description || '' })

  const updateMutation = useMutation({
    mutationFn: () => vcApi.update({ vc_id: vc.id, description: formData.description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vc-list'] })
      queryClient.invalidateQueries({ queryKey: ['vc-detail', vc.id] })
      setIsOpen(false)
      onSuccess()
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm"><Pencil className="h-4 w-4" /></Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>编辑合同描述</DialogTitle>
        </DialogHeader>
        <form onSubmit={(e) => { e.preventDefault(); updateMutation.mutate() }} className="space-y-4">
          <div className="space-y-2">
            <Label>描述</Label>
            <Textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setIsOpen(false)}>取消</Button>
            <Button type="submit" disabled={updateMutation.isPending}>保存</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function VCDetailDialog({ vc, onClose }: { vc: VirtualContract; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState('detail')

  const { data: detail, isLoading } = useQuery({
    queryKey: ['vc-detail', vc.id],
    queryFn: () => vcApi.getDetail(vc.id),
    enabled: activeTab === 'detail',
  })

  const { data: progress } = useQuery({
    queryKey: ['vc-progress', vc.id],
    queryFn: () => vcApi.getCashflowProgress(vc.id),
    enabled: activeTab === 'payment',
  })

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Badge className={VC_TYPE_COLORS[vc.type]}>{VC_TYPE_LABELS[vc.type]}</Badge>
            <span>VC-{vc.id}</span>
          </DialogTitle>
        </DialogHeader>

        {/* Status Badges */}
        <div className="flex gap-2 flex-wrap">
          <Badge className={STATUS_COLORS[vc.status] || 'bg-gray-100'}>状态: {vc.status}</Badge>
          <Badge className={STATUS_COLORS[vc.subject_status] || 'bg-gray-100'}>标的: {vc.subject_status}</Badge>
          <Badge className={STATUS_COLORS[vc.cash_status] || 'bg-gray-100'}>资金: {vc.cash_status}</Badge>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="detail">详情</TabsTrigger>
            <TabsTrigger value="payment">付款进度</TabsTrigger>
            <TabsTrigger value="logistics">物流</TabsTrigger>
          </TabsList>

          <TabsContent value="detail" className="space-y-4">
            {isLoading ? (
              <div className="text-center py-4">加载中...</div>
            ) : detail ? (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-muted-foreground">关联业务</Label>
                    <p>{detail.business_name || '-'}</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">供应链</Label>
                    <p>{detail.supply_chain_name || '-'}</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">总金额</Label>
                    <p>{formatCurrency(detail.total_amount || 0)}</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">预付款比例</Label>
                    <p>{((detail.deposit_info?.prepayment_ratio || 0) * 100).toFixed(0)}%</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">应收押金</Label>
                    <p>{formatCurrency(detail.deposit_info?.expected_deposit || 0)}</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">实收押金</Label>
                    <p>{formatCurrency(detail.deposit_info?.actual_deposit || 0)}</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">应付总额</Label>
                    <p>{formatCurrency(detail.total_amount || 0)}</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">实付金额</Label>
                    <p>{formatCurrency(detail.deposit_info?.paid_amount || 0)}</p>
                  </div>
                </div>

                <div>
                  <Label className="text-muted-foreground">描述</Label>
                  <p>{detail.description || '-'}</p>
                </div>

                {/* 合作方信息（物料供应类型 VC） */}
                {detail.partner_relation && (
                  <div className="flex items-center gap-4 p-3 bg-muted rounded-lg">
                    <Badge variant="outline">合作方</Badge>
                    <span className="font-medium">{detail.partner_relation.partner_name}</span>
                    <span className="text-muted-foreground">({detail.partner_relation.relation_type})</span>
                  </div>
                )}

                <div>
                  <Label className="mb-2">明细项目</Label>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>SKU</TableHead>
                        <TableHead>发货点</TableHead>
                        <TableHead>收货点位</TableHead>
                        <TableHead className="text-right">数量</TableHead>
                        <TableHead className="text-right">单价</TableHead>
                        <TableHead className="text-right">押金</TableHead>
                        <TableHead className="text-right">小计</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(((detail.elements as any)?.items) || ((detail.elements as any)?.elements) || [])?.map((el: any, idx: number) => (
                        <TableRow key={idx}>
                          <TableCell>{el.sku_name || el.sku_id}</TableCell>
                          <TableCell>{el.shipping_point_name || el.shipping_point_id}</TableCell>
                          <TableCell>{el.receiving_point_name || el.receiving_point_id}</TableCell>
                          <TableCell className="text-right">{el.qty}</TableCell>
                          <TableCell className="text-right">{formatCurrency(el.price)}</TableCell>
                          <TableCell className="text-right">{formatCurrency(el.deposit)}</TableCell>
                          <TableCell className="text-right">{formatCurrency(el.subtotal)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                {/* Status History */}
                {detail.status_logs && detail.status_logs.length > 0 && (
                  <div>
                    <Label className="mb-2">状态历史</Label>
                    <div className="space-y-2">
                      {[...detail.status_logs].sort((a, b) => (a.transaction_date || '').localeCompare(b.transaction_date || '')).map((log) => (
                        <div key={log.id} className="flex items-center gap-2 text-sm">
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          <span className="text-muted-foreground">{formatDate(log.transaction_date)}</span>
                          <Badge className={STATUS_COLORS[log.status_name] || 'bg-gray-100'}>{log.status_name}</Badge>
                          <span className="text-muted-foreground text-xs">[{(log.category || '').toUpperCase()}]</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-4">无数据</div>
            )}
          </TabsContent>

          <TabsContent value="payment" className="space-y-4">
            {progress ? (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold">{formatCurrency(progress.goods?.total || 0)}</div>
                    <p className="text-sm text-muted-foreground">应付总额</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold text-green-600">{formatCurrency(progress.goods?.paid || 0)}</div>
                    <p className="text-sm text-muted-foreground">已付金额</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold text-orange-600">{formatCurrency(progress.goods?.balance || 0)}</div>
                    <p className="text-sm text-muted-foreground">未付余额</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold">{formatCurrency(progress.deposit?.should || 0)}</div>
                    <p className="text-sm text-muted-foreground">应收押金</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold text-blue-600">{formatCurrency(progress.deposit?.received || 0)}</div>
                    <p className="text-sm text-muted-foreground">实收押金</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold">{formatCurrency(progress.goods?.pool || 0)}</div>
                    <p className="text-sm text-muted-foreground">核销池余额</p>
                  </CardContent>
                </Card>
              </div>
            ) : (
              <div className="text-center py-4">加载中...</div>
            )}
          </TabsContent>

          <TabsContent value="logistics">
            {detail?.logistics && detail.logistics.length > 0 ? (
              <div className="space-y-4">
                {detail.logistics.map(log => (
                  <Card key={log.id}>
                    <CardHeader>
                      <CardTitle className="text-base flex items-center justify-between">
                        <span>物流-{log.id}</span>
                        <Badge>{log.status}</Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>快递单号</TableHead>
                            <TableHead>状态</TableHead>
                            <TableHead>物品</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {(log.express_orders || []).map(order => (
                            <TableRow key={order.id}>
                              <TableCell className="font-mono">{order.tracking_number}</TableCell>
                              <TableCell><Badge>{order.status}</Badge></TableCell>
                              <TableCell>
                                {order.items?.map((item, i) => (
                                  <span key={i} className="mr-2">{item.sku_name} x{item.qty}</span>
                                ))}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-center py-4 text-muted-foreground">暂无物流记录</div>
            )}
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}

function ReturnCreateDialog({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)
  const [formData, setFormData] = useState({
    target_vc_id: '',
    return_direction: 'CUSTOMER_TO_US',
    receiving_point_id: '',
    goods_amount: '',
    deposit_amount: '',
    logistics_cost: '',
    logistics_bearer: 'SENDER',
    total_refund: '',
    reason: '',
    description: '',
  })
  const [elements, setElements] = useState<{
    original_element_id: string
    sku_id: string
    qty: string
    sn_list: string
  }[]>([])

  const { data: vcs } = useQuery({
    queryKey: ['vcs-for-return'],
    queryFn: () => vcApi.list({ status: '执行', size: 100 }),
  })

  const { data: skus } = useQuery({
    queryKey: ['skus-for-return'],
    queryFn: () => masterApi.skus.list({ size: 100 }),
  })

  const createMutation = useMutation({
    mutationFn: async () => {
      return vcApi.createReturn({
        target_vc_id: parseInt(formData.target_vc_id),
        return_direction: formData.return_direction as 'CUSTOMER_TO_US' | 'US_TO_SUPPLIER',
        receiving_point_id: parseInt(formData.receiving_point_id) || 0,
        elements: elements.map(el => ({
          shipping_point_id: 0,
          receiving_point_id: 0,
          sku_id: parseInt(el.sku_id),
          qty: parseFloat(el.qty),
          price: 0,
          deposit: 0,
          subtotal: 0,
          sn_list: el.sn_list ? el.sn_list.split(',').map(s => s.trim()).filter(Boolean) : [],
        })),
        goods_amount: parseFloat(formData.goods_amount) || 0,
        deposit_amount: parseFloat(formData.deposit_amount) || 0,
        logistics_cost: parseFloat(formData.logistics_cost) || 0,
        logistics_bearer: formData.logistics_bearer,
        total_refund: parseFloat(formData.total_refund) || 0,
        reason: formData.reason,
        description: formData.description,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vc-list'] })
      setIsOpen(false)
      onSuccess()
    },
  })

  const addElement = () => {
    setElements([...elements, { original_element_id: '', sku_id: '', qty: '', sn_list: '' }])
  }

  const updateElement = (index: number, field: string, value: string) => {
    const updated = [...elements]
    updated[index] = { ...updated[index], [field]: value }
    setElements(updated)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button><RotateCcw className="mr-2 h-4 w-4" />新建退货</Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>新建退货</DialogTitle>
        </DialogHeader>
        <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate() }} className="space-y-6">
          <div className="space-y-2">
            <Label>退货目标合同</Label>
            <Select value={formData.target_vc_id} onValueChange={(v) => setFormData({ ...formData, target_vc_id: v })}>
              <SelectTrigger><SelectValue placeholder="选择合同" /></SelectTrigger>
              <SelectContent>
                {vcs?.items?.map(vc => (
                  <SelectItem key={vc.id} value={String(vc.id)}>
                    VC-{vc.id} {VC_TYPE_LABELS[vc.type]} - {vc.description?.slice(0, 20)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>退货方向</Label>
            <Select value={formData.return_direction} onValueChange={(v) => setFormData({ ...formData, return_direction: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="CUSTOMER_TO_US">客户退给我们</SelectItem>
                <SelectItem value="US_TO_SUPPLIER">我们退给供应商</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>退货明细</Label>
            <Button type="button" variant="outline" size="sm" onClick={addElement}>
              <Plus className="mr-2 h-4 w-4" />添加
            </Button>
            {elements.map((el, idx) => (
              <Card key={idx}>
                <CardContent className="pt-4">
                  <div className="grid grid-cols-4 gap-3">
                    <div className="space-y-2">
                      <Label className="text-xs">SKU</Label>
                      <Select value={el.sku_id} onValueChange={(v) => updateElement(idx, 'sku_id', v)}>
                        <SelectTrigger><SelectValue placeholder="选择SKU" /></SelectTrigger>
                        <SelectContent>
                          {skus?.items?.map(s => (
                            <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">数量</Label>
                      <Input type="number" value={el.qty} onChange={(e) => updateElement(idx, 'qty', e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">SN列表</Label>
                      <Input placeholder="SN1,SN2,..." value={el.sn_list} onChange={(e) => updateElement(idx, 'sn_list', e.target.value)} />
                    </div>
                    <div className="flex items-end">
                      <Button type="button" variant="ghost" onClick={() => setElements(elements.filter((_, i) => i !== idx))}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>货款金额</Label>
              <Input type="number" value={formData.goods_amount} onChange={(e) => setFormData({ ...formData, goods_amount: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>退还押金</Label>
              <Input type="number" value={formData.deposit_amount} onChange={(e) => setFormData({ ...formData, deposit_amount: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>物流费用</Label>
              <Input type="number" value={formData.logistics_cost} onChange={(e) => setFormData({ ...formData, logistics_cost: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>物流费承担方</Label>
              <Select value={formData.logistics_bearer} onValueChange={(v) => setFormData({ ...formData, logistics_bearer: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="SENDER">发货方</SelectItem>
                  <SelectItem value="RECEIVER">收货方</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>总退款金额</Label>
            <Input type="number" value={formData.total_refund} onChange={(e) => setFormData({ ...formData, total_refund: e.target.value })} />
          </div>

          <div className="space-y-2">
            <Label>退货原因</Label>
            <Textarea value={formData.reason} onChange={(e) => setFormData({ ...formData, reason: e.target.value })} />
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setIsOpen(false)}>取消</Button>
            <Button type="submit" disabled={!formData.target_vc_id || elements.length === 0 || createMutation.isPending}>
              创建
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function VCDeleteButton({ vcId }: { vcId: number }) {
  const queryClient = useQueryClient()
  const deleteMutation = useMutation({
    mutationFn: () => vcApi.delete(vcId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['vc-list'] }),
  })

  return (
    <Button variant="ghost" size="sm" onClick={() => {
      if (confirm('确认删除此虚拟合同？删除后不可恢复。')) {
        deleteMutation.mutate()
      }
    }} className="text-destructive">
      <Trash2 className="h-4 w-4" />
    </Button>
  )
}

export function VCPager() {
  const [activeTab, setActiveTab] = useState('list')
  const [typeFilter, setTypeFilter] = useState<VCType | 'ALL'>('ALL')
  const [statusFilter, setStatusFilter] = useState<VCStatus | 'ALL'>('ALL')
  const [search, setSearch] = useState('')
  const [selectedVC, setSelectedVC] = useState<VirtualContract | null>(null)
  const [page, setPage] = useState(1)
  const pageSize = 20

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['vc-list', typeFilter, statusFilter, search, page],
    queryFn: () => vcApi.list({
      type: typeFilter !== 'ALL' ? typeFilter : undefined,
      status: statusFilter !== 'ALL' ? statusFilter : undefined,
      search: search || undefined,
      page,
      size: pageSize,
    }),
  })

  // 快速查询用 SKU 列表
  const { data: skus } = useQuery({
    queryKey: ['skus-for-quick'],
    queryFn: () => masterApi.skus.list({ size: 100 }),
  })

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0

  useEffect(() => { setPage(1) }, [typeFilter, statusFilter, search])

  // ========== 全局概览搜索状态 ==========
  // Store form values as strings (from <Input>), convert to numbers in queryFn
  const [overviewParams, setOverviewParams] = useState<Record<string, string | number | undefined>>({ size: 20, page: 1 })
  const [searchCount, setSearchCount] = useState(0)

  // 快速查询状态
  type QuickTemplateKey = 'sku' | 'skuExact' | 'batch'
  const [quickTemplate, setQuickTemplate] = useState<QuickTemplateKey>('sku')
  const [quickParams, setQuickParams] = useState({
    sku_name_kw: '',
    skuId: null as number | null,
    vc_date_from: '',
    vc_date_to: '',
    batch_no: '',
  })
  const [quickSearchCount, setQuickSearchCount] = useState(0)
  const { data: quickData, isLoading: isQuickSearching } = useQuery({
    queryKey: ['vc-quick', quickParams, quickSearchCount],
    enabled: quickSearchCount > 0,
    queryFn: () => {
      const p: Record<string, unknown> = {}
      if (quickTemplate === 'sku' && quickParams.sku_name_kw) p.sku_name_kw = quickParams.sku_name_kw
      if (quickTemplate === 'skuExact' && quickParams.skuId) p.sku_id = quickParams.skuId
      if (quickTemplate === 'batch' && quickParams.sku_name_kw) p.sku_name_kw = quickParams.sku_name_kw
      if (quickParams.vc_date_from) p.vc_date_from = quickParams.vc_date_from
      if (quickParams.vc_date_to) p.vc_date_to = quickParams.vc_date_to
      if (quickParams.batch_no) p.batch_no = quickParams.batch_no
      return vcApi.getGlobalOverview(p as VCGlobalSearchParams) as unknown as Promise<VCListResponse>
    },
  })
  const doQuickSearch = () => { setQuickSearchCount(c => c + 1) }
  const clearQuick = () => { setQuickParams({ sku_name_kw: '', skuId: null, vc_date_from: '', vc_date_to: '', batch_no: '' }); setQuickSearchCount(0) }

  const { data: overviewData, isLoading: isOverviewSearching } = useQuery({
    queryKey: ['vc-global', overviewParams, searchCount],
    enabled: searchCount > 0,
    queryFn: () => {
      const p = { ...overviewParams }
      const numFields = ['vc_id', 'business_id', 'supply_chain_id', 'sku_id', 'shipping_point_id', 'receiving_point_id']
      Object.keys(p).forEach(k => {
        if (numFields.includes(k) && typeof p[k] === 'string' && p[k] !== '') {
          p[k] = Number(p[k])
        } else if ((p[k] === '' || p[k] === undefined) && !['vc_date_from', 'vc_date_to'].includes(k)) {
          delete p[k]
        }
      })
      return vcApi.getGlobalOverview(p as VCGlobalSearchParams) as unknown as Promise<VCListResponse>
    },
  })

  const doOverviewSearch = () => {
    setSelectedVC(null)
    setSearchCount(c => c + 1)
  }

  const clearOverview = () => {
    setOverviewParams({ size: 20, page: 1 })
    setSelectedVC(null)
  }

  const overviewTotalPages = overviewData ? Math.ceil(overviewData.total / (overviewData.size || 20)) : 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">虚拟合同</h2>
        <div className="flex gap-2">
          <VCCreateDialog onSuccess={() => refetch()} />
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList>
          <TabsTrigger value="list">列表</TabsTrigger>
          <TabsTrigger value="quick">快速查询</TabsTrigger>
          <TabsTrigger value="global">全局概览</TabsTrigger>
        </TabsList>

        <TabsContent value="list" className="space-y-4">
          {/* Filters */}
          <div className="flex gap-4 flex-wrap">
            <Input placeholder="搜索合同..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-64" />
            <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v as VCType | 'ALL')}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="合同类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部类型</SelectItem>
                {Object.entries(VC_TYPE_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as VCStatus | 'ALL')}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部状态</SelectItem>
                <SelectItem value="执行">执行中</SelectItem>
                <SelectItem value="完成">已完成</SelectItem>
                <SelectItem value="终止">已终止</SelectItem>
                <SelectItem value="取消">已取消</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button variant="outline" onClick={async () => {
              if (!data?.items?.length) return
              await exportToExcel(data.items, [
                { key: 'id', header: 'ID', format: (v) => `VC-${v}` },
                { key: 'type', header: '类型', format: (v) => VC_TYPE_LABELS[v as string] || String(v) },
                { key: 'counterparty', header: '交易对手' },
                { key: 'description', header: '描述' },
                { key: 'created_at', header: '创建时间', format: (v, r) => formatDate((r as VirtualContract).transaction_date || (r as VirtualContract).created_at) },
                { key: 'status', header: '状态' },
                { key: 'subject_status', header: '标的状态' },
                { key: 'cash_status', header: '资金状态' },
                { key: 'total_amount', header: '总金额', format: (v) => formatCurrency(Number(v) || 0) },
              ], `虚拟合同列表_${new Date().toISOString().slice(0,10)}`)
            }}>
              <Download className="h-4 w-4 mr-1" />导出
            </Button>
          </div>

          {/* VC List */}
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>交易对手</TableHead>
                    <TableHead>描述</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>标的</TableHead>
                    <TableHead>资金</TableHead>
                    <TableHead>总金额</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data?.items?.map(vc => (
                    <TableRow key={vc.id}>
                      <TableCell className="font-medium">VC-{vc.id}</TableCell>
                      <TableCell>
                        <Badge className={VC_TYPE_COLORS[vc.type]}>{VC_TYPE_LABELS[vc.type]}</Badge>
                      </TableCell>
                      <TableCell className="max-w-[100px] text-xs">
                        {vc.counterparty?.split('\n').map((line, i) => (
                          <div key={i}>{line}</div>
                        )) || '-'}
                      </TableCell>
                      <TableCell className="max-w-[280px] text-xs">
                        {vc.description?.split('\n').map((line, i) => (
                          <div key={i}>{line}</div>
                        )) || '-'}
                      </TableCell>
                      <TableCell>{formatDate(vc.transaction_date || vc.created_at || '')}</TableCell>
                      <TableCell><Badge className={STATUS_COLORS[vc.status]}>{vc.status}</Badge></TableCell>
                      <TableCell><Badge className={STATUS_COLORS[vc.subject_status] || 'bg-gray-100'}>{vc.subject_status}</Badge></TableCell>
                      <TableCell><Badge className={STATUS_COLORS[vc.cash_status] || 'bg-gray-100'}>{vc.cash_status}</Badge></TableCell>
                      <TableCell className="text-right">{formatCurrency(vc.total_amount || 0)}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="sm" onClick={() => setSelectedVC(vc)}>详情</Button>
                          <VCUpdateDialog vc={vc} onSuccess={() => refetch()} />
                          <VCDeleteButton vcId={vc.id} />
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
        </TabsContent>

        <TabsContent value="quick" className="space-y-4">
          {/* 快速查询表单 */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">快速查询</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* 模板选择区 */}
              <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg border">
                <span className="text-sm font-medium text-muted-foreground shrink-0">查询模板：</span>
                <Select value={quickTemplate} onValueChange={(v) => { setQuickTemplate(v as QuickTemplateKey); clearQuick() }}>
                  <SelectTrigger className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sku">按SKU模糊查询</SelectItem>
                    <SelectItem value="skuExact">按SKU精确查询</SelectItem>
                    <SelectItem value="batch">按物料批次号查询</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* 模板条件区 */}
              <div className="border rounded-lg p-4 bg-card">
                <div className="text-sm font-medium mb-3 text-foreground">
                  {quickTemplate === 'sku' && '▼ 按SKU模糊查询条件'}
                  {quickTemplate === 'skuExact' && '▼ 按SKU精确查询条件'}
                  {quickTemplate === 'batch' && '▼ 按物料批次号查询条件'}
                </div>
                {quickTemplate === 'sku' && (
                  <div className="grid grid-cols-4 gap-4">
                    <div className="space-y-1">
                      <Label className="text-xs">SKU名称（模糊匹配）</Label>
                      <Input value={quickParams.sku_name_kw} onChange={e => setQuickParams(p => ({ ...p, sku_name_kw: e.target.value }))} placeholder="输入SKU名称" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">VC创建日期起</Label>
                      <DatePicker value={quickParams.vc_date_from} onChange={v => setQuickParams(p => ({ ...p, vc_date_from: v }))} />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">VC创建日期止</Label>
                      <DatePicker value={quickParams.vc_date_to} onChange={v => setQuickParams(p => ({ ...p, vc_date_to: v }))} />
                    </div>
                  </div>
                )}
                {quickTemplate === 'skuExact' && (
                  <div className="grid grid-cols-4 gap-4">
                    <div className="space-y-1">
                      <Label className="text-xs">选择SKU</Label>
                      <Select value={quickParams.skuId ? String(quickParams.skuId) : ''} onValueChange={v => setQuickParams(p => ({ ...p, skuId: Number(v) }))}>
                        <SelectTrigger>
                          <SelectValue placeholder="选择SKU" />
                        </SelectTrigger>
                        <SelectContent>
                          {skus && skus.items && skus.items.map((s: { id: number; name: string }) => (
                            <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">VC创建日期起</Label>
                      <DatePicker value={quickParams.vc_date_from} onChange={v => setQuickParams(p => ({ ...p, vc_date_from: v }))} />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">VC创建日期止</Label>
                      <DatePicker value={quickParams.vc_date_to} onChange={v => setQuickParams(p => ({ ...p, vc_date_to: v }))} />
                    </div>
                  </div>
                )}
                {quickTemplate === 'batch' && (
                  <div className="grid grid-cols-4 gap-4">
                    <div className="space-y-1">
                      <Label className="text-xs">SKU名称（可不填）</Label>
                      <Input value={quickParams.sku_name_kw} onChange={e => setQuickParams(p => ({ ...p, sku_name_kw: e.target.value }))} placeholder="输入SKU名称" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">批次号</Label>
                      <Input value={quickParams.batch_no} onChange={e => setQuickParams(p => ({ ...p, batch_no: e.target.value }))} placeholder="输入批次号" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">VC创建日期起</Label>
                      <DatePicker value={quickParams.vc_date_from} onChange={v => setQuickParams(p => ({ ...p, vc_date_from: v }))} />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">VC创建日期止</Label>
                      <DatePicker value={quickParams.vc_date_to} onChange={v => setQuickParams(p => ({ ...p, vc_date_to: v }))} />
                    </div>
                  </div>
                )}
              </div>

              {/* 操作按钮区 */}
              <div className="flex gap-2 pt-2">
                <Button variant="outline" onClick={clearQuick}>清空</Button>
                <Button onClick={doQuickSearch} disabled={isQuickSearching}>
                  {isQuickSearching ? '搜索中...' : '搜索'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {quickData && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">共 {quickData.total} 条记录</span>
                <Button variant="outline" size="sm" onClick={async () => {
                  if (!quickData.items?.length) return
                  await exportToExcel(quickData.items, [
                    { key: 'id', header: 'ID', format: (v) => `VC-${v}` },
                    { key: 'type', header: '类型', format: (v) => VC_TYPE_LABELS[v as string] || String(v) },
                    { key: 'counterparty', header: '交易对手' },
                    { key: 'description', header: '描述' },
                    { key: 'created_at', header: '创建时间', format: (v, r) => formatDate((r as VirtualContract).transaction_date || (r as VirtualContract).created_at) },
                    { key: 'status', header: '状态' },
                    { key: 'subject_status', header: '标的状态' },
                    { key: 'cash_status', header: '资金状态' },
                    { key: 'total_amount', header: '总金额', format: (v) => formatCurrency(Number(v) || 0) },
                  ], `快速查询结果_${new Date().toISOString().slice(0,10)}`)
                }}>
                  <Download className="h-4 w-4 mr-1" />导出
                </Button>
              </div>
              <Card>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>ID</TableHead>
                        <TableHead>类型</TableHead>
                        <TableHead>交易对手</TableHead>
                        <TableHead>描述</TableHead>
                        <TableHead>创建时间</TableHead>
                        <TableHead>状态</TableHead>
                        <TableHead>标的</TableHead>
                        <TableHead>资金</TableHead>
                        <TableHead>总金额</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {quickData.items?.map((vc) => (
                        <TableRow key={vc.id}>
                          <TableCell className="font-medium">VC-{vc.id}</TableCell>
                          <TableCell>
                            <Badge className={VC_TYPE_COLORS[vc.type]}>{VC_TYPE_LABELS[vc.type]}</Badge>
                          </TableCell>
                          <TableCell className="max-w-[100px] text-xs">
                            {vc.counterparty?.split('\n').map((line, i) => (
                              <div key={i}>{line}</div>
                            )) || '-'}
                          </TableCell>
                          <TableCell className="max-w-[280px] text-xs">
                            {vc.description?.split('\n').map((line, i) => (
                              <div key={i}>{line}</div>
                            )) || '-'}
                          </TableCell>
                          <TableCell>{formatDate(vc.transaction_date || vc.created_at || '')}</TableCell>
                          <TableCell><Badge className={STATUS_COLORS[vc.status]}>{vc.status}</Badge></TableCell>
                          <TableCell><Badge className={STATUS_COLORS[vc.subject_status] || 'bg-gray-100'}>{vc.subject_status}</Badge></TableCell>
                          <TableCell><Badge className={STATUS_COLORS[vc.cash_status] || 'bg-gray-100'}>{vc.cash_status}</Badge></TableCell>
                          <TableCell className="text-right">{formatCurrency(vc.total_amount || 0)}</TableCell>
                        </TableRow>
                      ))}
                      {!quickData.items?.length && (
                        <TableRow>
                          <TableCell colSpan={9} className="text-center text-muted-foreground">暂无数据</TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="global" className="space-y-4">
          {/* 搜索表单 */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">多条件搜索</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-4 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs">VC ID</Label>
                  <Input value={overviewParams.vc_id} onChange={e => setOverviewParams((prev) => ({ ...prev, vc_id: e.target.value }))} placeholder="VC ID" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">VC类型</Label>
                  <Select value={String(overviewParams.vc_type || '')} onValueChange={v => setOverviewParams((prev) => ({ ...prev, vc_type: v === 'ALL' ? '' : v }))}>
                    <SelectTrigger><SelectValue placeholder="选择类型" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ALL">全部</SelectItem>
                      {Object.entries(VC_TYPE_LABELS).map(([value, label]) => (
                        <SelectItem key={value} value={value}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">VC状态</Label>
                  <Select value={String(overviewParams.vc_status || '')} onValueChange={v => setOverviewParams((prev) => ({ ...prev, vc_status: v === 'ALL' ? '' : v }))}>
                    <SelectTrigger><SelectValue placeholder="选择状态" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ALL">全部</SelectItem>
                      <SelectItem value="执行">执行中</SelectItem>
                      <SelectItem value="完成">已完成</SelectItem>
                      <SelectItem value="终止">已终止</SelectItem>
                      <SelectItem value="取消">已取消</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">标的状态</Label>
                  <Select value={String(overviewParams.vc_subject_status || '')} onValueChange={v => setOverviewParams((prev) => ({ ...prev, vc_subject_status: v === 'ALL' ? '' : v }))}>
                    <SelectTrigger><SelectValue placeholder="选择标的状态" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ALL">全部</SelectItem>
                      <SelectItem value="执行">执行</SelectItem>
                      <SelectItem value="发货">发货</SelectItem>
                      <SelectItem value="签收">签收</SelectItem>
                      <SelectItem value="完成">完成</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">资金状态</Label>
                  <Select value={String(overviewParams.vc_cash_status || '')} onValueChange={v => setOverviewParams((prev) => ({ ...prev, vc_cash_status: v === 'ALL' ? '' : v }))}>
                    <SelectTrigger><SelectValue placeholder="选择资金状态" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ALL">全部</SelectItem>
                      <SelectItem value="执行">执行</SelectItem>
                      <SelectItem value="预付">预付</SelectItem>
                      <SelectItem value="完成">完成</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Business ID</Label>
                  <Input value={overviewParams.business_id} onChange={e => setOverviewParams((prev) => ({ ...prev, business_id: e.target.value }))} placeholder="Business ID" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">客户名称</Label>
                  <Input value={overviewParams.business_customer_name_kw} onChange={e => setOverviewParams((prev) => ({ ...prev, business_customer_name_kw: e.target.value }))} placeholder="精确包含" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">供应链ID</Label>
                  <Input value={overviewParams.supply_chain_id} onChange={e => setOverviewParams((prev) => ({ ...prev, supply_chain_id: e.target.value }))} placeholder="供应链ID" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">供应商名称</Label>
                  <Input value={overviewParams.supply_chain_supplier_name_kw} onChange={e => setOverviewParams((prev) => ({ ...prev, supply_chain_supplier_name_kw: e.target.value }))} placeholder="精确包含" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">SKU ID</Label>
                  <Input value={overviewParams.sku_id} onChange={e => setOverviewParams((prev) => ({ ...prev, sku_id: e.target.value }))} placeholder="SKU ID" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">SKU名称</Label>
                  <Input value={overviewParams.sku_name_kw} onChange={e => setOverviewParams((prev) => ({ ...prev, sku_name_kw: e.target.value }))} placeholder="精确包含" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">发货点位ID</Label>
                  <Input value={overviewParams.shipping_point_id} onChange={e => setOverviewParams((prev) => ({ ...prev, shipping_point_id: e.target.value }))} placeholder="发货点位ID" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">发货点位名称</Label>
                  <Input value={overviewParams.shipping_point_name_kw} onChange={e => setOverviewParams((prev) => ({ ...prev, shipping_point_name_kw: e.target.value }))} placeholder="精确包含" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">收货点位ID</Label>
                  <Input value={overviewParams.receiving_point_id} onChange={e => setOverviewParams((prev) => ({ ...prev, receiving_point_id: e.target.value }))} placeholder="收货点位ID" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">收货点位名称</Label>
                  <Input value={overviewParams.receiving_point_name_kw} onChange={e => setOverviewParams((prev) => ({ ...prev, receiving_point_name_kw: e.target.value }))} placeholder="精确包含" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">物流单号</Label>
                  <Input value={overviewParams.tracking_number} onChange={e => setOverviewParams((prev) => ({ ...prev, tracking_number: e.target.value }))} placeholder="精确包含" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">批次号</Label>
                  <Input value={overviewParams.batch_no || ''} onChange={e => setOverviewParams((prev) => ({ ...prev, batch_no: e.target.value }))} placeholder="精确包含" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">VC创建日期起</Label>
                  <DatePicker value={(overviewParams.vc_date_from as string) || ''} onChange={v => setOverviewParams((prev) => ({ ...prev, vc_date_from: v }))} />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">VC创建日期止</Label>
                  <DatePicker value={(overviewParams.vc_date_to as string) || ''} onChange={v => setOverviewParams((prev) => ({ ...prev, vc_date_to: v }))} />
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={clearOverview}>清空</Button>
                <Button onClick={doOverviewSearch} disabled={isOverviewSearching}>
                  {isOverviewSearching ? '搜索中...' : '搜索'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* 搜索结果 */}
          {overviewData && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">共 {overviewData.total} 条记录</span>
                <Button variant="outline" size="sm" onClick={async () => {
                  if (!overviewData.items?.length) return
                  await exportToExcel(overviewData.items, [
                    { key: 'id', header: 'ID', format: (v) => `VC-${v}` },
                    { key: 'type', header: '类型', format: (v) => VC_TYPE_LABELS[v as string] || String(v) },
                    { key: 'counterparty', header: '交易对手' },
                    { key: 'description', header: '描述' },
                    { key: 'created_at', header: '创建时间', format: (v, r) => formatDate((r as VirtualContract).transaction_date || (r as VirtualContract).created_at) },
                    { key: 'status', header: '状态' },
                    { key: 'subject_status', header: '标的状态' },
                    { key: 'cash_status', header: '资金状态' },
                    { key: 'total_amount', header: '总金额', format: (v) => formatCurrency(Number(v) || 0) },
                  ], `虚拟合同全局搜索_${new Date().toISOString().slice(0,10)}`)
                }}>
                  <Download className="h-4 w-4 mr-1" />导出
                </Button>
              </div>
              <Card>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>ID</TableHead>
                        <TableHead>类型</TableHead>
                        <TableHead>交易对手</TableHead>
                        <TableHead>描述</TableHead>
                        <TableHead>创建时间</TableHead>
                        <TableHead>状态</TableHead>
                        <TableHead>标的</TableHead>
                        <TableHead>资金</TableHead>
                        <TableHead>总金额</TableHead>
                        <TableHead>操作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {overviewData.items?.map((vc) => (
                        <TableRow key={vc.id}>
                          <TableCell className="font-medium">VC-{vc.id}</TableCell>
                          <TableCell>
                            <Badge className={VC_TYPE_COLORS[vc.type]}>{VC_TYPE_LABELS[vc.type]}</Badge>
                          </TableCell>
                          <TableCell className="max-w-[100px] text-xs">
                            {vc.counterparty?.split('\n').map((line, i) => (
                              <div key={i}>{line}</div>
                            )) || '-'}
                          </TableCell>
                          <TableCell className="max-w-[280px] text-xs">
                            {vc.description?.split('\n').map((line, i) => (
                              <div key={i}>{line}</div>
                            )) || '-'}
                          </TableCell>
                          <TableCell>{formatDate(vc.transaction_date || vc.created_at || '')}</TableCell>
                          <TableCell><Badge className={STATUS_COLORS[vc.status]}>{vc.status}</Badge></TableCell>
                          <TableCell><Badge className={STATUS_COLORS[vc.subject_status] || 'bg-gray-100'}>{vc.subject_status}</Badge></TableCell>
                          <TableCell><Badge className={STATUS_COLORS[vc.cash_status] || 'bg-gray-100'}>{vc.cash_status}</Badge></TableCell>
                          <TableCell className="text-right">{formatCurrency(vc.total_amount || 0)}</TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              <Button variant="ghost" size="sm" onClick={() => setSelectedVC(vc)}>详情</Button>
                              <VCUpdateDialog vc={vc} onSuccess={() => refetch()} />
                              <VCDeleteButton vcId={vc.id} />
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                      {!overviewData.items?.length && (
                        <TableRow>
                          <TableCell colSpan={10} className="text-center text-muted-foreground">暂无数据</TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {/* 分页 */}
              {overviewTotalPages > 1 && (
                <div className="flex items-center justify-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => setOverviewParams((prev) => ({ ...prev, page: Number(prev.page || 1) - 1 }))} disabled={(Number(overviewParams.page) || 1) <= 1}>上一页</Button>
                  <span className="text-sm text-muted-foreground">第 {Number(overviewParams.page) || 1} / {overviewTotalPages} 页</span>
                  <Button variant="outline" size="sm" onClick={() => setOverviewParams((prev) => ({ ...prev, page: Number(prev.page || 1) + 1 }))} disabled={(Number(overviewParams.page) || 1) >= overviewTotalPages}>下一页</Button>
                </div>
              )}
            </>
          )}
        </TabsContent>
      </Tabs>

      {selectedVC && (
        <VCDetailDialog vc={selectedVC} onClose={() => setSelectedVC(null)} />
      )}
    </div>
  )
}
