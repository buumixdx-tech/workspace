import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'

export default function ShipmentCompleted() {
  const [shipments, setShipments] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const res = await axios.get('/am/shipments?status=delivered')
      setShipments(res.data.data || [])
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">已完成发货</h1>

      <div className="space-y-4">
        {loading ? (
          <div className="p-8 text-center text-text-secondary">加载中...</div>
        ) : shipments.length === 0 ? (
          <div className="bg-white rounded-card shadow-card p-8 text-center text-text-secondary">
            暂无已完成的发货
          </div>
        ) : (
          shipments.map(s => (
            <div key={s.id} className="bg-white rounded-card shadow-card p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">发往：{s.office_name}</p>
                  <p className="text-sm text-text-secondary">
                    {s.carrier && s.tracking_number ? `${s.carrier} ${s.tracking_number}` : '-'}
                  </p>
                  <p className="text-sm text-text-secondary">
                    {JSON.parse(s.items || '[]').map(i => `${i.sku_name} x${i.quantity}`).join(', ')}
                  </p>
                </div>
                <span className="text-success text-sm">✓ 已入库</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
