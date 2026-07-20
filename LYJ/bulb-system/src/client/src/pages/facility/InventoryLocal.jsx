import { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../../App'

export default function InventoryLocal() {
  const { user } = useAuth()
  const [inventory, setInventory] = useState([])
  const [loading, setLoading] = useState(true)
  const [isAlert, setIsAlert] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [invRes, alertRes] = await Promise.all([
        axios.get(`/am/inventory?office_id=${user.office_id}`),
        axios.get('/am/inventory/office-alerts')
      ])
      setInventory(invRes.data.data || [])
      const alerts = alertRes.data.data || []
      setIsAlert(alerts.some(a => a.office_id === user.office_id))
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">本区库存</h1>

      <div className={`bg-white rounded-card shadow-card overflow-hidden ${isAlert ? 'border-2 border-danger' : ''}`}>
        {isAlert && (
          <div className="px-4 py-2 bg-red-50 border-b border-danger flex items-center gap-2 text-sm text-danger">
            <span>⚠️</span>
            <span>本设施灯泡库存不足</span>
          </div>
        )}
        {loading ? (
          <div className="p-8 text-center text-text-secondary">加载中...</div>
        ) : inventory.length === 0 ? (
          <div className="p-8 text-center text-text-secondary">暂无库存数据</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-border">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">SKU</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">数量</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">警戒线</th>
              </tr>
            </thead>
            <tbody>
              {inventory.map(item => (
                <tr key={item.sku_id} className="border-b border-border hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{item.sku_name}</td>
                  <td className="px-4 py-3 text-sm">
                    <span className={item.quantity <= item.min_stock ? 'text-danger' : ''}>
                      {item.quantity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">{item.min_stock || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
