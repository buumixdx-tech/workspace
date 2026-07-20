import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, createContext, useContext, useEffect } from 'react'
import axios from 'axios'

// Layouts
import DashboardLayout from './components/DashboardLayout'

// Pages - Auth
import LoginPage from './pages/LoginPage'

// Pages - Facility (会服)
import FacilityDashboard from './pages/facility/Dashboard'
import ReplacementForm from './pages/facility/ReplacementForm'
import ReplacementList from './pages/facility/ReplacementList'
import InventoryLocal from './pages/facility/InventoryLocal'
import InventoryGlobal from './pages/facility/InventoryGlobal'
import FacilityInventoryAlerts from './pages/facility/InventoryAlerts'
import ShipmentConfirm from './pages/facility/ShipmentConfirm'
import ProjectorList from './pages/facility/ProjectorList'
import ProjectorDetail from './pages/facility/ProjectorDetail'

// Pages - Asset (资产管理员)
import AssetDashboard from './pages/asset/Dashboard'
import InventoryOverview from './pages/asset/InventoryOverview'
import InventoryAlerts from './pages/asset/InventoryAlerts'
import ReplacementRecords from './pages/asset/ReplacementRecords'
import ShipmentRecords from './pages/asset/ShipmentRecords'
import ReportsCenter from './pages/asset/ReportsCenter'

// Pages - Supplier (供应商)
import SupplierDashboard from './pages/supplier/Dashboard'
import ShipmentForm from './pages/supplier/ShipmentForm'
import ShipmentPending from './pages/supplier/ShipmentPending'
import ShipmentCompleted from './pages/supplier/ShipmentCompleted'
import ShipmentEdit from './pages/supplier/ShipmentEdit'

// Pages - Admin
import AdminDashboard from './pages/admin/Dashboard'
import UserManagement from './pages/admin/UserManagement'
import OfficeManagement from './pages/admin/OfficeManagement'
import MeetingRoomManagement from './pages/admin/MeetingRoomManagement'
import ProjectorManagement from './pages/admin/ProjectorManagement'
import SKUManagement from './pages/admin/SKUManagement'
import SupplierManagement from './pages/admin/SupplierManagement'
import ImportPage from './pages/admin/ImportPage'

// API 配置
axios.defaults.baseURL = ''

// Auth Context
const AuthContext = createContext(null)

export const useAuth = () => useContext(AuthContext)

function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('token')
      if (token) {
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
        const res = await axios.get('/auth/me')
        setUser(res.data.data)
      }
    } catch (e) {
      localStorage.removeItem('token')
    } finally {
      setLoading(false)
    }
  }

  const login = async (username, password) => {
    const res = await axios.post('/auth/login', { username, password })
    const { token, data } = res.data
    localStorage.setItem('token', token)
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
    setUser(data)
  }

  const logout = () => {
    localStorage.removeItem('token')
    delete axios.defaults.headers.common['Authorization']
    setUser(null)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-primary">加载中...</div>
      </div>
    )
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      <BrowserRouter basename="/">
        <Routes>
          {/* 公共路由 */}
          <Route path="/login" element={user ? <Navigate to={getHomePath(user.role)} /> : <LoginPage />} />

          {/* 会服路由 */}
          <Route path="/facility" element={<ProtectedRoute roles={['facility', 'admin']} user={user} />}>
            <Route index element={<FacilityDashboard />} />
            <Route path="replacements/new" element={<ReplacementForm />} />
            <Route path="replacements" element={<ReplacementList />} />
            <Route path="inventory" element={<InventoryLocal />} />
            <Route path="inventory/global" element={<InventoryGlobal />} />
            <Route path="inventory/alerts" element={<FacilityInventoryAlerts />} />
            <Route path="shipments" element={<ShipmentConfirm />} />
            <Route path="projectors" element={<ProjectorList />} />
            <Route path="projectors/:id" element={<ProjectorDetail />} />
          </Route>

          {/* 资产管理员路由 */}
          <Route path="/am" element={<ProtectedRoute roles={['asset_manager', 'admin']} user={user} />}>
            <Route index element={<AssetDashboard />} />
            <Route path="inventory" element={<InventoryOverview />} />
            <Route path="inventory/alerts" element={<InventoryAlerts />} />
            <Route path="replacements" element={<ReplacementRecords />} />
            <Route path="shipments" element={<ShipmentRecords />} />
            <Route path="reports" element={<ReportsCenter />} />
          </Route>

          {/* 供应商路由 */}
          <Route path="/supplier" element={<ProtectedRoute roles={['supplier']} user={user} />}>
            <Route index element={<SupplierDashboard />} />
            <Route path="shipments/new" element={<ShipmentForm />} />
            <Route path="shipments/pending" element={<ShipmentPending />} />
            <Route path="shipments/completed" element={<ShipmentCompleted />} />
            <Route path="shipments/:id" element={<ShipmentEdit />} />
          </Route>

          {/* Admin 路由 */}
          <Route path="/admin" element={<ProtectedRoute roles={['admin']} user={user} />}>
            <Route index element={<AdminDashboard />} />
            <Route path="users" element={<UserManagement />} />
            <Route path="offices" element={<OfficeManagement />} />
            <Route path="meeting-rooms" element={<MeetingRoomManagement />} />
            <Route path="projectors" element={<ProjectorManagement />} />
            <Route path="skus" element={<SKUManagement />} />
            <Route path="suppliers" element={<SupplierManagement />} />
            <Route path="import" element={<ImportPage />} />
          </Route>

          {/* 默认跳转 */}
          <Route path="/" element={<Navigate to={user ? getHomePath(user.role) : '/login'} />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  )
}

function getHomePath(role) {
  const paths = {
    admin: '/admin',
    asset_manager: '/am',
    facility: '/facility',
    supplier: '/supplier'
  }
  return paths[role] || '/login'
}

function ProtectedRoute({ children, roles, user }) {
  if (!user) {
    return <Navigate to="/login" replace />
  }
  if (!roles.includes(user.role)) {
    return <Navigate to={getHomePath(user.role)} replace />
  }
  return <DashboardLayout>{children}</DashboardLayout>
}

export default App
