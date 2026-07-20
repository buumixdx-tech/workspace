import { Link } from 'react-router-dom'
import { useAuth } from '../../App'
import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import axios from 'axios'

export default function AssetDashboard() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [alertCount, setAlertCount] = useState(0)
  const [todayReplacementCount, setTodayReplacementCount] = useState(0)
  const [stats, setStats] = useState({
    replacement: { today: 0, week: 0, month: 0 },
    shipment: { today: 0, week: 0, month: 0 }
  })

  useEffect(() => {
    // 获取告警数量
    axios.get('/am/inventory/office-alerts').then(res => {
      setAlertCount(res.data.data?.length || 0)
    }).catch(() => {})

    // 获取今日更换数量（角标用）
    const today = new Date()
    const pad = n => n.toString().padStart(2, '0')
    const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`
    axios.get(`/am/replacements?start_date=${todayStr}`).then(res => {
      setTodayReplacementCount(res.data.data?.length || 0)
    }).catch(() => {})

    // 获取统计数据（所有办公区）
    const now = new Date()
    const todayStr2 = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`

    // 本周第一天
    const weekDay = now.getDay() || 7
    const weekStart = new Date(now)
    weekStart.setDate(now.getDate() - weekDay + 1)
    const weekStartStr = `${weekStart.getFullYear()}-${pad(weekStart.getMonth() + 1)}-${pad(weekStart.getDate())}`

    // 本月第一天
    const monthStartStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-01`

    // 获取报备数量（不限办公区）
    axios.get(`/am/replacements?start_date=${todayStr2}`).then(res => {
      const todayCount = res.data.data?.length || 0
      setStats(prev => ({ ...prev, replacement: { ...prev.replacement, today: todayCount } }))
    }).catch(() => {})

    axios.get(`/am/replacements?start_date=${weekStartStr}`).then(res => {
      const weekCount = res.data.data?.length || 0
      setStats(prev => ({ ...prev, replacement: { ...prev.replacement, week: weekCount } }))
    }).catch(() => {})

    axios.get(`/am/replacements?start_date=${monthStartStr}`).then(res => {
      const monthCount = res.data.data?.length || 0
      setStats(prev => ({ ...prev, replacement: { ...prev.replacement, month: monthCount } }))
    }).catch(() => {})

    // 获取入库数量（不限办公区）
    axios.get(`/am/shipments?page_size=100`).then(res => {
      const shipments = res.data.data || []
      const deliveredShipments = shipments.filter(s => s.status === 'delivered')
      const deliveredData = deliveredShipments.map(s => ({
        ...s,
        storage_at: s.storage_at || s.updated_at
      }))

      const todayCount = deliveredData.filter(s => s.storage_at && s.storage_at.startsWith(todayStr2)).length
      const weekCount = deliveredData.filter(s => s.storage_at && s.storage_at >= weekStartStr).length
      const monthCount = deliveredData.filter(s => s.storage_at && s.storage_at >= monthStartStr).length

      setStats(prev => ({ ...prev, shipment: { today: todayCount, week: weekCount, month: monthCount } }))
    }).catch(() => {})
  }, [])

  const menuItems = [
    { path: '/am/inventory', icon: '📦', label: '全局库存' },
    { path: '/am/inventory/alerts', icon: '⚠️', label: '库存预警', badge: alertCount },
    { path: '/am/replacements', icon: '🔧', label: '更换记录', badge: todayReplacementCount },
    { path: '/am/shipments', icon: '🚚', label: '供货记录' },
    { path: '/am/reports', icon: '📈', label: '报表中心' },
  ]

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text-primary">资产管理工作台</h1>
        <button
          onClick={handleLogout}
          className="text-sm text-text-secondary hover:text-danger"
        >
          退出
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
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

      <div className="bg-white rounded-card shadow-card p-4">
        <h2 className="font-semibold text-text-primary mb-3">数据统计</h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-text-secondary mb-1">报备数量</p>
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <p className="text-lg font-bold text-primary">{stats.replacement.today}</p>
                <p className="text-xs text-text-secondary">今日</p>
              </div>
              <div>
                <p className="text-lg font-bold text-primary">{stats.replacement.week}</p>
                <p className="text-xs text-text-secondary">本周</p>
              </div>
              <div>
                <p className="text-lg font-bold text-primary">{stats.replacement.month}</p>
                <p className="text-xs text-text-secondary">本月</p>
              </div>
            </div>
          </div>
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-text-secondary mb-1">确认入库数量</p>
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <p className="text-lg font-bold text-primary">{stats.shipment.today}</p>
                <p className="text-xs text-text-secondary">今日</p>
              </div>
              <div>
                <p className="text-lg font-bold text-primary">{stats.shipment.week}</p>
                <p className="text-xs text-text-secondary">本周</p>
              </div>
              <div>
                <p className="text-lg font-bold text-primary">{stats.shipment.month}</p>
                <p className="text-xs text-text-secondary">本月</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
