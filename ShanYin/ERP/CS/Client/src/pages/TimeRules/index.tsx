import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, RefreshCw, AlertTriangle, Pencil, Trash2, ChevronDown, ChevronRight } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DatePicker } from '@/components/ui/date-picker'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import {
  rulesApi, TimeRule, RuleRelatedType, RuleParty, RuleUnit, RuleDirection,
  RULE_EVENTS, ALL_EVENTS, VC_EVENTS, LOGISTICS_EVENTS,
  CreateTimeRuleSchema
} from '@/api/endpoints/rules'
import { businessApi } from '@/api/endpoints/business'
import { supplyChainApi } from '@/api/endpoints/supplyChain'
import { vcApi } from '@/api/endpoints/vc'
import { logisticsApi } from '@/api/endpoints/logistics'

// ─── Constants ────────────────────────────────────────────────────────────────

const AUTO_TAG = '付款条款生成'

const STATUS_COLORS: Record<string, string> = {
  '失效': 'bg-gray-100 text-gray-600',
  '模板': 'bg-purple-50 text-purple-600 border-purple-200',
  '生效': 'bg-blue-50 text-blue-600 border-blue-200',
  '有结果': 'bg-green-50 text-green-600 border-green-200',
  '结束': 'bg-gray-100 text-gray-500',
}

const STATUS_LABELS: Record<string, string> = {
  '失效': '未激活',
  '模板': '模板',
  '生效': '生效中',
  '有结果': '已触发',
  '结束': '已结束',
}

