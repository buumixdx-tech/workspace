import { useState } from 'react'
import axios from 'axios'

export default function ImportPage() {
  const [file, setFile] = useState(null)
  const [type, setType] = useState('offices')
  const [exportType, setExportType] = useState('')
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)

  const importTypes = [
    { value: 'offices', label: '办公区' },
    { value: 'meeting_rooms', label: '会议室' },
    { value: 'skus', label: 'SKU' },
    { value: 'projectors', label: '投影仪' },
    { value: 'suppliers', label: '供应商' },
    { value: 'users', label: '用户' },
    { value: 'inventory', label: '库存' },
  ]

  const exportTypes = [
    { value: '__all__', label: '所有类型（分Sheet）' },
    { value: 'offices', label: '办公区' },
    { value: 'meeting_rooms', label: '会议室' },
    { value: 'skus', label: 'SKU' },
    { value: 'projectors', label: '投影仪' },
    { value: 'suppliers', label: '供应商' },
    { value: 'users', label: '用户' },
    { value: 'inventory', label: '库存' },
    { value: 'replacements', label: '更换记录' },
    { value: 'shipments', label: '供货记录' },
  ]

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!file) return
    setUploading(true)
    setResult(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await axios.post(`/admin/import/${type}`, formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      setResult({ success: true, message: `成功导入 ${res.data.data?.count || 0} 条记录` })
    } catch (err) {
      setResult({ success: false, message: err.response?.data?.message || '导入失败' })
    } finally {
      setUploading(false)
    }
  }

  const handleExport = async (exportType) => {
    if (!exportType) return
    try {
      const res = await axios.get(`/admin/import/export/${exportType}`, { responseType: 'blob' })
      const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = exportType === '__all__' ? '全部数据.xlsx' : `${exportType}.xlsx`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      alert('导出失败')
    }
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-text-primary mb-6">数据导入导出</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 导入 */}
        <div className="bg-white rounded-card shadow-card p-6">
          <h2 className="font-semibold text-text-primary mb-4">导入数据</h2>
          <form onSubmit={handleUpload} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">数据类型</label>
              <select value={type} onChange={e => setType(e.target.value)} className="w-full border border-border rounded-input px-3 py-2">
                {importTypes.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Excel 文件</label>
              <input type="file" accept=".xlsx,.xls,.csv" onChange={e => setFile(e.target.files[0])} className="w-full border border-border rounded-input px-3 py-2" />
            </div>

            {result && (
              <div className={`p-3 rounded-btn ${result.success ? 'bg-green-50 text-success' : 'bg-red-50 text-danger'}`}>
                {result.message}
              </div>
            )}

            <button type="submit" disabled={!file || uploading} className="w-full bg-primary text-white py-2 rounded-btn hover:bg-blue-600 disabled:opacity-50">
              {uploading ? '导入中...' : '导入'}
            </button>
          </form>

          <div className="mt-4 pt-4 border-t border-border">
            <h3 className="text-sm font-medium mb-2">导入说明</h3>
            <ul className="text-xs text-text-secondary space-y-1">
              <li>• 请下载 Excel 模板进行编辑</li>
              <li>• 支持 .xlsx、.xls、.csv 格式</li>
              <li>• 第一行为表头，请勿修改</li>
              <li>• 导入将增量更新已有数据</li>
            </ul>
          </div>
        </div>

        {/* 导出 */}
        <div className="bg-white rounded-card shadow-card p-6">
          <h2 className="font-semibold text-text-primary mb-4">导出数据</h2>
          <div className="space-y-4">
            <div>
              <select
                value={exportType}
                onChange={e => setExportType(e.target.value)}
                className="w-full border border-border rounded-input px-3 py-2"
              >
                <option value="">选择导出类型</option>
                {exportTypes.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <button
              onClick={() => handleExport(exportType)}
              disabled={!exportType}
              className="w-full bg-primary text-white py-2 rounded-btn hover:bg-blue-600 disabled:opacity-50"
            >
              下载 Excel
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
