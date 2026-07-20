import { Link } from 'react-router-dom'
import { useAuth } from '../../App'
import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import axios from 'axios'

export default function AdminDashboard() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [alertCount, setAlertCount] = useState(0)
  const [todayReplacementCount, setTodayReplacementCount] = useState(0)

  useEffect(() => {
    // 获取告警数量
    axios.get('/am/inventory/office-alerts').then(res => {
      setAlertCount(res.data.data?.length || 0)
    }).catch(() => {})

    // 获取今日更换数量
    const today = new Date()
    const pad = n => n.toString().padStart(2, '0')
    const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`
    axios.get(`/am/replacements?start_date=${todayStr}`).then(res => {
      setTodayReplacementCount(res.data.data?.length || 0)
    }).catch(() => {})
  }, [])

  const menuItems = [
    { path: '/am/inventory', icon: '📦', label: '库存' },
    { path: '/am/replacements', icon: '🔧', label: '更换记录', badge: todayReplacementCount },
    { path: '/am/shipments', icon: '🚚', label: '供货记录' },
    { path: '/admin/users', icon: '👥', label: '用户管理' },
    { path: '/admin/offices', icon: '🏢', label: '办公区' },
    { path: '/admin/meeting-rooms', icon: '🚪', label: '会议室' },
    { path: '/admin/projectors', icon: '📽️', label: '投影仪' },
    { path: '/admin/skus', icon: '📦', label: 'SKU' },
    { path: '/admin/suppliers', icon: '🚚', label: '供应商' },
    { path: '/admin/import', icon: '📥', label: '数据导入' },
    { path: '/am/inventory/alerts', icon: '⚠️', label: '库存预警', badge: alertCount },
  ]

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text-primary">系统管理</h1>
        <button
          onClick={handleLogout}
          className="text-sm text-text-secondary hover:text-danger"
        >
          退出
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {menuItems.map(item => (
          <Link
            key={item.path}
            to={item.path}
            className="bg-white rounded-card shadow-card p-4 flex flex-col items-center justify-center gap-2 hover:shadow-md transition-shadow relative"
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
    </div>
  )
}
