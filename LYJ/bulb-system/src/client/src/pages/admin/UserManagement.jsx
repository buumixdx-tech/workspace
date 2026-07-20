import { useState, useEffect } from 'react'
import axios from 'axios'

export default function UserManagement() {
  const [users, setUsers] = useState([])
  const [offices, setOffices] = useState([])
  const [suppliers, setSuppliers] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [showPwdModal, setShowPwdModal] = useState(false)
  const [resetPwdUser, setResetPwdUser] = useState(null)
  const [newPassword, setNewPassword] = useState('')
  const [formData, setFormData] = useState({
    username: '', password: '', role: 'facility', real_name: '', phone: '', email: '', office_id: '', supplier_id: ''
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [usersRes, officesRes, suppliersRes] = await Promise.all([
        axios.get('/admin/users'),
        axios.get('/admin/offices'),
        axios.get('/admin/suppliers')
      ])
      setUsers(usersRes.data.data || [])
      setOffices(officesRes.data.data || [])
      setSuppliers(suppliersRes.data.data || [])
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  const openModal = (user = null) => {
    if (user) {
      setEditingUser(user)
      setFormData({
        username: user.username, password: '', role: user.role,
        real_name: user.real_name || '', phone: user.phone || '',
        email: user.email || '', office_id: user.office_id || '', supplier_id: user.supplier_id || ''
      })
    } else {
      setEditingUser(null)
      setFormData({ username: '', password: '', role: 'facility', real_name: '', phone: '', email: '', office_id: '', supplier_id: '' })
    }
    setShowModal(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingUser) {
        await axios.put(`/admin/users/${editingUser.id}`, formData)
      } else {
        await axios.post('/admin/users', formData)
      }
      setShowModal(false)
      loadData()
    } catch (err) {
      alert(err.response?.data?.message || '操作失败')
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除？')) return
    try {
      await axios.delete(`/admin/users/${id}`)
      loadData()
    } catch (err) {
      alert(err.response?.data?.message || '删除失败')
    }
  }

  const openPwdModal = (user) => {
    setResetPwdUser(user)
    setNewPassword('')
    setShowPwdModal(true)
  }

  const handleResetPwd = async (e) => {
    e.preventDefault()
    if (!resetPwdUser.username && !newPassword) {
      alert('用户名和密码不能同时为空')
      return
    }
    try {
      await axios.put(`/admin/users/${resetPwdUser.id}/password`, {
        username: resetPwdUser.username,
        password: newPassword
      })
      alert('重置成功')
      setShowPwdModal(false)
      loadData()
    } catch (err) {
      alert(err.response?.data?.message || '重置失败')
    }
  }

  const getRoleName = (role) => {
    const names = { admin: '管理员', asset_manager: '资产管理员', facility: '会服', supplier: '供应商' }
    return names[role] || role
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl font-bold text-text-primary">用户管理</h1>
        <button onClick={() => openModal()} className="bg-primary text-white px-4 py-2 rounded-btn hover:bg-blue-600">
          添加用户
        </button>
      </div>

      <div className="bg-white rounded-card shadow-card overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">用户名</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">姓名</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">角色</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">办公区</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">供应商</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">电话</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">邮箱</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-b border-border hover:bg-gray-50">
                <td className="px-4 py-3 text-sm">{u.username}</td>
                <td className="px-4 py-3 text-sm">{u.real_name || '-'}</td>
                <td className="px-4 py-3 text-sm">{getRoleName(u.role)}</td>
                <td className="px-4 py-3 text-sm">{u.office_name || '-'}</td>
                <td className="px-4 py-3 text-sm">{u.supplier_name || '-'}</td>
                <td className="px-4 py-3 text-sm">{u.phone || '-'}</td>
                <td className="px-4 py-3 text-sm">{u.email || '-'}</td>
                <td className="px-4 py-3 text-sm">
                  <button onClick={() => openModal(u)} className="text-primary mr-2">编辑</button>
                  <button onClick={() => openPwdModal(u)} className="text-warning mr-2">重置</button>
                  <button onClick={() => handleDelete(u.id)} className="text-danger">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-card p-6 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4">{editingUser ? '编辑用户' : '添加用户'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              {!editingUser && (
                <>
                  <div>
                    <label className="block text-sm mb-1">用户名（登录用，不填则无登录权限）</label>
                    <input type="text" value={formData.username} onChange={e => setFormData({...formData, username: e.target.value})}
                      className="w-full border border-border rounded-input px-3 py-2" disabled={!!editingUser} />
                  </div>
                  <div>
                    <label className="block text-sm mb-1">密码（登录用，不填则无登录权限）</label>
                    <input type="password" value={formData.password} onChange={e => setFormData({...formData, password: e.target.value})}
                      className="w-full border border-border rounded-input px-3 py-2" />
                  </div>
                </>
              )}
              <div>
                <label className="block text-sm mb-1">角色 *</label>
                <select value={formData.role} onChange={e => setFormData({...formData, role: e.target.value})}
                  className="w-full border border-border rounded-input px-3 py-2" required>
                  <option value="facility">会服</option>
                  <option value="asset_manager">资产管理员</option>
                  <option value="supplier">供应商</option>
                  <option value="admin">管理员</option>
                </select>
              </div>
              <div>
                <label className="block text-sm mb-1">姓名</label>
                <input type="text" value={formData.real_name} onChange={e => setFormData({...formData, real_name: e.target.value})}
                  className="w-full border border-border rounded-input px-3 py-2" />
              </div>
              <div>
                <label className="block text-sm mb-1">办公区</label>
                <select value={formData.office_id} onChange={e => setFormData({...formData, office_id: e.target.value})}
                  className="w-full border border-border rounded-input px-3 py-2">
                  <option value="">无</option>
                  {offices.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm mb-1">供应商</label>
                <select value={formData.supplier_id} onChange={e => setFormData({...formData, supplier_id: e.target.value})}
                  className="w-full border border-border rounded-input px-3 py-2">
                  <option value="">无</option>
                  {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm mb-1">电话</label>
                <input type="text" value={formData.phone} onChange={e => setFormData({...formData, phone: e.target.value})}
                  className="w-full border border-border rounded-input px-3 py-2" />
              </div>
              <div>
                <label className="block text-sm mb-1">邮箱</label>
                <input type="email" value={formData.email} onChange={e => setFormData({...formData, email: e.target.value})}
                  className="w-full border border-border rounded-input px-3 py-2" />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 bg-primary text-white py-2 rounded-btn">保存</button>
                <button type="button" onClick={() => setShowModal(false)} className="flex-1 border border-border py-2 rounded-btn">取消</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showPwdModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-card p-6 w-full max-w-sm">
            <h2 className="text-lg font-bold mb-4">重置登录信息</h2>
            <form onSubmit={handleResetPwd} className="space-y-4">
              <div>
                <label className="block text-sm mb-1">用户名</label>
                <input type="text" value={resetPwdUser?.username || ''} onChange={e => setResetPwdUser({...resetPwdUser, username: e.target.value})}
                  className="w-full border border-border rounded-input px-3 py-2" placeholder="不填则保留原用户名" />
              </div>
              <div>
                <label className="block text-sm mb-1">新密码</label>
                <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)}
                  className="w-full border border-border rounded-input px-3 py-2" placeholder="不填则保留原密码" />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 bg-primary text-white py-2 rounded-btn">保存</button>
                <button type="button" onClick={() => setShowPwdModal(false)} className="flex-1 border border-border py-2 rounded-btn">取消</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
