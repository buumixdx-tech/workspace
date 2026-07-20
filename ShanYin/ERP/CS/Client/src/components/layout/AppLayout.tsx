import { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  Warehouse,
  Truck,
  DollarSign,
  Briefcase,
  Box,
  ClipboardList,
  Settings,
  Activity,
  ChevronDown,
  ChevronRight,
  Handshake,
  Menu,
  X,
  LogOut,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/authStore'

interface NavItem {
  label: string
  icon: React.ElementType
  path: string
  children?: NavItem[]
}

const navItems: NavItem[] = [
  { label: '运行看板', icon: LayoutDashboard, path: '/' },
  {
    label: '业务中心',
    icon: Briefcase,
    path: '/business',
    children: [
      { label: '业务管理', path: '/business/management', icon: ClipboardList },
      { label: '供应链管理', path: '/business/supply-chain', icon: Box },
      { label: '合作方管理', path: '/business/partners', icon: Handshake },
    ],
  },
  {
    label: '业务运营',
    icon: Box,
    path: '/vc',
    children: [
      { label: '虚拟合同', path: '/vc', icon: FileText },
      { label: '库存看板', path: '/inventory', icon: Warehouse },
    ],
  },
  {
    label: '业务操作',
    icon: Truck,
    path: '/logistics',
    children: [
      { label: '物流管理', path: '/logistics', icon: Truck },
      { label: '资金流管理', path: '/cash-flow', icon: DollarSign },
    ],
  },
  { label: '时间规则', icon: ClipboardList, path: '/rules' },
  { label: '系统事件', icon: Activity, path: '/events' },
  { label: '财务管理', icon: DollarSign, path: '/finance' },
  { label: '信息录入', icon: Settings, path: '/entry' },
]

export function AppLayout({ children }: { children?: React.ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [expandedItems, setExpandedItems] = useState<string[]>(['业务中心', '业务运营', '业务操作'])
  const { user, logout, accessToken, setUser } = useAuthStore()

  // 页面刷新后，token存在但user为null时，重新获取用户信息
  useEffect(() => {
    if (accessToken && !user) {
      fetch(`${import.meta.env.VITE_API_URL || ''}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
        .then((res) => res.json())
        .then((data) => {
          if (data?.data) {
            setUser(data.data)
          }
        })
        .catch(console.error)
    }
  }, [accessToken, user, setUser])

  const toggleExpand = (label: string) => {
    setExpandedItems((prev) =>
      prev.includes(label) ? prev.filter((item) => item !== label) : [...prev, label]
    )
  }

  const isActive = (path: string) => location.pathname === path

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside
        className={cn(
          'flex flex-col border-r bg-card transition-all duration-300',
          collapsed ? 'w-16' : 'w-64'
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center border-b px-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-600 text-white font-bold">
              SY
            </div>
            {!collapsed && <span className="font-semibold">闪饮管理中心</span>}
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto p-2">
          {navItems.map((item) => (
            <div key={item.label}>
              {item.children ? (
                <div>
                  <Button
                    variant="ghost"
                    className={cn(
                      'w-full justify-start gap-3',
                      collapsed && 'justify-center px-2'
                    )}
                    onClick={() => toggleExpand(item.label)}
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    {!collapsed && (
                      <>
                        <span className="flex-1 text-left">{item.label}</span>
                        {expandedItems.includes(item.label) ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </>
                    )}
                  </Button>
                  {!collapsed && expandedItems.includes(item.label) && (
                    <div className="ml-6 mt-1 space-y-1">
                      {item.children.map((child) => (
                        <Link key={child.path} to={child.path}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className={cn(
                              'w-full justify-start',
                              isActive(child.path) && 'bg-accent'
                            )}
                          >
                            <child.icon className="mr-2 h-4 w-4" />
                            {child.label}
                          </Button>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <Link to={item.path}>
                  <Button
                    variant="ghost"
                    className={cn(
                      'w-full justify-start gap-3',
                      collapsed && 'justify-center px-2',
                      isActive(item.path) && 'bg-accent'
                    )}
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    {!collapsed && <span>{item.label}</span>}
                  </Button>
                </Link>
              )}
            </div>
          ))}
        </nav>

        {/* Collapse Toggle */}
        <div className="border-t p-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-center"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? <Menu className="h-4 w-4" /> : <X className="h-4 w-4" />}
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="flex h-14 items-center justify-between border-b px-6">
          <h1 className="text-lg font-semibold">
            {(() => {
              const item = navItems.find((item) => item.path === location.pathname || item.children?.some((c) => c.path === location.pathname))
              const child = item?.children?.find((c) => c.path === location.pathname)
              return child?.label ?? item?.label ?? '闪饮 ERP'
            })()}
          </h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">{user?.username || '用户'}</span>
            <Button variant="ghost" size="sm" onClick={handleLogout} title="退出登录">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6"><Outlet /></div>
      </main>
    </div>
  )
}
