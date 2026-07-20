import { useState, useEffect } from 'react'
import axios from 'axios'

export default function SupplierManagement() {
  const [suppliers, setSuppliers] = useState([])
  const [users, setUsers] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editingSupplier, setEditingSupplier] = useState(null)
  const [formData, setFormData] = useState({ name: '', contact_user_id: '', address: '' })
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadData() }, [])
  const loadData = async () => {
    try {
      const [suppliersRes, usersRes] = await Promise.all([
        axios.get('/admin/suppliers'),
        axios.get('/admin/users')
      ])
      setSuppliers(suppliersRes.data.data || [])
      setUsers(usersRes.data.data || [])
    } catch (err) { console.error('加载失败', err) }
    finally { setLoading(false) }
  }

  const openModal = (supplier = null) => {
    setEditingSupplier(supplier)
    setFormData(supplier ? {
      name: supplier.name,
      contact_user_id: supplier.contact_user_id || '',
      address: supplier.address || ''
    } : { name: '', contact_user_id: '', address: '' })
    setShowModal(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingSupplier) { await axios.put(`/admin/suppliers/${editingSupplier.id}`, formData) }
      else { await axios.post('/admin/suppliers', formData) }
      setShowModal(false); loadData()
    } catch (err) { alert(err.response?.data?.message || '操作失败') }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除？')) return
    try { await axios.delete(`/admin/suppliers/${id}`); loadData() }
    catch (err) { alert(err.response?.data?.message || '删除失败') }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl font-bold text-text-primary">供应商管理</h1>
        <button onClick={() => openModal()} className="bg-primary text-white px-4 py-2 rounded-btn hover:bg-blue-600">添加供应商</button>
      </div>
      <div className="bg-white rounded-card shadow-card overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">名称</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">联系人</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">电话</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">邮箱</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">地址</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">操作</th>
            </tr>
          </thead>
          <tbody>
            {suppliers.map(s => (
              <tr key={s.id} className="border-b border-border hover:bg-gray-50">
                <td className="px-4 py-3 text-sm">{s.name}</td>
                <td className="px-4 py-3 text-sm">{s.contact_name || '-'}</td>
                <td className="px-4 py-3 text-sm">{s.contact_phone || '-'}</td>
                <td className="px-4 py-3 text-sm">{s.contact_email || '-'}</td>
                <td className="px-4 py-3 text-sm">{s.address || '-'}</td>
                <td className="px-4 py-3 text-sm">
                  <button onClick={() => openModal(s)} className="text-primary mr-2">编辑</button>
                  <button onClick={() => handleDelete(s.id)} className="text-danger">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-card p-6 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4">{editingSupplier ? '编辑供应商' : '添加供应商'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div><label className="block text-sm mb-1">名称 *</label><input type="text" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" required /></div>
              <div>
                <label className="block text-sm mb-1">联系人</label>
                <select value={formData.contact_user_id} onChange={e => setFormData({...formData, contact_user_id: e.target.value})} className="w-full border border-border rounded-input px-3 py-2">
                  <option value="">无</option>
                  {users.filter(u => u.role === 'supplier').map(u => (
                    <option key={u.id} value={u.id}>{u.real_name || u.username}</option>
                  ))}
                </select>
              </div>
              <div><label className="block text-sm mb-1">地址</label><input type="text" value={formData.address} onChange={e => setFormData({...formData, address: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" /></div>
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
