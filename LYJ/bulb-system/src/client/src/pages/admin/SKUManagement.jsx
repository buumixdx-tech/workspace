import { useState, useEffect } from 'react'
import axios from 'axios'
import Select from 'react-select'

export default function SKUManagement() {
  const [skus, setSkus] = useState([])
  const [bulbSkus, setBulbSkus] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editingSku, setEditingSku] = useState(null)
  const [specs, setSpecs] = useState([{ k: '', v: '' }])
  const [formData, setFormData] = useState({ name: '', type: 'bulb' })
  const [selectedCompat, setSelectedCompat] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadData() }, [])
  const loadData = async () => {
    try {
      const [skusRes, bulbRes] = await Promise.all([axios.get('/admin/skus'), axios.get('/admin/skus?type=bulb')])
      setSkus(skusRes.data.data || [])
      setBulbSkus(bulbRes.data.data || [])
    } catch (err) { console.error('加载失败', err) }
    finally { setLoading(false) }
  }

  const parseSpecs = (specsStr) => {
    if (!specsStr) return [{ k: '', v: '' }]
    try {
      const obj = JSON.parse(specsStr)
      return Object.entries(obj).map(([k, v]) => ({ k, v })).concat([{ k: '', v: '' }])
    } catch {
      return [{ k: '', v: '' }]
    }
  }

  const stringifySpecs = (specsArr) => {
    const obj = {}
    specsArr.forEach(({ k, v }) => {
      if (k.trim()) obj[k.trim()] = v.trim()
    })
    return Object.keys(obj).length > 0 ? JSON.stringify(obj) : ''
  }

  const openModal = (sku = null) => {
    setEditingSku(sku)
    setFormData(sku ? { name: sku.name, type: sku.type } : { name: '', type: 'bulb' })
    setSpecs(sku ? parseSpecs(sku.specs) : [{ k: '', v: '' }])
    if (sku && sku.type === 'projector') {
      const compatIds = sku.compatible_model_ids || []
      setSelectedCompat(bulbSkus.filter(b => compatIds.includes(b.id)).map(b => ({ value: b.id, label: b.name })))
    } else {
      setSelectedCompat([])
    }
    setShowModal(true)
  }

  const handleSpecChange = (index, field, value) => {
    const newSpecs = [...specs]
    newSpecs[index][field] = value
    setSpecs(newSpecs)
  }

  const handleRemoveSpec = (index) => {
    if (specs.length > 1) {
      setSpecs(specs.filter((_, i) => i !== index))
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const data = {
        ...formData,
        specs: stringifySpecs(specs),
        compatible_model_ids: selectedCompat.map(s => s.value)
      }
      if (editingSku) { await axios.put(`/admin/skus/${editingSku.id}`, data) }
      else { await axios.post('/admin/skus', data) }
      setShowModal(false); loadData()
    } catch (err) { alert(err.response?.data?.message || '操作失败') }
  }

  const formatSpecsDisplay = (specsStr) => {
    if (!specsStr) return '-'
    try {
      const obj = JSON.parse(specsStr)
      return Object.entries(obj).map(([k, v]) => `${k}: ${v}`).join(', ')
    } catch {
      return specsStr
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除？')) return
    try { await axios.delete(`/admin/skus/${id}`); loadData() }
    catch (err) { alert(err.response?.data?.message || '删除失败') }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl font-bold text-text-primary">SKU管理</h1>
        <button onClick={() => openModal()} className="bg-primary text-white px-4 py-2 rounded-btn hover:bg-blue-600">添加SKU</button>
      </div>
      <div className="bg-white rounded-card shadow-card overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">型号</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">类型</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">规格参数</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-text-secondary">操作</th>
            </tr>
          </thead>
          <tbody>
            {skus.map(s => (
              <tr key={s.id} className="border-b border-border hover:bg-gray-50">
                <td className="px-4 py-3 text-sm">{s.name}</td>
                <td className="px-4 py-3 text-sm"><span className={`px-2 py-1 rounded text-xs ${s.type === 'bulb' ? 'bg-primary text-white' : 'bg-purple-500 text-white'}`}>{s.type === 'bulb' ? '灯泡' : '投影仪'}</span></td>
                <td className="px-4 py-3 text-sm">{formatSpecsDisplay(s.specs)}</td>
                <td className="px-4 py-3 text-sm">
                  <button onClick={() => openModal(s)} className="text-primary mr-2">编辑</button>
                  <button onClick={() => handleDelete(s.id)} className="text-danger">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-card p-6 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4">{editingSku ? '编辑SKU' : '添加SKU'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div><label className="block text-sm mb-1">型号名称 *</label><input type="text" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} className="w-full border border-border rounded-input px-3 py-2" required /></div>
              <div><label className="block text-sm mb-1">类型 *</label><select value={formData.type} onChange={e => { setFormData({...formData, type: e.target.value}); setSelectedCompat([]); }} className="w-full border border-border rounded-input px-3 py-2" required><option value="bulb">灯泡</option><option value="projector">投影仪</option></select></div>
              {formData.type === 'projector' && (
                <div>
                  <label className="block text-sm mb-1">适配灯泡型号</label>
                  <Select
                    isMulti
                    options={bulbSkus.map(s => ({ value: s.id, label: s.name }))}
                    value={selectedCompat}
                    onChange={setSelectedCompat}
                    className="basic-multi-select"
                    classNamePrefix="select"
                  />
                </div>
              )}
              <div>
                <label className="block text-sm mb-1">规格参数</label>
                <div className="flex flex-col gap-2">
                  {specs.slice(0, -1).map((spec, index) => (
                    <div key={index} className="flex gap-2 items-center">
                      <input type="text" value={spec.k} onChange={e => handleSpecChange(index, 'k', e.target.value)} placeholder="键" className="w-1/2 border border-border rounded-input px-3 py-2" />
                      <input type="text" value={spec.v} onChange={e => handleSpecChange(index, 'v', e.target.value)} placeholder="值" className="w-1/2 border border-border rounded-input px-3 py-2" />
                      <button type="button" onClick={() => handleRemoveSpec(index)} className="text-danger">×</button>
                    </div>
                  ))}
                  {specs[specs.length - 1].k === '' && specs[specs.length - 1].v === '' && (
                    <div className="flex gap-2 items-center">
                      <input type="text" placeholder="键" className="w-1/2 border border-border rounded-input px-3 py-2 bg-gray-50" disabled />
                      <input type="text" placeholder="值" className="w-1/2 border border-border rounded-input px-3 py-2 bg-gray-50" disabled />
                      <button type="button" onClick={() => setSpecs([...specs, { k: '', v: '' }])} className="text-primary">+</button>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 bg-primary text-white py-2 rounded-btn">保存</button>
                <button type="button" onClick={() => setShowModal(false)} className="flex-1 border border-border py-2 rounded-btn">取消</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
