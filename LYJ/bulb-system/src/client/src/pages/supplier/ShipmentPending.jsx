import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'

export default function ShipmentPending() {
  const [shipments, setShipments] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const res = await axios.get('/am/shipments?status=pending')
      setShipments(res.data.data || [])
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">待处理发货</h1>

      <div className="space-y-4">
        {loading ? (
          <div className="p-8 text-center text-text-secondary">加载中...</div>
        ) : shipments.length === 0 ? (
          <div className="bg-white rounded-card shadow-card p-8 text-center text-text-secondary">
            暂无待处理的发货
          </div>
        ) : (
          shipments.map(s => (
            <Link
              key={s.id}
              to={`/supplier/shipments/${s.id}`}
              className="block bg-white rounded-card shadow-card p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">发往：{s.office_name}</p>
                  <p className="text-sm text-text-secondary">
                    {JSON.parse(s.items || '[]').map(i => `${i.sku_name} x${i.quantity}`).join(', ')}
                  </p>
                </div>
                <span className="text-primary">编辑 →</span>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}
