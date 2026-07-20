import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppLayout } from '@/components/layout/AppLayout'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { LoginPage } from '@/pages/Login'
import { DashboardPage } from '@/pages/Dashboard'
import { EntryPage } from '@/pages/Entry'
import { FinancePage } from '@/pages/Finance'
import { VCPager } from '@/pages/VC'
import { LogisticsPage } from '@/pages/Logistics'
import { CashFlowPage } from '@/pages/CashFlow'
import { BusinessPage } from '@/pages/Business'
import { SupplyChainPage } from '@/pages/SupplyChain'
import { BusinessPartnersPage } from '@/pages/BusinessPartners'
import { TimeRulesPage } from '@/pages/TimeRules'
import { SystemEventsPage } from '@/pages/SystemEvents'
import { InventoryPage } from '@/pages/Inventory'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/shanyinerp">
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="entry" element={<EntryPage />} />
            <Route path="entry/customers" element={<EntryPage />} />
            <Route path="entry/points" element={<EntryPage />} />
            <Route path="entry/suppliers" element={<EntryPage />} />
            <Route path="entry/skus" element={<EntryPage />} />
            <Route path="entry/partners" element={<EntryPage />} />
            <Route path="entry/bank-accounts" element={<EntryPage />} />
            <Route path="entry/import-export" element={<EntryPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="vc" element={<VCPager />} />
            <Route path="logistics" element={<LogisticsPage />} />
            <Route path="cash-flow" element={<CashFlowPage />} />
            <Route path="business/management" element={<BusinessPage />} />
            <Route path="business/supply-chain" element={<SupplyChainPage />} />
            <Route path="business/partners" element={<BusinessPartnersPage />} />
            <Route path="inventory" element={<InventoryPage />} />
            <Route path="rules" element={<TimeRulesPage />} />
            <Route path="events" element={<SystemEventsPage />} />
          </Route>

          {/* Fallback redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
