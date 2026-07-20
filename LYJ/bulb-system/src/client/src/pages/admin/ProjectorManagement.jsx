import { useState, useEffect } from 'react'
import axios from 'axios'

export default function ProjectorManagement() {
  const [projectors, setProjectors] = useState([])
  const [meetingRooms, setMeetingRooms] = useState([])
  const [skus, setSkus] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editingProjector, setEditingProjector] = useState(null)
  const [formData, setFormData] = useState({ asset_code: '', meeting_room_id: '', sku_id: '', status: 'normal', notes: '' })
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadData() }, [])
  const loadData = async () => {
    try {
      const [projectorsRes, roomsRes, skusRes] = await Promise.all([axios.get('/admin/projectors'), axios.get('/admin/meeting-rooms'), axios.get('/admin/skus?type=projector')])
      setProjectors(projectorsRes.data.data || [])
      setMeetingRooms(roomsRes.data.data || [])
      setSkus(skusRes.data.data || [])
    } catch (err) { console.error('加载失败', err) }
    finally { setLoading(false) }
  }

  const openModal = (projector = null) => {
    setEditingProjector(projector)
    if (projector) {
      setFormData({ asset_code: projector.asset_code, meeting_room_id: projector.meeting_room_id || '', sku_id: projector.sku_id, status: projector.status, notes: projector.notes || '' })
    } else {
      setFormData({ asset_code: '', meeting_room_id: '', sku_id: '', status: 'normal', notes: '' })
    }
    setShowModal(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingProjector) { await axios.put(`/admin/projectors/${editingProjector.id}`, formData) }
      else { await axios.post('/admin/projectors', formData) }
      setShowModal(false); loadData()
    } catch (err) { alert(err.response?.data?.message || '操作失败') }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除？')) return
    try { await axios.delete(`/admin/projectors/${id}`); loadData() }
    catch (err) { alert(err.response?.data?.message || '删除失败') }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl font-bold text-text-primary">投影仪管理</h1>
        <button onClick={() => openModal()} className="bg-primary text-white px-4 py-2 rounded-btn hover:bg-blue-600">添加投影仪</button>
      </div>
      <div className="bg-white rounded-card shadow-card overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">资产编码</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">会议室</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">型号</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">状态</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">操作</th>
            </tr>
          </thead>
          <tbody>
            {projectors.map(p => (
              <tr key={p.id} className="border-b border-border hover:bg-gray-50">
                <td className="px-4 py-3 text-sm">{p.asset_code}</td>
                <td className="px-4 py-3 text-sm">{p.meeting_room_name || '-'}</td>
                <td className="px-4 py-3 text-sm">{p.sku_name}</td>
                <td className="px-4 py-3 text-sm"><span className={`px-2 py-1 rounded text-xs ${p.status === 'normal' ? 'bg-success text-white' : p.status === 'warning' ? 'bg-warning text-white' : 'bg-danger text-white'}`}>{p.status === 'normal' ? '正常' : p.status === 'warning' ? '警告' : '离线'}</span></td>
                <td className="px-4 py-3 text-sm">
                  <button onClick={() => openModal(p)} className="text-primary mr-2">编辑</button>
                  <button onClick={() => handleDelete(p.id)} className="text-danger">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-card p-6 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4">{editingProjector ? '编辑投影仪' : '添加投影仪'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div><label className="block text-sm mb-1">资产编码(6位) *</label><input type="text" value={formData.asset_code} onChange={e => setFormData({...formData, asset_code: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" required maxLength={6} disabled={!!editingProjector} /></div>
              <div><label className="block text-sm mb-1">会议室</label><select value={formData.meeting_room_id} onChange={e => setFormData({...formData, meeting_room_id: e.target.value})} className="w-full border border-border rounded-input px-3 py-2"><option value="">无</option>{meetingRooms.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></div>
              <div><label className="block text-sm mb-1">投影仪型号 *</label><select value={formData.sku_id} onChange={e => setFormData({...formData, sku_id: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" required><option value="">选择型号</option>{skus.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
              <div><label className="block text-sm mb-1">状态</label><select value={formData.status} onChange={e => setFormData({...formData, status: e.target.value})} className="w-full border border-border rounded-input px-3 py-2"><option value="normal">正常</option><option value="warning">警告</option><option value="offline">离线</option></select></div>
              <div><label className="block text-sm mb-1">备注</label><textarea value={formData.notes} onChange={e => setFormData({...formData, notes: e.target.value})} className="w-full border border-border rounded-input px-3 py-2 h-20" /></div>
              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 bg-primary text-white py-2 rounded-btn">保存</button>
                <button type="button" onClick={() => setShowModal(false)} className="flex-1 border border-border py-2 rounded-btn">取消</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
