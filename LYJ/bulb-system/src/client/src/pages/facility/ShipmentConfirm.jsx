import { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../../App'

export default function ShipmentConfirm() {
  const { user } = useAuth()
  const [pending, setPending] = useState([])
  const [history, setHistory] = useState([])
  const [historyPage, setHistoryPage] = useState(1)
  const [historyTotal, setHistoryTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  const PAGE_SIZE = 10

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    loadHistory()
  }, [historyPage])

  const loadData = async () => {
    try {
      const res = await axios.get(`/am/shipments?office_id=${user.office_id}&status=pending`)
      setPending(res.data.data || [])
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  const loadHistory = async () => {
    try {
      const res = await axios.get(`/am/shipments?office_id=${user.office_id}&status=delivered&page=${historyPage}&page_size=${PAGE_SIZE}`)
      setHistory(res.data.data || [])
      setHistoryTotal(res.data.total || 0)
    } catch (err) {
      console.error('加载历史失败', err)
    }
  }

  const handleConfirm = async (id) => {
    if (!confirm('确认收货入库？')) return
    try {
      await axios.post(`/am/shipments/${id}/deliver`)
      alert('入库成功')
      loadData()
      loadHistory()
    } catch (err) {
      alert(err.response?.data?.message || '操作失败')
    }
  }

  const totalPages = Math.ceil(historyTotal / PAGE_SIZE)

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">确认入库</h1>

      {/* 待入库 */}
      <div className="bg-white rounded-card shadow-card overflow-hidden mb-6">
        <div className="px-4 py-3 bg-gray-50 border-b border-border">
          <h2 className="font-semibold text-text-primary">待入库</h2>
        </div>
        {loading ? (
          <div className="p-8 text-center text-text-secondary">加载中...</div>
        ) : pending.length === 0 ? (
          <div className="p-8 text-center text-text-secondary">暂无待入库的货物</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-border">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">供应商</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">快递</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">发货明细</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">操作</th>
              </tr>
            </thead>
            <tbody>
              {pending.map(s => (
                <tr key={s.id} className="border-b border-border hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{s.supplier_name}</td>
                  <td className="px-4 py-3 text-sm">
                    {s.carrier && s.tracking_number ? `${s.carrier} ${s.tracking_number}` : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {JSON.parse(s.items || '[]').map(i => `${i.sku_name} x${i.quantity}`).join(', ')}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <button
                      onClick={() => handleConfirm(s.id)}
                      className="bg-primary text-white px-3 py-1 rounded-btn text-sm hover:bg-blue-600"
                    >
                      确认入库
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 我的入库记录 */}
      <div className="bg-white rounded-card shadow-card overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b border-border">
          <h2 className="font-semibold text-text-primary">我的入库记录</h2>
        </div>
        {history.length === 0 ? (
          <div className="p-8 text-center text-text-secondary">暂无入库记录</div>
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-border">
                <tr>
                  <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">时间</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">供应商</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">快递</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">发货明细</th>
                </tr>
              </thead>
              <tbody>
                {history.map(s => (
                  <tr key={s.id} className="border-b border-border hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm">{s.created_at}</td>
                    <td className="px-4 py-3 text-sm">{s.supplier_name}</td>
                    <td className="px-4 py-3 text-sm">
                      {s.carrier && s.tracking_number ? `${s.carrier} ${s.tracking_number}` : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {JSON.parse(s.items || '[]').map(i => `${i.sku_name} x${i.quantity}`).join(', ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* 分页 */}
            {totalPages > 1 && (
              <div className="px-4 py-3 flex items-center justify-between border-t border-border">
                <span className="text-sm text-text-secondary">
                  共 {historyTotal} 条，第 {historyPage}/{totalPages} 页
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setHistoryPage(p => Math.max(1, p - 1))}
                    disabled={historyPage <= 1}
                    className="px-3 py-1 border border-border rounded-btn text-sm disabled:opacity-50 hover:bg-gray-50"
                  >
                    上一页
                  </button>
                  <button
                    onClick={() => setHistoryPage(p => Math.min(totalPages, p + 1))}
                    disabled={historyPage >= totalPages}
                    className="px-3 py-1 border border-border rounded-btn text-sm disabled:opacity-50 hover:bg-gray-50"
                  >
                    下一页
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