const WARNING_COLORS: Record<string, string> = {
  GREEN: 'bg-green-50 text-green-600',
  YELLOW: 'bg-yellow-50 text-yellow-600',
  ORANGE: 'bg-orange-50 text-orange-600',
  RED: 'bg-red-50 text-red-600',
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getEventLabel(eventKey: string): string {
  return RULE_EVENTS[eventKey as keyof typeof RULE_EVENTS] || eventKey
}

function isAutoRule(rule: TimeRule): boolean {
  return rule.tae_param1 === AUTO_TAG
}

function getEntityDisplayId(rule: TimeRule): string {
  if (rule.related_type === '虚拟合同') return `VC#${rule.related_id}`
  if (rule.related_type === '物流') return `物流#${rule.related_id}`
  if (rule.related_type === '供应链') return `SC#${rule.related_id}`
  return `业务#${rule.related_id}`
}

function getInheritOptions(relatedType: RuleRelatedType): { value: string; label: string }[] {
  if (relatedType === '虚拟合同') return [
    { value: '0', label: '本级定制 (合同级)' },
    { value: '1', label: '近继承 (至物流)' },
  ]
  if (relatedType === '物流') return [{ value: '0', label: '本级定制 (物流级)' }]
  return [
    { value: '0', label: '本级定制 (项目级)' },
    { value: '1', label: '近继承 (至虚拟合同)' },
    { value: '2', label: '远继承 (至物流)' },
  ]
}

function getEventsForType(relatedType: RuleRelatedType) {
  if (relatedType === '虚拟合同') return VC_EVENTS
  if (relatedType === '物流') return LOGISTICS_EVENTS
  return ALL_EVENTS
}

const OFFSET_UNIT_SHORT: Record<string, string> = {
  '自然日': '天',
  '工作日': '工作日',
  '小时': '小时',
}

// ─── Entity Name Cache ───────────────────────────────────────────────────────

type EntityNameCache = Record<string, string>

function useEntityNames(rules: TimeRule[]) {
  const [cache, setCache] = useState<EntityNameCache>({})

  useEffect(() => {
    const idsByType: Record<string, number[]> = {}
    for (const r of rules) {
      if (!cache[`${r.related_type}-${r.related_id}`]) {
        idsByType[r.related_type] = idsByType[r.related_type] || []
        if (!idsByType[r.related_type].includes(r.related_id)) {
          idsByType[r.related_type].push(r.related_id)
        }
      }
    }

    const fetches: Promise<void>[] = []

    if (idsByType['业务']?.length) {
      fetches.push(
        businessApi.list({ ids: idsByType['业务'], size: 100 }).then(res => {
          setCache(prev => {
            const next = { ...prev }
            for (const b of res.items) {
              next[`业务-${b.id}`] = b.customer_name || `业务#${b.id}`
            }
            return next
          })
        }).catch(() => {})
      )
    }

    if (idsByType['供应链']?.length) {
      fetches.push(
        supplyChainApi.list({ ids: idsByType['供应链'], size: 100 }).then(res => {
          setCache(prev => {
            const next = { ...prev }
            for (const sc of res.items) {
              next[`供应链-${sc.id}`] = `${sc.supplier_name} (${sc.type})`
            }
            return next
          })
        }).catch(() => {})
      )
    }

    if (idsByType['虚拟合同']?.length) {
      fetches.push(
        vcApi.list({ ids: idsByType['虚拟合同'], size: 100 }).then(res => {
          setCache(prev => {
            const next = { ...prev }
            for (const vc of res.items) {
              next[`虚拟合同-${vc.id}`] = `${vc.type} #${vc.id}`
            }
            return next
          })
        }).catch(() => {})
      )
    }

    if (idsByType['物流']?.length) {
      fetches.push(
        logisticsApi.list({ ids: idsByType['物流'], size: 100 }).then(res => {
          setCache(prev => {
            const next = { ...prev }
            for (const lg of res.items) {
              next[`物流-${lg.id}`] = `物流#${lg.id} (${lg.status})`
            }
            return next
          })
        }).catch(() => {})
      )
    }

    if (fetches.length === 0) return
    Promise.allSettled(fetches)
  }, [rules.map(r => `${r.related_type}-${r.related_id}`).join(',')])

  return cache
}

// ─── Timeline Visualization ───────────────────────────────────────────────────

function RuleTimeline({ rule }: { rule: TimeRule }) {
  const triggerLabel = getEventLabel(rule.trigger_event)
  const targetLabel = getEventLabel(rule.target_event)
  const isAfter = rule.direction === 'after'
  const offset = rule.offset ?? 0
  const unit = OFFSET_UNIT_SHORT[rule.unit || '自然日'] || rule.unit || '天'

  const offsetText = offset > 0 ? `${offset}${unit}` : offset < 0 ? `${Math.abs(offset)}${unit}` : ''

  if (isAfter) {
    return (
      <p className="text-sm leading-relaxed">
        <span className="font-medium">于</span>
        <span className="text-blue-600 font-semibold">{triggerLabel}</span>
        <span className="font-medium">后</span>
        {offset > 0 ? (
          <>
            <span className="text-orange-500 font-bold">{offsetText}</span>
            <span className="font-medium">达成</span>
          </>
        ) : (
          <span className="font-medium">即刻达成</span>
        )}
        <span className="text-green-600 font-semibold">{targetLabel}</span>
      </p>
    )
  } else {
    return (
      <p className="text-sm leading-relaxed">
        <span className="font-medium">于</span>
        <span className="text-green-600 font-semibold">{targetLabel}</span>
        <span className="font-medium">前</span>
        {offset > 0 ? (
          <>
            <span className="text-orange-500 font-bold">{offsetText}</span>
            <span className="font-medium">完成</span>
          </>
        ) : (
          <span className="font-medium">即刻完成</span>
        )}
        <span className="text-blue-600 font-semibold">{triggerLabel}</span>
      </p>
    )
  }
}

// ─── Rule Card ────────────────────────────────────────────────────────────────

function RuleCard({
  rule,
  entityName,
  onUpdate,
}: {
  rule: TimeRule
  entityName: string
  onUpdate: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const isAuto = isAutoRule(rule)
  const entityLabel = getEntityDisplayId(rule)

  return (
    <Card className={`relative transition-all ${isAuto ? 'border-dashed border-blue-200' : ''}`}>
      <CardContent className="pt-4">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="space-y-1 flex-1 min-w-0">
            {/* Entity + badges */}
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="outline" className="text-xs font-normal">
                {rule.related_type}
              </Badge>
              <span className="text-xs text-muted-foreground font-mono">{entityLabel}</span>
              <span className="text-xs text-muted-foreground">·</span>
              <span className="text-xs text-muted-foreground truncate max-w-[120px]" title={entityName}>
                {entityName}
              </span>
              <Badge className={`text-xs ${STATUS_COLORS[rule.status] || 'bg-gray-100'}`}>
                {STATUS_LABELS[rule.status] || rule.status}
              </Badge>
              {isAuto && (
                <Badge variant="outline" className="text-xs bg-blue-50 text-blue-600 border-blue-200">
                  自动生成
                </Badge>
              )}
              {rule.warning && (
                <Badge className={`text-xs ${WARNING_COLORS[rule.warning]}`}>
                  <AlertTriangle className="h-3 w-3 mr-0.5" />
                  {rule.warning}
                </Badge>
              )}
            </div>

            {/* Timeline */}
            <div className="mt-2">
              <RuleTimeline rule={rule} />
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => setExpanded(e => !e)}
              className="p-1 rounded hover:bg-muted text-muted-foreground"
              title={expanded ? '收起详情' : '展开详情'}
            >
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
            <RuleFormDialog mode="update" rule={rule} onSuccess={onUpdate} />
          </div>
        </div>

        {/* Footer meta */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>责任方: {rule.party}</span>
          {rule.trigger_time && <span>触发: {rule.trigger_time.split('T')[0]}</span>}
          {rule.flag_time && <span>标杆: {rule.flag_time.split('T')[0]}</span>}
          {rule.warning && <span className={WARNING_COLORS[rule.warning]}>{rule.warning === 'GREEN' ? '合规' : '告警'}</span>}
        </div>

        {/* Expanded details */}
        {expanded && (
          <div className="mt-3 pt-3 border-t space-y-2">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              {rule.tge_param1 && (
                <div>
                  <span className="text-muted-foreground">触发参数: </span>
                  <span>{rule.tge_param1}</span>
                </div>
              )}
              {rule.tae_param1 && rule.tae_param1 !== AUTO_TAG && (
                <div>
                  <span className="text-muted-foreground">目标参数: </span>
                  <span>{rule.tae_param1}</span>
                </div>
              )}
              {rule.trigger_time && (
                <div>
                  <span className="text-muted-foreground">触发时间: </span>
                  <span>{rule.trigger_time.replace('T', ' ').split('.')[0]}</span>
                </div>
              )}
              {rule.target_time && (
                <div>
                  <span className="text-muted-foreground">目标时间: </span>
                  <span>{rule.target_time.replace('T', ' ').split('.')[0]}</span>
                </div>
              )}
              <div>
                <span className="text-muted-foreground">继承层级: </span>
                <span>{rule.inherit === 0 ? '本级定制' : rule.inherit === 1 ? '近继承' : '远继承'}</span>
              </div>
              <div>
                <span className="text-muted-foreground">偏移: </span>
                <span>{rule.offset} {rule.unit}</span>
              </div>
              {rule.result && (
                <div>
                  <span className="text-muted-foreground">合规性: </span>
                  <span>{rule.result}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── ChevronUp icon (missing from lucide-react) ───────────────────────────────

function ChevronUp({ className }: { className?: string }) {
  return (
    <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="18 15 12 9 6 15" />
    </svg>
  )
}

// ─── Rule Form Dialog ─────────────────────────────────────────────────────────

interface RuleFormData {
  related_id: string
  related_type: RuleRelatedType
  party: RuleParty
  trigger_event: string
  target_event: string
  offset: string
  unit: RuleUnit
  direction: RuleDirection
  inherit: string
  tge_param1: string
  flag_time: string
  // prepayment_ratio slider value — stored separately, mapped to tge_param1 on save
  prepayment_ratio: string
}

function RuleFormDialog({
  mode,
  rule,
  relatedId,
  relatedType,
  onSuccess,
}: {
  mode: 'create' | 'update'
  rule?: TimeRule
  relatedId?: string
  relatedType?: RuleRelatedType
  onSuccess: () => void
}) {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)

  const isAutoRule = rule?.tae_param1 === AUTO_TAG

  const defaultFormData: RuleFormData = {
    related_id: rule?.related_id?.toString() || relatedId || '',
    related_type: (rule?.related_type || relatedType || '业务') as RuleRelatedType,
    party: (rule?.party || '我方') as RuleParty,
    trigger_event: rule?.trigger_event || '',
    target_event: rule?.target_event || '',
    offset: rule?.offset?.toString() || '0',
    unit: (rule?.unit || '自然日') as RuleUnit,
    direction: (rule?.direction || 'after') as RuleDirection,
    inherit: rule?.inherit?.toString() || '0',
    tge_param1: rule?.tge_param1 || '',
    flag_time: rule?.flag_time?.split('T')[0] || '',
    prepayment_ratio: rule?.tge_param1?.replace('%', '') || '0',
  }

  const [formData, setFormData] = useState<RuleFormData>(defaultFormData)

  const createMutation = useMutation({
    mutationFn: () => {
      const inheritIdx = parseInt(formData.inherit)
      const status = inheritIdx === 0 ? '生效' : '模板'
      const payload: CreateTimeRuleSchema = {
        ...(mode === 'update' && rule ? { id: rule.id } : {}),
        related_id: parseInt(formData.related_id) || 0,
        related_type: formData.related_type,
        party: formData.party,
        trigger_event: formData.trigger_event,
        target_event: formData.target_event,
        offset: parseInt(formData.offset) || 0,
        unit: formData.unit,
        direction: formData.direction,
        inherit: inheritIdx as 0 | 1 | 2,
        status: status as '生效' | '模板',
        tge_param1: formData.trigger_event === '绝对日期' ? undefined : (formData.tge_param1 || undefined),
        tge_param2: undefined,
        tae_param1: formData.trigger_event === '绝对日期' ? '绝对日期' : undefined,
        tae_param2: undefined,
        flag_time: formData.trigger_event === '绝对日期' && formData.flag_time
          ? formData.flag_time + ' 00:00:00' : undefined,
      }
      return rulesApi.save(payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules-list'] })
      setIsOpen(false)
      onSuccess()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => rule ? rulesApi.delete(rule.id) : Promise.reject(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules-list'] })
      setIsOpen(false)
      onSuccess()
    },
  })

  const openDialog = () => {
    setFormData(defaultFormData)
    setIsOpen(true)
  }

  const availableEvents = getEventsForType(formData.related_type)
  const isAbsoluteDate = formData.trigger_event === '绝对日期'
  const isPrepayRatio = formData.target_event === '合同预付完成' && !isAbsoluteDate

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        {mode === 'create' ? (
          <Button><Plus className="mr-2 h-4 w-4" />新建规则</Button>
        ) : (
          <Button variant="ghost" size="sm"><Pencil className="h-4 w-4" /></Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {mode === 'create' ? '新建时间规则' : '编辑时间规则'}
            {formData.related_type && formData.related_id && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                — {formData.related_type} (ID: {formData.related_id})
              </span>
            )}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate() }} className="space-y-5">

          {/* 关联信息 */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>关联类型</Label>
              <Select
                value={formData.related_type}
                onValueChange={(v) => {
                  const rt = v as RuleRelatedType
                  setFormData({
                    ...formData,
                    related_type: rt,
                    inherit: getInheritOptions(rt)[0].value,
                    trigger_event: '',
                    target_event: '',
                  })
                }}
                disabled={mode === 'update'}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="业务">业务</SelectItem>
                  <SelectItem value="供应链">供应链</SelectItem>
                  <SelectItem value="虚拟合同">虚拟合同</SelectItem>
                  <SelectItem value="物流">物流</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>关联ID</Label>
              <Input
                type="number"
                value={formData.related_id}
                onChange={(e) => setFormData({ ...formData, related_id: e.target.value })}
                disabled={mode === 'update'}
              />
            </div>
          </div>

          {/* 触发事件 + 触发参数 */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>触发事件</Label>
              <Select value={formData.trigger_event} onValueChange={(v) => setFormData({ ...formData, trigger_event: v })}>
                <SelectTrigger><SelectValue placeholder="选择触发事件" /></SelectTrigger>
                <SelectContent>
                  {availableEvents.map(({ key, label }) => (
                    <SelectItem key={key} value={key}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {isAbsoluteDate ? (
              <div className="space-y-2">
                <Label>设定标杆日期</Label>
                <DatePicker
                  value={formData.flag_time}
                  onChange={(v) => setFormData({ ...formData, flag_time: v })}
                />
              </div>
            ) : isPrepayRatio ? (
              <div className="space-y-2">
                <Label>预付比例</Label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={parseInt(formData.prepayment_ratio) || 0}
                    onChange={(e) => {
                      const v = e.target.value
                      setFormData({ ...formData, prepayment_ratio: v, tge_param1: `${v}%` })
                    }}
                    className="flex-1"
                  />
                  <span className="text-sm w-10 text-right">{formData.prepayment_ratio}%</span>
                </div>
                <Input
                  placeholder="或直接输入（如 40%）"
                  value={formData.tge_param1}
                  onChange={(e) => setFormData({ ...formData, tge_param1: e.target.value })}
                  className="h-8"
                />
              </div>
            ) : (
              <div className="space-y-2">
                <Label>触发参数（选填）</Label>
                <Input value={formData.tge_param1} onChange={(e) => setFormData({ ...formData, tge_param1: e.target.value })} placeholder="如 0.4 或 40%" />
              </div>
            )}
          </div>

          {/* 目标事件 */}
          {!isAbsoluteDate && (
            <div className="grid grid-cols-1 gap-4">
              <div className="space-y-2">
                <Label>目标事件</Label>
                <Select value={formData.target_event} onValueChange={(v) => setFormData({ ...formData, target_event: v })}>
                  <SelectTrigger><SelectValue placeholder="选择目标事件" /></SelectTrigger>
                  <SelectContent>
                    {availableEvents.map(({ key, label }) => (
                      <SelectItem key={key} value={key}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {isAbsoluteDate && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>目标事件</Label>
                <Select value={formData.target_event} onValueChange={(v) => setFormData({ ...formData, target_event: v })}>
                  <SelectTrigger><SelectValue placeholder="选择目标事件" /></SelectTrigger>
                  <SelectContent>
                    {availableEvents.map(({ key, label }) => (
                      <SelectItem key={key} value={key}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          <Separator />

          {/* 偏移 / 单位 / 方向 / 责任方 */}
          <div className="grid grid-cols-4 gap-4">
            <div className="space-y-2">
              <Label>偏移量</Label>
              <Input type="number" value={formData.offset} onChange={(e) => setFormData({ ...formData, offset: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>单位</Label>
              <Select value={formData.unit} onValueChange={(v) => setFormData({ ...formData, unit: v as RuleUnit })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="自然日">自然日</SelectItem>
                  <SelectItem value="工作日">工作日</SelectItem>
                  <SelectItem value="小时">小时</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>方向</Label>
              <Select value={formData.direction} onValueChange={(v) => setFormData({ ...formData, direction: v as RuleDirection })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="after">之后</SelectItem>
                  <SelectItem value="before">之前</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>责任方</Label>
              <Select value={formData.party} onValueChange={(v) => setFormData({ ...formData, party: v as RuleParty })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="我方">我方</SelectItem>
                  <SelectItem value="客户">客户</SelectItem>
                  <SelectItem value="供应商">供应商</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* 作用范围 */}
          <div className="space-y-2">
            <Label>作用范围</Label>
            <Select value={formData.inherit} onValueChange={(v) => setFormData({ ...formData, inherit: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {getInheritOptions(formData.related_type).map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {formData.inherit === '0' ? '将自动设为"生效"' : '将自动设为"模板"，可被下级继承'}
            </p>
          </div>

          {/* Actions */}
          <div className="flex justify-between pt-2">
            <div>
              {mode === 'update' && rule && (
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending || isAutoRule}
                  title={isAutoRule ? '自动生成的规则不可删除' : undefined}
                >
                  <Trash2 className="mr-2 h-4 w-4" />删除
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={() => setIsOpen(false)}>取消</Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? '保存中...' : mode === 'create' ? '创建' : '保存'}
              </Button>
            </div>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Grouped Rules View ───────────────────────────────────────────────────────

type GroupedRules = Record<string, { entityName: string; rules: TimeRule[] }>

function useGroupedRules(rules: TimeRule[], entityNames: EntityNameCache, tab: string) {
  return useMemo(() => {
    const filtered = tab === 'ALL' ? rules : rules.filter(r => r.related_type === tab)

    const groups: GroupedRules = {}
    for (const rule of filtered) {
      const key = `${rule.related_type}-${rule.related_id}`
      if (!groups[key]) {
        groups[key] = {
          entityName: entityNames[key] || getEntityDisplayId(rule),
          rules: [],
        }
      }
      groups[key].rules.push(rule)
    }
    return Object.values(groups).sort((a, b) => {
      // Sort by first rule's related_type, then related_id
      const aRule = a.rules[0]
      const bRule = b.rules[0]
      if (aRule.related_type !== bRule.related_type) return aRule.related_type.localeCompare(bRule.related_type)
      return aRule.related_id - bRule.related_id
    })
  }, [rules, entityNames, tab])
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function TimeRulesPage() {
  const [entityFilter, setEntityFilter] = useState<RuleRelatedType | 'ALL'>('ALL')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')

  const { data: rulesData, isLoading, refetch } = useQuery({
    queryKey: ['rules-list', statusFilter],
    queryFn: () => rulesApi.list({ status: statusFilter !== 'ALL' ? statusFilter as any : undefined, size: 500 }),
  })

  const rules = rulesData?.items || []
  const entityNames = useEntityNames(rules)
  const grouped = useGroupedRules(rules, entityNames, entityFilter)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">时间规则</h2>
        <RuleFormDialog mode="create" onSuccess={() => refetch()} />
      </div>

      {/* Filter bar */}
      <div className="flex gap-3 flex-wrap items-center">
        <Select value={entityFilter} onValueChange={(v) => setEntityFilter(v as RuleRelatedType | 'ALL')}>
          <SelectTrigger className="w-28">
            <SelectValue placeholder="关联类型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">全部</SelectItem>
            <SelectItem value="业务">业务</SelectItem>
            <SelectItem value="供应链">供应链</SelectItem>
            <SelectItem value="虚拟合同">虚拟合同</SelectItem>
            <SelectItem value="物流">物流</SelectItem>
          </SelectContent>
        </Select>

        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-28">
            <SelectValue placeholder="状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">全部状态</SelectItem>
            <SelectItem value="模板">模板</SelectItem>
            <SelectItem value="生效">生效中</SelectItem>
            <SelectItem value="有结果">已触发</SelectItem>
            <SelectItem value="结束">已结束</SelectItem>
            <SelectItem value="失效">失效</SelectItem>
          </SelectContent>
        </Select>

        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" />
        </Button>

        <span className="text-sm text-muted-foreground">
          {rulesData?.total ?? 0} 条规则
        </span>
      </div>

      {/* Rules view */}
      {isLoading ? (
        <div className="text-center py-8 text-muted-foreground">加载中...</div>
      ) : grouped.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">暂无规则</div>
      ) : (
        <div className="space-y-6">
          {grouped.map(group => (
            <div key={`${group.rules[0].related_type}-${group.rules[0].related_id}`}>
              {/* Entity header */}
              <div className="flex items-center gap-2 mb-3">
                <Badge variant="outline">{group.rules[0].related_type}</Badge>
                <span className="font-medium text-sm">
                  {group.entityName}
                </span>
                <span className="text-xs text-muted-foreground">
                  ({group.rules.length} 条规则)
                </span>
              </div>
              {/* Rules grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {group.rules.map(rule => (
                  <RuleCard
                    key={rule.id}
                    rule={rule}
                    entityName={group.entityName}
                    onUpdate={() => refetch()}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
