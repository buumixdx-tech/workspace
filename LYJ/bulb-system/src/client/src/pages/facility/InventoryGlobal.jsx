import { useState, useEffect } from 'react'
import axios from 'axios'

export default function InventoryGlobal() {
  const [inventory, setInventory] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [invRes, alertRes] = await Promise.all([
        axios.get('/am/inventory'),
        axios.get('/am/inventory/office-alerts')
      ])
      setInventory(invRes.data.data || [])
      setAlerts(alertRes.data.data || [])
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  const alertOfficeIds = new Set(alerts.map(a => a.office_id))

  // Group by office
  const grouped = inventory.reduce((acc, item) => {
    if (!acc[item.office_id]) {
      acc[item.office_id] = { name: item.office_name, items: [] }
    }
    acc[item.office_id].items.push(item)
    return acc
  }, {})

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">全局库存</h1>

      {loading ? (
        <div className="p-8 text-center text-text-secondary">加载中...</div>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="p-8 text-center text-text-secondary">暂无数据</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(grouped).map(([officeId, office]) => {
            const isAlert = alertOfficeIds.has(Number(officeId))
            return (
              <div key={officeId} className={`bg-white rounded-card shadow-card overflow-hidden ${isAlert ? 'border-2 border-danger' : ''}`}>
                <div className={`px-4 py-3 border-b border-border ${isAlert ? 'bg-red-50' : 'bg-gray-50'}`}>
                  <h2 className="font-semibold text-text-primary flex items-center gap-2">
                    {isAlert && <span>⚠️</span>}
                    {office.name}
                    {isAlert && <span className="text-xs text-danger font-normal">库存不足</span>}
                  </h2>
                </div>
                <div className="divide-y divide-border">
                  {office.items.map(item => (
                    <div key={`${item.office_id}-${item.sku_id}`} className="px-4 py-3 flex items-center justify-between">
                      <div>
                        <div className="text-sm font-medium text-text-primary">{item.sku_name}</div>
                        <div className="text-xs text-text-secondary">{item.sku_type === 'bulb' ? '灯泡' : '投影仪'}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-semibold">{item.quantity}</div>
                        {item.min_stock != null && (
                          <div className={`text-xs ${item.quantity <= item.min_stock ? 'text-danger' : 'text-text-secondary'}`}>
                            警戒: {item.min_stock}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
