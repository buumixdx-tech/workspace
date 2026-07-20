import { useState, useEffect } from 'react'
import axios from 'axios'

export default function OfficeManagement() {
  const [offices, setOffices] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editingOffice, setEditingOffice] = useState(null)
  const [formData, setFormData] = useState({ name: '', location: '' })
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadData() }, [])
  const loadData = async () => {
    try { const res = await axios.get('/admin/offices'); setOffices(res.data.data || []) }
    catch (err) { console.error('加载失败', err) }
    finally { setLoading(false) }
  }

  const openModal = (office = null) => {
    setEditingOffice(office)
    setFormData(office ? { name: office.name, location: office.location || '' } : { name: '', location: '' })
    setShowModal(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingOffice) { await axios.put(`/admin/offices/${editingOffice.id}`, formData) }
      else { await axios.post('/admin/offices', formData) }
      setShowModal(false); loadData()
    } catch (err) { alert(err.response?.data?.message || '操作失败') }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除？')) return
    try { await axios.delete(`/admin/offices/${id}`); loadData() }
    catch (err) { alert(err.response?.data?.message || '删除失败') }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl font-bold text-text-primary">办公区管理</h1>
        <button onClick={() => openModal()} className="bg-primary text-white px-4 py-2 rounded-btn hover:bg-blue-600">添加办公区</button>
      </div>
      <div className="bg-white rounded-card shadow-card overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">名称</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">位置</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">操作</th>
            </tr>
          </thead>
          <tbody>
            {offices.map(o => (
              <tr key={o.id} className="border-b border-border hover:bg-gray-50">
                <td className="px-4 py-3 text-sm">{o.name}</td>
                <td className="px-4 py-3 text-sm">{o.location || '-'}</td>
                <td className="px-4 py-3 text-sm">
                  <button onClick={() => openModal(o)} className="text-primary mr-2">编辑</button>
                  <button onClick={() => handleDelete(o.id)} className="text-danger">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-card p-6 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4">{editingOffice ? '编辑办公区' : '添加办公区'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div><label className="block text-sm mb-1">名称 *</label><input type="text" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" required /></div>
              <div><label className="block text-sm mb-1">位置</label><input type="text" value={formData.location} onChange={e => setFormData({...formData, location: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" /></div>
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
