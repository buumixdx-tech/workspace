import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

export default function ShipmentForm() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    office_id: '',
    recipient_id: '',
    carrier: '',
    tracking_number: '',
    items: [{ sku_id: '', quantity: 1 }],
    notes: ''
  })
  const [offices, setOffices] = useState([])
  const [skus, setSkus] = useState([])
  const [facilityUsers, setFacilityUsers] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [officesRes, skusRes, facilityRes] = await Promise.all([
        axios.get('/admin/offices'),
        axios.get('/admin/skus?type=bulb'),
        axios.get('/admin/users?role=facility')
      ])
      setOffices(officesRes.data.data || [])
      setSkus(skusRes.data.data || [])
      setFacilityUsers(facilityRes.data.data || [])
    } catch (err) {
      console.error('加载数据失败', err)
    }
  }

  const handleItemChange = (index, field, value) => {
    const newItems = [...formData.items]
    newItems[index][field] = value
    setFormData({ ...formData, items: newItems })
  }

  const addItem = () => {
    setFormData({
      ...formData,
      items: [...formData.items, { sku_id: '', quantity: 1 }]
    })
  }

  const removeItem = (index) => {
    if (formData.items.length > 1) {
      const newItems = formData.items.filter((_, i) => i !== index)
      setFormData({ ...formData, items: newItems })
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const submitData = {
        ...formData,
        items: formData.items.filter(i => i.sku_id && i.quantity > 0)
      }
      await axios.post('/am/shipments', submitData)
      alert('提交成功')
      navigate('/supplier/shipments/pending')
    } catch (err) {
      alert(err.response?.data?.message || '提交失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-6">发起供货</h1>

      <form onSubmit={handleSubmit} className="bg-white rounded-card shadow-card p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">收货办公区 *</label>
          <select
            value={formData.office_id}
            onChange={(e) => setFormData({ ...formData, office_id: e.target.value })}
            className="w-full border border-border rounded-input px-3 py-2"
            required
          >
            <option value="">选择办公区</option>
            {offices.map(o => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">收货人</label>
          <select
            value={formData.recipient_id}
            onChange={(e) => setFormData({ ...formData, recipient_id: e.target.value })}
            className="w-full border border-border rounded-input px-3 py-2"
          >
            <option value="">选择收货人</option>
            {facilityUsers.map(u => (
              <option key={u.id} value={u.id}>{u.real_name} - {u.office_name || '无办公区'}</option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
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
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">发货明细 *</label>
          {formData.items.map((item, index) => (
            <div key={index} className="flex gap-2 mb-2">
              <select
                value={item.sku_id}
                onChange={(e) => handleItemChange(index, 'sku_id', e.target.value)}
                className="flex-1 border border-border rounded-input px-3 py-2"
                required
              >
                <option value="">选择SKU</option>
                {skus.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
              <input
                type="number"
                value={item.quantity}
                onChange={(e) => handleItemChange(index, 'quantity', parseInt(e.target.value) || 1)}
                className="w-20 border border-border rounded-input px-3 py-2"
                min="1"
                required
              />
              {formData.items.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeItem(index)}
                  className="text-danger px-2"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            onClick={addItem}
            className="text-primary text-sm"
          >
            + 添加物品
          </button>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">备注</label>
          <textarea
            value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            className="w-full border border-border rounded-input px-3 py-2 h-20"
            placeholder="备注信息..."
          />
        </div>

        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            disabled={loading}
            className="flex-1 bg-primary text-white py-2 rounded-btn hover:bg-blue-600 disabled:opacity-50"
          >
            {loading ? '提交中...' : '提交'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/supplier')}
            className="flex-1 border border-border py-2 rounded-btn hover:bg-gray-50"
          >
            取消
          </button>
        </div>
      </form>
    </div>
  )
}
