import { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../../App'

export default function InventoryAlerts() {
  const { user } = useAuth()
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

  const localAlert = alerts.find(a => a.office_id === user?.office_id)
  const globalAlerts = alerts.filter(a => a.office_id !== user?.office_id)

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">库存警戒</h1>

      {loading ? (
        <div className="p-8 text-center text-text-secondary">加载中...</div>
      ) : (
        <div className="space-y-6">
          {/* 本区状态 */}
          <div>
            <h2 className="text-lg font-semibold text-text-primary mb-3">本区状态</h2>
            {localAlert ? (
              <div className="bg-white rounded-card shadow-card p-4 flex items-center gap-4 border-2 border-danger">
                <span className="text-2xl">⚠️</span>
                <div className="flex-1">
                  <p className="font-medium">{localAlert.office_name} <span className="text-xs text-danger">(本设施)</span></p>
                  <p className="text-sm text-text-secondary">灯泡库存不足</p>
                </div>
                <div className="text-right">
                  <p className="text-lg font-bold text-danger">{localAlert.total_bulb_quantity}</p>
                  <p className="text-sm text-text-secondary">当前库存</p>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-card shadow-card p-4 flex items-center gap-4">
                <span className="text-2xl">✅</span>
                <div className="flex-1">
                  <p className="font-medium">{user?.office_name} <span className="text-xs text-text-secondary">(本设施)</span></p>
                  <p className="text-sm text-text-secondary">本区无预警</p>
                </div>
                <div className="text-right text-text-secondary">
                  <p className="text-lg font-semibold">-</p>
                </div>
              </div>
            )}
          </div>

          {/* 其他办公区 */}
          {globalAlerts.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-text-primary mb-3">其他办公区</h2>
              <div className="space-y-4">
                {globalAlerts.map(item => (
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
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
