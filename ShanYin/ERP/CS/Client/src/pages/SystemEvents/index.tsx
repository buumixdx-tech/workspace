import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { rulesApi, SystemEvent } from '@/api/endpoints/rules'
import { formatDate } from '@/lib/utils'

const EVENT_TYPE_OPTIONS = [
  { value: 'RULE_UPDATED', label: '规则更新' },
  { value: 'RULE_DELETED', label: '规则删除' },
  { value: 'RULES_TRIGGERED_BY_LOGISTICS', label: '物流触发规则' },
  { value: 'BUSINESS_STATUS_CHANGED', label: '业务状态变更' },
  { value: 'BUSINESS_STAGE_ADVANCED', label: '业务阶段推进' },
  { value: 'BUSINESS_CREATED', label: '业务创建' },
  { value: 'VC_CREATED', label: 'VC创建' },
  { value: 'VC_STATUS_CHANGED', label: 'VC状态变更' },
  { value: 'LOGISTICS_STATUS_CHANGED', label: '物流状态变更' },
  { value: 'SUPPLY_CHAIN_CREATED', label: '供应链创建' },
  { value: 'SUPPLY_CHAIN_UPDATED', label: '供应链更新' },
]

const AGGREGATE_TYPE_OPTIONS = [
  { value: 'Business', label: '业务' },
  { value: 'VirtualContract', label: '虚拟合同' },
  { value: 'SupplyChain', label: '供应链' },
  { value: 'Logistics', label: '物流' },
  { value: 'TimeRule', label: '时间规则' },
  { value: 'ExternalPartner', label: '外部合作方' },
]

const EVENT_TYPE_COLORS: Record<string, string> = {
  'RULE_UPDATED': 'bg-blue-50 text-blue-600',
  'RULE_DELETED': 'bg-red-50 text-red-600',
  'RULES_TRIGGERED_BY_LOGISTICS': 'bg-green-50 text-green-600',
  'BUSINESS_STATUS_CHANGED': 'bg-purple-50 text-purple-600',
  'BUSINESS_STAGE_ADVANCED': 'bg-purple-50 text-purple-600',
  'BUSINESS_CREATED': 'bg-gray-50 text-gray-600',
  'VC_CREATED': 'bg-orange-50 text-orange-600',
  'VC_STATUS_CHANGED': 'bg-orange-50 text-orange-600',
  'LOGISTICS_STATUS_CHANGED': 'bg-cyan-50 text-cyan-600',
  'SUPPLY_CHAIN_CREATED': 'bg-yellow-50 text-yellow-700',
  'SUPPLY_CHAIN_UPDATED': 'bg-yellow-50 text-yellow-700',
}

const PAGE_SIZE = 20

export function SystemEventsPage() {
  const [page, setPage] = useState(1)
  const [eventType, setEventType] = useState<string>('')
  const [aggregateType, setAggregateType] = useState<string>('')

  const { data: resp, isLoading, refetch } = useQuery({
    queryKey: ['system-events', page, eventType, aggregateType],
    queryFn: () => rulesApi.getRecentEvents(
      page,
      PAGE_SIZE,
      eventType || undefined,
      aggregateType || undefined
    ),
  })

  const events: SystemEvent[] = resp?.items || []
  const total = resp?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const handleFilterChange = () => {
    setPage(1)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">系统事件</h2>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-1" />
          刷新
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap items-center">
        <Select value={eventType} onValueChange={(v) => { setEventType(v); handleFilterChange() }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="事件类型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">全部事件类型</SelectItem>
            {EVENT_TYPE_OPTIONS.map(opt => (
              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={aggregateType} onValueChange={(v) => { setAggregateType(v); handleFilterChange() }}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="聚合对象" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">全部对象</SelectItem>
            {AGGREGATE_TYPE_OPTIONS.map(opt => (
              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        {(eventType || aggregateType) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setEventType(''); setAggregateType(''); setPage(1) }}
          >
            清除筛选
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-muted-foreground">加载中...</div>
      ) : events.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">暂无事件</div>
      ) : (
        <>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>时间</TableHead>
                    <TableHead>事件类型</TableHead>
                    <TableHead>聚合对象</TableHead>
                    <TableHead>载荷</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map(event => (
                    <TableRow key={event.id}>
                      <TableCell className="text-sm whitespace-nowrap">
                        {formatDate(event.created_at || event.timestamp || '')}
                      </TableCell>
                      <TableCell>
                        <Badge className={EVENT_TYPE_COLORS[event.event_type] || 'bg-gray-50 text-gray-600'}>
                          {EVENT_TYPE_OPTIONS.find(o => o.value === event.event_type)?.label || event.event_type}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {event.aggregate_type && event.aggregate_id ? (
                          <div className="flex items-center gap-1">
                            <Badge variant="outline">
                              {AGGREGATE_TYPE_OPTIONS.find(o => o.value === event.aggregate_type)?.label || event.aggregate_type}
                            </Badge>
                            <span className="text-sm text-muted-foreground">#{event.aggregate_id}</span>
                          </div>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                        {event.payload ? JSON.stringify(event.payload) : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              共 {total} 条，第 {page}/{totalPages} 页
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                <ChevronLeft className="h-4 w-4" />
                上一页
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                下一页
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
