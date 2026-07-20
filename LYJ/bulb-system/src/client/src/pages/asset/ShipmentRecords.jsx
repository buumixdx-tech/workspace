import { useState, useEffect } from 'react'
import axios from 'axios'

export default function ShipmentRecords() {
  const [shipments, setShipments] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const res = await axios.get('/am/shipments')
      setShipments(res.data.data || [])
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  const getStatusBadge = (status) => {
    const badges = {
      pending: { text: '待入库', class: 'bg-warning text-white' },
      delivered: { text: '已入库', class: 'bg-success text-white' }
    }
    const badge = badges[status] || { text: status, class: 'bg-gray-400 text-white' }
    return <span className={`px-2 py-1 rounded text-xs ${badge.class}`}>{badge.text}</span>
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">供货记录</h1>

      <div className="bg-white rounded-card shadow-card overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-text-secondary">加载中...</div>
        ) : shipments.length === 0 ? (
          <div className="p-8 text-center text-text-secondary">暂无记录</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-border">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">供应商</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">收货办公区</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">快递信息</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">状态</th>
              </tr>
            </thead>
            <tbody>
              {shipments.map(s => (
                <tr key={s.id} className="border-b border-border hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{s.supplier_name}</td>
                  <td className="px-4 py-3 text-sm">{s.office_name}</td>
                  <td className="px-4 py-3 text-sm">
                    {s.carrier && s.tracking_number ? `${s.carrier} ${s.tracking_number}` : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">{getStatusBadge(s.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
