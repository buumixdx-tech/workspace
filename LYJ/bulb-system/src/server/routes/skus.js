const express = require('express')
const { getDB } = require('../db/init')
const { authMiddleware, roleMiddleware } = require('../middleware/auth')

const router = express.Router()

// 获取 SKU 列表
router.get('/', authMiddleware, (req, res) => {
  const db = getDB()
  const { type } = req.query
  let skus
  if (type) {
    skus = db.prepare('SELECT * FROM skus WHERE type = ? ORDER BY name').all(type)
  } else {
    skus = db.prepare('SELECT * FROM skus ORDER BY type, name').all()
  }
  skus = skus.map(s => ({
    ...s,
    compatible_model_ids: s.compatible_model_ids ? JSON.parse(s.compatible_model_ids) : []
  }))
  res.json({ data: skus })
})

// 获取单个 SKU
router.get('/:id', authMiddleware, (req, res) => {
  const db = getDB()
  const sku = db.prepare('SELECT * FROM skus WHERE id = ?').get(req.params.id)
  if (!sku) {
    return res.status(404).json({ message: 'SKU 不存在' })
  }
  sku.compatible_model_ids = sku.compatible_model_ids ? JSON.parse(sku.compatible_model_ids) : []
  res.json({ data: sku })
})

// 创建 SKU
router.post('/', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const { name, type, specs, compatible_model_ids } = req.body
  if (!name || !type) {
    return res.status(400).json({ message: '型号和类型不能为空' })
  }

  db.prepare('INSERT INTO skus (name, type, specs, compatible_model_ids) VALUES (?, ?, ?, ?)').run(
    name, type, specs || null,
    type === 'projector' && compatible_model_ids ? JSON.stringify(compatible_model_ids) : null
  )
  const sku = db.prepare('SELECT * FROM skus WHERE id = last_insert_rowid()').get()
  sku.compatible_model_ids = sku.compatible_model_ids ? JSON.parse(sku.compatible_model_ids) : []
  res.json({ data: sku })
})

// 更新 SKU
router.put('/:id', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const { name, type, specs, compatible_model_ids } = req.body
  db.prepare('UPDATE skus SET name = ?, type = ?, specs = ?, compatible_model_ids = ? WHERE id = ?').run(
    name, type, specs || null,
    type === 'projector' && compatible_model_ids ? JSON.stringify(compatible_model_ids) : null,
    req.params.id
  )
  const sku = db.prepare('SELECT * FROM skus WHERE id = ?').get(req.params.id)
  sku.compatible_model_ids = sku.compatible_model_ids ? JSON.parse(sku.compatible_model_ids) : []
  res.json({ data: sku })
})

// 删除 SKU
router.delete('/:id', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  db.prepare('DELETE FROM skus WHERE id = ?').run(req.params.id)
  res.json({ message: '删除成功' })
})

module.exports = router
