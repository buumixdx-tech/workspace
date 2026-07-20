import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'

export default function ProjectorDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [projector, setProjector] = useState(null)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [id])

  const loadData = async () => {
    try {
      const res = await axios.get(`/admin/projectors/${id}`)
      setProjector(res.data.data)
      setStatus(res.data.data.status)
    } catch (err) {
      console.error('加载失败', err)
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateStatus = async () => {
    try {
      await axios.put(`/admin/projectors/${id}/status`, { status })
      alert('状态更新成功')
      loadData()
    } catch (err) {
      alert(err.response?.data?.message || '更新失败')
    }
  }

  if (loading) {
    return <div className="p-8 text-center">加载中...</div>
  }

  if (!projector) {
    return <div className="p-8 text-center">未找到投影仪</div>
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-6">投影仪详情</h1>

      <div className="bg-white rounded-card shadow-card p-6 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-text-secondary">资产编码</label>
            <p className="font-medium">{projector.asset_code}</p>
          </div>
          <div>
            <label className="text-sm text-text-secondary">会议室</label>
            <p className="font-medium">{projector.meeting_room_name}</p>
          </div>
          <div>
            <label className="text-sm text-text-secondary">型号</label>
            <p className="font-medium">{projector.sku_name}</p>
          </div>
          <div>
            <label className="text-sm text-text-secondary">适配灯泡</label>
            <p className="font-medium">{projector.compatible_bulb_skus?.map(b => b.name).join(', ') || '-'}</p>
          </div>
        </div>

        <div className="border-t border-border pt-4">
          <label className="text-sm text-text-secondary block mb-2">状态</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full border border-border rounded-input px-3 py-2"
          >
            <option value="normal">正常</option>
            <option value="warning">警告</option>
            <option value="offline">离线</option>
          </select>
        </div>

        <div className="flex gap-3 pt-4">
          <button
            onClick={handleUpdateStatus}
            className="flex-1 bg-primary text-white py-2 rounded-btn hover:bg-blue-600"
          >
            保存
          </button>
          <button
            onClick={() => navigate(-1)}
            className="flex-1 border border-border py-2 rounded-btn hover:bg-gray-50"
          >
            返回
          </button>
        </div>
      </div>
    </div>
  )
}
