import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../App'

export default function DashboardLayout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const getNavItems = () => {
    const base = []
    if (user.role === 'admin') {
      return [
        { path: '/admin', label: '首页', icon: '📊' },
        { path: '/admin/users', label: '用户', icon: '👥' },
        { path: '/am/inventory', label: '库存', icon: '📦' },
        { path: '/am/inventory/alerts', label: '预警', icon: '⚠️' },
        { path: '/am/replacements', label: '更换记录', icon: '🔧' },
        { path: '/am/shipments', label: '供货记录', icon: '🚚' },
        { path: '/admin/offices', label: '办公区', icon: '🏢' },
        { path: '/admin/meeting-rooms', label: '会议室', icon: '🚪' },
        { path: '/admin/projectors', label: '投影仪', icon: '📽️' },
        { path: '/admin/skus', label: 'SKU', icon: '📦' },
        { path: '/admin/suppliers', label: '供应商', icon: '🚚' },
        { path: '/admin/import', label: '导入导出', icon: '📥' },
      ]
    }
    if (user.role === 'asset_manager') {
      return [
        { path: '/am', label: '首页', icon: '📊' },
        { path: '/am/inventory', label: '库存', icon: '📦' },
        { path: '/am/inventory/alerts', label: '预警', icon: '⚠️' },
        { path: '/am/replacements', label: '更换记录', icon: '🔧' },
        { path: '/am/shipments', label: '供货记录', icon: '🚚' },
        { path: '/am/reports', label: '报表', icon: '📈' },
      ]
    }
    if (user.role === 'facility') {
      return [
        { path: '/facility', label: '首页', icon: '📊' },
        { path: '/facility/replacements/new', label: '报备', icon: '📝' },
        { path: '/facility/inventory', label: '库存', icon: '📦' },
        { path: '/facility/shipments', label: '入库', icon: '📥' },
        { path: '/facility/inventory/alerts', label: '预警', icon: '⚠️' },
        { path: '/facility/replacements', label: '记录', icon: '📋' },
        { path: '/facility/inventory/global', label: '全局', icon: '🌍' },
        { path: '/facility/projectors', label: '投影仪', icon: '📽️' },
      ]
    }
    if (user.role === 'supplier') {
      return [
        { path: '/supplier', label: '首页', icon: '📊' },
        { path: '/supplier/shipments/new', label: '供货', icon: '➕' },
        { path: '/supplier/shipments/pending', label: '待处理', icon: '⏳' },
        { path: '/supplier/shipments/completed', label: '已完成', icon: '✅' },
      ]
    }
    return []
  }

  const navItems = getNavItems()

  return (
    <div className="min-h-screen flex">
      {/* 侧边栏 - PC 端 */}
      <aside className="hidden md:flex flex-col w-64 bg-white border-r border-border">
        <div className="p-4 border-b border-border">
          <h1 className="text-lg font-semibold text-text-primary">资产管理系统</h1>
          <p className="text-sm text-text-secondary">{user?.office_name || user?.supplier_name || ''}</p>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              end={true}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-btn text-sm transition-colors ${
                  isActive
                    ? 'bg-primary text-white'
                    : 'text-text-secondary hover:bg-gray-50'
                }`
              }
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-border">
          <div className="flex items-center justify-between">
            <div className="text-sm">
              <p className="font-medium">{user?.real_name}</p>
              <p className="text-text-secondary text-xs">{getRoleName(user?.role)}</p>
            </div>
            <button
              onClick={handleLogout}
              className="text-sm text-text-secondary hover:text-danger"
            >
              退出
            </button>
          </div>
        </div>
      </aside>

      {/* 移动端底部导航 */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-border z-50">
        <nav className="flex justify-around py-2">
          {navItems.slice(0, 5).map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              end={true}
              className={({ isActive }) =>
                `flex flex-col items-center px-2 py-1 text-xs ${
                  isActive ? 'text-primary' : 'text-text-secondary'
                }`
              }
            >
              <span className="text-lg">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      {/* 主内容区 */}
      <main className="flex-1 md:p-6 p-4 pb-20 md:pb-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}

function getRoleName(role) {
  const names = {
    admin: '管理员',
    asset_manager: '资产管理员',
    facility: '会服',
    supplier: '供应商'
  }
  return names[role] || role
}
