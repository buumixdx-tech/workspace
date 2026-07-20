import { useState, useEffect } from 'react'
import axios from 'axios'

export default function MeetingRoomManagement() {
  const [rooms, setRooms] = useState([])
  const [offices, setOffices] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editingRoom, setEditingRoom] = useState(null)
  const [formData, setFormData] = useState({ office_id: '', name: '', floor: '', capacity_normal: '', capacity_max: '' })
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadData() }, [])
  const loadData = async () => {
    try {
      const [roomsRes, officesRes] = await Promise.all([axios.get('/admin/meeting-rooms'), axios.get('/admin/offices')])
      setRooms(roomsRes.data.data || [])
      setOffices(officesRes.data.data || [])
    } catch (err) { console.error('加载失败', err) }
    finally { setLoading(false) }
  }

  const openModal = (room = null) => {
    setEditingRoom(room)
    setFormData(room ? { office_id: room.office_id, name: room.name, floor: room.floor || '', capacity_normal: room.capacity_normal || '', capacity_max: room.capacity_max || '' } : { office_id: '', name: '', floor: '', capacity_normal: '', capacity_max: '' })
    setShowModal(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingRoom) { await axios.put(`/admin/meeting-rooms/${editingRoom.id}`, formData) }
      else { await axios.post('/admin/meeting-rooms', formData) }
      setShowModal(false); loadData()
    } catch (err) { alert(err.response?.data?.message || '操作失败') }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除？')) return
    try { await axios.delete(`/admin/meeting-rooms/${id}`); loadData() }
    catch (err) { alert(err.response?.data?.message || '删除失败') }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl font-bold text-text-primary">会议室管理</h1>
        <button onClick={() => openModal()} className="bg-primary text-white px-4 py-2 rounded-btn hover:bg-blue-600">添加会议室</button>
      </div>
      <div className="bg-white rounded-card shadow-card overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">名称</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">办公区</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">楼层</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">容纳人数</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">操作</th>
            </tr>
          </thead>
          <tbody>
            {rooms.map(r => (
              <tr key={r.id} className="border-b border-border hover:bg-gray-50">
                <td className="px-4 py-3 text-sm">{r.name}</td>
                <td className="px-4 py-3 text-sm">{r.office_name}</td>
                <td className="px-4 py-3 text-sm">{r.floor || '-'}</td>
                <td className="px-4 py-3 text-sm">{r.capacity_normal || '-'}{r.capacity_max ? `/${r.capacity_max}` : ''}</td>
                <td className="px-4 py-3 text-sm">
                  <button onClick={() => openModal(r)} className="text-primary mr-2">编辑</button>
                  <button onClick={() => handleDelete(r.id)} className="text-danger">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-card p-6 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4">{editingRoom ? '编辑会议室' : '添加会议室'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div><label className="block text-sm mb-1">所属办公区 *</label><select value={formData.office_id} onChange={e => setFormData({...formData, office_id: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" required><option value="">选择办公区</option>{offices.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></div>
              <div><label className="block text-sm mb-1">名称 *</label><input type="text" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" required /></div>
              <div><label className="block text-sm mb-1">楼层</label><input type="text" value={formData.floor} onChange={e => setFormData({...formData, floor: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" /></div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-sm mb-1">正常容纳人数</label><input type="number" value={formData.capacity_normal} onChange={e => setFormData({...formData, capacity_normal: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" /></div>
                <div><label className="block text-sm mb-1">最大容纳人数</label><input type="number" value={formData.capacity_max} onChange={e => setFormData({...formData, capacity_max: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" /></div>
              </div>
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
