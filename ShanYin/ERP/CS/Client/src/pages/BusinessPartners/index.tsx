import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, Handshake } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { partnerApi, PartnerRelation } from '@/api/endpoints/partner'
import { masterApi, Partner } from '@/api/endpoints/master'
import { supplyChainApi, SupplyChain } from '@/api/endpoints/supplyChain'
import { businessApi, Business } from '@/api/endpoints/business'
import { PARTNER_RELATION_TYPES, EXTERNAL_PARTNER_TYPES, OWNER_TYPES } from '@/lib/constants'

const OWNER_TYPE_LABELS: Record<string, string> = {
  business: '业务',
  supply_chain: '供应链',
  ourselves: '我方自身',
}

export function BusinessPartnersPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingRelation, setEditingRelation] = useState<PartnerRelation | null>(null)
  const [formData, setFormData] = useState({
    partner_id: '',
    owner_type: 'business',
    owner_id: '',
    relation_type: PARTNER_RELATION_TYPES.PROCUREMENT as string,
    remark: '',
  })

  // 合作方关系列表
  const { data, isLoading } = useQuery({
    queryKey: ['business-partners', page],
    queryFn: () => partnerApi.relations.list({}) as unknown as Promise<{ items: PartnerRelation[]; total: number }>,
  })

  // 合作方列表（用于下拉选择）
  const { data: partnersData } = useQuery({
    queryKey: ['partners-all'],
    queryFn: () => masterApi.partners.list({ size: 500 }) as Promise<{ items: Partner[] }>,
  })

  // 业务列表（owner_type=business 时使用）
  const { data: businessData } = useQuery({
    queryKey: ['businesses-all'],
    queryFn: () => businessApi.list({ size: 500 }) as Promise<{ items: Business[] }>,
  })

  // 供应链列表（owner_type=supply_chain 时使用）
  const { data: supplyChainData } = useQuery({
    queryKey: ['supplychains-all'],
    queryFn: () => supplyChainApi.list({ size: 500 }) as Promise<{ items: SupplyChain[] }>,
  })

  // owner_type 变化时清空 owner_id
  useEffect(() => {
    setFormData(prev => ({ ...prev, owner_id: '' }))
  }, [formData.owner_type])

  // 编辑时填充表单
  useEffect(() => {
    if (editingRelation) {
      setFormData({
        partner_id: String(editingRelation.partner_id),
        owner_type: editingRelation.owner_type,
        owner_id: editingRelation.owner_id ? String(editingRelation.owner_id) : '',
        relation_type: editingRelation.relation_type,
        remark: editingRelation.remark || '',
      })
    }
  }, [editingRelation])

  // 创建
  const createMutation = useMutation({
    mutationFn: () => partnerApi.relations.create({
      partner_id: parseInt(formData.partner_id),
      owner_type: formData.owner_type,
      owner_id: formData.owner_id ? parseInt(formData.owner_id) : undefined,
      relation_type: formData.relation_type,
      remark: formData.remark || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business-partners'] })
      setIsDialogOpen(false)
      setEditingRelation(null)
      resetForm()
    },
  })

  // 删除
  const deleteMutation = useMutation({
    mutationFn: (ids: number[]) => partnerApi.relations.delete(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business-partners'] })
    },
  })

  const resetForm = () => {
    setFormData({
      partner_id: '',
      owner_type: 'business',
      owner_id: '',
      relation_type: PARTNER_RELATION_TYPES.PROCUREMENT as string,
      remark: '',
    })
  }

  const handleOpenCreate = () => {
    setEditingRelation(null)
    resetForm()
    setIsDialogOpen(true)
  }

  const handleOpenEdit = (relation: PartnerRelation) => {
    setEditingRelation(relation)
    setIsDialogOpen(true)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate()
  }

  // 根据 owner_type 获取显示名称
  const getOwnerName = (relation: PartnerRelation): string => {
    if (!relation.owner_id) return '-'
    if (relation.owner_type === 'business') {
      const biz = businessData?.items?.find(b => b.id === relation.owner_id)
      return biz?.customer_name || `业务-${relation.owner_id}`
    }
    if (relation.owner_type === 'supply_chain') {
      const sc = supplyChainData?.items?.find(s => s.id === relation.owner_id)
      return sc?.supplier_name || `供应链-${relation.owner_id}`
    }
    return '-'
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Handshake className="h-5 w-5" />
          <h2 className="text-2xl font-bold">合作方管理</h2>
        </div>
        <Button onClick={handleOpenCreate}>
          <Plus className="mr-2 h-4 w-4" />新建关系
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>合作方</TableHead>
                <TableHead>归属类型</TableHead>
                <TableHead>归属对象</TableHead>
                <TableHead>合作模式</TableHead>
                <TableHead>备注</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items?.map((rel) => (
                <TableRow key={rel.id}>
                  <TableCell className="font-medium">{rel.id}</TableCell>
                  <TableCell>{rel.partner_name}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{OWNER_TYPE_LABELS[rel.owner_type] || rel.owner_type}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{getOwnerName(rel)}</TableCell>
                  <TableCell><Badge variant="secondary">{rel.relation_type}</Badge></TableCell>
                  <TableCell className="text-muted-foreground max-w-[200px] truncate">{rel.remark || '-'}</TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button variant="ghost" size="icon" onClick={() => handleOpenEdit(rel)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate([rel.id])}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!data?.items?.length && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground">
                    {isLoading ? '加载中...' : '暂无数据'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          {data && data.total > 50 && (
            <div className="flex items-center justify-between px-4 py-2 border-t">
              <span className="text-sm text-muted-foreground">共 {data.total} 条</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}>上一页</Button>
                <span className="text-sm py-1 px-2">第 {page} / {Math.ceil(data.total / 50)} 页</span>
                <Button variant="outline" size="sm" onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(data.total / 50)}>下一页</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isDialogOpen} onOpenChange={(open) => {
        setIsDialogOpen(open)
        if (!open) {
          setEditingRelation(null)
          resetForm()
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingRelation ? '编辑合作方关系' : '新建合作方关系'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label>合作方</Label>
              <Select value={formData.partner_id} onValueChange={(v) => setFormData({ ...formData, partner_id: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="选择合作方" />
                </SelectTrigger>
                <SelectContent>
                  {partnersData?.items?.map(p => (
                    <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>归属类型</Label>
              <Select value={formData.owner_type} onValueChange={(v) => setFormData({ ...formData, owner_type: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={OWNER_TYPES.BUSINESS}>业务</SelectItem>
                  <SelectItem value={OWNER_TYPES.SUPPLY_CHAIN}>供应链</SelectItem>
                  <SelectItem value={OWNER_TYPES.OURSELVES}>我方自身</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {formData.owner_type !== OWNER_TYPES.OURSELVES && (
              <div className="space-y-2">
                <Label>归属对象</Label>
                <Select value={formData.owner_id} onValueChange={(v) => setFormData({ ...formData, owner_id: v })}>
                  <SelectTrigger>
                    <SelectValue placeholder={
                      formData.owner_type === OWNER_TYPES.BUSINESS ? '选择业务' : '选择供应链'
                    } />
                  </SelectTrigger>
                  <SelectContent>
                    {formData.owner_type === OWNER_TYPES.BUSINESS && businessData?.items?.map(b => (
                      <SelectItem key={b.id} value={String(b.id)}>{b.customer_name}</SelectItem>
                    ))}
                    {formData.owner_type === OWNER_TYPES.SUPPLY_CHAIN && supplyChainData?.items?.map(sc => (
                      <SelectItem key={sc.id} value={String(sc.id)}>{sc.supplier_name} ({sc.type})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label>合作模式</Label>
              <Select value={formData.relation_type} onValueChange={(v) => setFormData({ ...formData, relation_type: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.values(PARTNER_RELATION_TYPES).map(type => (
                    <SelectItem key={type} value={type}>{type}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>备注</Label>
              <Input value={formData.remark} onChange={(e) => setFormData({ ...formData, remark: e.target.value })} />
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => { setIsDialogOpen(false); setEditingRelation(null); resetForm() }}>取消</Button>
              <Button type="submit">{editingRelation ? '更新' : '保存'}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
