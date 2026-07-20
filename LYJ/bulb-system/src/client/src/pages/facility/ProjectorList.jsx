import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from '../../App'

export default function ProjectorList() {
  const { user } = useAuth()
  const [projectors, setProjectors] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const res = await axios.get(`/admin/projectors?office_id=${user.office_id}`)
      setProjectors(res.data.data || [])
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status) => {
    const colors = {
      normal: 'bg-success',
      warning: 'bg-warning',
      offline: 'bg-danger'
    }
    return colors[status] || 'bg-gray-400'
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">投影仪列表</h1>

      <div className="grid gap-4 md:grid-cols-2">
        {loading ? (
          <div className="col-span-2 p-8 text-center text-text-secondary">加载中...</div>
        ) : projectors.length === 0 ? (
          <div className="col-span-2 p-8 text-center text-text-secondary">暂无投影仪</div>
        ) : (
          projectors.map(p => (
            <Link
              key={p.id}
              to={`/facility/projectors/${p.id}`}
              className="bg-white rounded-card shadow-card p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium">{p.asset_code}</span>
                <span className={`w-3 h-3 rounded-full ${getStatusColor(p.status)}`}></span>
              </div>
              <p className="text-sm text-text-secondary">{p.meeting_room_name}</p>
              <p className="text-sm text-text-secondary">{p.sku_name}</p>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}
