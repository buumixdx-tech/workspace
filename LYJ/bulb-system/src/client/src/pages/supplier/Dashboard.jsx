import { Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../../App'
import { useNavigate } from 'react-router-dom'

export default function SupplierDashboard() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [stats, setStats] = useState({ pending: 0, completed: 0 })

  useEffect(() => {
    const token = localStorage.getItem('token')
    const headers = { Authorization: `Bearer ${token}` }

    Promise.all([
      axios.get('/am/shipments?status=pending', { headers }),
      axios.get('/am/shipments?status=delivered', { headers }),
    ]).then(([pendingRes, completedRes]) => {
      setStats({
        pending: pendingRes.data.data?.length || 0,
        completed: completedRes.data.data?.length || 0,
      })
    }).catch(() => {})
  }, [])

  const menuItems = [
    { path: '/supplier/shipments/new', icon: '➕', label: '发起供货' },
    { path: '/supplier/shipments/pending', icon: '⏳', label: '待处理', badge: stats.pending },
    { path: '/supplier/shipments/completed', icon: '✅', label: '已完成' },
  ]

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text-primary">供应商工作台</h1>
        <button
          onClick={handleLogout}
          className="text-sm text-text-secondary hover:text-danger"
        >
          退出
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        {menuItems.map(item => (
          <Link
            key={item.path}
            to={item.path}
            className="bg-white rounded-card shadow-card p-4 flex flex-col items-center gap-2 hover:shadow-md transition-shadow relative"
          >
            <span className="text-3xl">{item.icon}</span>
            <span className="text-sm font-medium text-text-primary">{item.label}</span>
            {item.badge > 0 && (
              <span className="absolute top-2 right-2 bg-danger text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {item.badge}
              </span>
            )}
          </Link>
        ))}
      </div>

      <div className="bg-white rounded-card shadow-card p-4">
        <h2 className="font-semibold text-text-primary mb-3">快捷操作</h2>
        <ul className="text-sm text-text-secondary space-y-2">
          <li>• 点击「发起供货」创建新的供货单</li>
          <li>• 「待处理」显示尚未确认收货的供货单</li>
          <li>• 「已完成」显示已入库的供货历史记录</li>
        </ul>
      </div>
    </div>
  )
}
