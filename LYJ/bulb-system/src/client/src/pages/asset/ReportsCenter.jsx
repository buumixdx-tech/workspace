import { Link } from 'react-router-dom'

export default function ReportsCenter() {
  const reports = [
    { path: '/am/reports/inventory', icon: '📦', label: '库存汇总', desc: '各办公区库存情况' },
    { path: '/am/reports/consumption', icon: '📉', label: '消耗趋势', desc: '月度消耗统计' },
    { path: '/am/reports/cost', icon: '💰', label: '成本分析', desc: '耗材成本统计' },
    { path: '/am/reports/projectors', icon: '📽️', label: '投影仪状况', desc: '投影仪状态分布' },
    { path: '/am/reports/transfers', icon: '🔄', label: '调拨记录', desc: '跨区调拨明细' },
  ]

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">报表中心</h1>

      <div className="grid gap-4 md:grid-cols-2">
        {reports.map(report => (
          <Link
            key={report.path}
            to={report.path}
            className="bg-white rounded-card shadow-card p-6 flex items-center gap-4 hover:shadow-md transition-shadow"
          >
            <span className="text-3xl">{report.icon}</span>
            <div>
              <p className="font-medium">{report.label}</p>
              <p className="text-sm text-text-secondary">{report.desc}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
