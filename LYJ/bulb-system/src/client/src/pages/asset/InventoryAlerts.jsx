import { useState, useEffect } from 'react'
import axios from 'axios'

export default function InventoryAlerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const res = await axios.get('/am/inventory/office-alerts')
      setAlerts(res.data.data || [])
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">库存警戒</h1>

      <div className="space-y-4">
        {loading ? (
          <div className="p-8 text-center text-text-secondary">加载中...</div>
        ) : alerts.length === 0 ? (
          <div className="bg-white rounded-card shadow-card p-8 text-center text-text-secondary">
            目前没有库存警戒
          </div>
        ) : (
          alerts.map(item => (
            <div key={item.office_id} className="bg-white rounded-card shadow-card p-4 flex items-center gap-4">
              <span className="text-2xl">⚠️</span>
              <div className="flex-1">
                <p className="font-medium">{item.office_name}</p>
                <p className="text-sm text-text-secondary">灯泡库存不足</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-danger">{item.total_bulb_quantity}</p>
                <p className="text-sm text-text-secondary">当前库存</p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
