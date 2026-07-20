import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from '../../App'

export default function ReplacementForm() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [formData, setFormData] = useState({
    projector_id: '',
    sku_id: '',
    from_office_id: '',
    replaced_at: (() => { const d=new Date(); const p=n=>n.toString().padStart(2,'0'); return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`; })(),
    notes: '',
    photos: []
  })
  const [projectors, setProjectors] = useState([])
  const [allBulbSkus, setAllBulbSkus] = useState([])
  const [filteredBulbSkus, setFilteredBulbSkus] = useState([])
  const [filteredOffices, setFilteredOffices] = useState([])
  const [allOffices, setAllOffices] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [projectorsRes, skusRes, officesRes] = await Promise.all([
        axios.get('/admin/projectors'),
        axios.get('/admin/skus?type=bulb'),
        axios.get('/admin/offices')
      ])
      setProjectors(projectorsRes.data.data || [])
      setAllBulbSkus(skusRes.data.data || [])
      setFilteredBulbSkus(skusRes.data.data || [])
      setAllOffices(officesRes.data.data || [])
      setFilteredOffices(officesRes.data.data || [])
    } catch (err) {
      console.error('加载数据失败', err)
    }
  }

  const handleProjectorChange = (projectorId) => {
    setFormData({ ...formData, projector_id: projectorId, sku_id: '', from_office_id: '' })
    if (!projectorId) {
      setFilteredBulbSkus(allBulbSkus)
      setFilteredOffices(allOffices)
      return
    }
    const projector = projectors.find(p => p.id === parseInt(projectorId))
    if (projector && projector.compatible_bulb_skus && projector.compatible_bulb_skus.length > 0) {
      setFilteredBulbSkus(allBulbSkus.filter(s => projector.compatible_bulb_skus.some(cb => cb.id === s.id)))
    } else {
      setFilteredBulbSkus(allBulbSkus)
    }
    setFilteredOffices(allOffices)
  }

  const handleBulbChange = async (skuId) => {
    if (!skuId) {
      setFormData({ ...formData, sku_id: '', from_office_id: '' })
      setFilteredOffices(allOffices)
      return
    }
    setFormData(prev => ({ ...prev, sku_id: skuId, from_office_id: '' }))
    try {
      const res = await axios.get(`/am/inventory?sku_type=bulb`)
      const inventory = res.data.data || []
      const officesWithStock = inventory
        .filter(i => i.sku_id === parseInt(skuId) && i.quantity > 0)
        .map(i => ({ id: i.office_id, name: i.office_name }))
      setFilteredOffices(officesWithStock)
      if (user?.office_id && officesWithStock.some(o => o.id === user.office_id)) {
        setFormData(prev => ({ ...prev, from_office_id: user.office_id }))
      }
    } catch (err) {
      console.error('加载库存失败', err)
      setFilteredOffices(allOffices)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await axios.post('/am/replacements', formData)
      alert('报备成功')
      navigate('/facility/replacements')
    } catch (err) {
      alert(err.response?.data?.message || '提交失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-6">报备灯泡更换</h1>

      <form onSubmit={handleSubmit} className="bg-white rounded-card shadow-card p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">投影仪 *</label>
          <select
            value={formData.projector_id}
            onChange={(e) => handleProjectorChange(e.target.value)}
            className="w-full border border-border rounded-input px-3 py-2"
            required
          >
            <option value="">选择投影仪</option>
            {projectors.map(p => (
              <option key={p.id} value={p.id}>
                {p.asset_code} - {p.meeting_room_name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">灯泡型号 *</label>
          <select
            value={formData.sku_id}
            onChange={(e) => handleBulbChange(e.target.value)}
            className="w-full border border-border rounded-input px-3 py-2"
            required
          >
            <option value="">选择灯泡型号</option>
            {filteredBulbSkus.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">灯泡来源 *</label>
          <select
            value={formData.from_office_id}
            onChange={(e) => setFormData({ ...formData, from_office_id: e.target.value })}
            className="w-full border border-border rounded-input px-3 py-2"
            required
          >
            <option value="">选择来源办公区</option>
            {filteredOffices.map(o => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">更换时间</label>
          <input
            type="datetime-local"
            value={formData.replaced_at}
            onChange={(e) => setFormData({ ...formData, replaced_at: e.target.value })}
            className="w-full border border-border rounded-input px-3 py-2"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">详细备注</label>
          <textarea
            value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            className="w-full border border-border rounded-input px-3 py-2 h-24"
            placeholder="请详细描述更换情况..."
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
            onClick={() => navigate('/facility')}
            className="flex-1 border border-border py-2 rounded-btn hover:bg-gray-50"
          >
            取消
          </button>
        </div>
      </form>
    </div>
  )
}
