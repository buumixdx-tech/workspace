import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'

export default function ShipmentEdit() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    carrier: '',
    tracking_number: '',
    notes: ''
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadData()
  }, [id])

  const loadData = async () => {
    try {
      const res = await axios.get(`/am/shipments/${id}`)
      const s = res.data.data
      setFormData({
        carrier: s.carrier || '',
        tracking_number: s.tracking_number || '',
        notes: s.notes || ''
      })
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await axios.put(`/am/shipments/${id}/tracking`, formData)
      alert('保存成功')
      navigate('/supplier/shipments/pending')
    } catch (err) {
      alert(err.response?.data?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="p-8 text-center">加载中...</div>
  }

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-6">编辑发货信息</h1>

      <form onSubmit={handleSubmit} className="bg-white rounded-card shadow-card p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">快递公司</label>
          <input
            type="text"
            value={formData.carrier}
            onChange={(e) => setFormData({ ...formData, carrier: e.target.value })}
            className="w-full border border-border rounded-input px-3 py-2"
            placeholder="顺丰"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">快递单号</label>
          <input
            type="text"
            value={formData.tracking_number}
            onChange={(e) => setFormData({ ...formData, tracking_number: e.target.value })}
            className="w-full border border-border rounded-input px-3 py-2"
            placeholder="SF123456789"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">备注</label>
          <textarea
            value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            className="w-full border border-border rounded-input px-3 py-2 h-20"
          />
        </div>

        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            disabled={saving}
            className="flex-1 bg-primary text-white py-2 rounded-btn hover:bg-blue-600 disabled:opacity-50"
          >
            {saving ? '保存中...' : '保存'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/supplier/shipments/pending')}
            className="flex-1 border border-border py-2 rounded-btn hover:bg-gray-50"
          >
            取消
          </button>
        </div>
      </form>
    </div>
  )
}
