import { useState, useEffect } from 'react'
import axios from 'axios'

export default function ReplacementRecords() {
  const [replacements, setReplacements] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const res = await axios.get('/am/replacements')
      setReplacements(res.data.data || [])
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">更换记录</h1>

      <div className="bg-white rounded-card shadow-card overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-text-secondary">加载中...</div>
        ) : replacements.length === 0 ? (
          <div className="p-8 text-center text-text-secondary">暂无记录</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-border">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">时间</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">投影仪</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">灯泡</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">来源</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">操作人</th>
              </tr>
            </thead>
            <tbody>
              {replacements.map(r => (
                <tr key={r.id} className="border-b border-border hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{r.replaced_at}</td>
                  <td className="px-4 py-3 text-sm">{r.projector_code}</td>
                  <td className="px-4 py-3 text-sm">{r.sku_name}</td>
                  <td className="px-4 py-3 text-sm">{r.from_office_name}</td>
                  <td className="px-4 py-3 text-sm">{r.operator_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
