const express = require('express')
const { getDB } = require('../db/init')
const { authMiddleware, roleMiddleware } = require('../middleware/auth')

const router = express.Router()

// 获取办公区列表
router.get('/', authMiddleware, (req, res) => {
  console.log('[DEBUG offices GET] user:', JSON.stringify(req.user))
  const db = getDB()
  let offices
  if (req.user.role === 'facility') {
    offices = db.prepare('SELECT * FROM offices WHERE id = ?').all(req.user.office_id)
  } else {
    offices = db.prepare('SELECT * FROM offices ORDER BY name').all()
  }
  console.log('[DEBUG offices GET] result:', JSON.stringify(offices))
  res.json({ data: offices })
})

// 获取单个办公区
router.get('/:id', authMiddleware, (req, res) => {
  const db = getDB()
  const office = db.prepare('SELECT * FROM offices WHERE id = ?').get(req.params.id)
  if (!office) {
    return res.status(404).json({ message: '办公区不存在' })
  }
  res.json({ data: office })
})

// 创建办公区
router.post('/', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const { name, location } = req.body
  if (!name) {
    return res.status(400).json({ message: '名称不能为空' })
  }

  const result = db.prepare('INSERT INTO offices (name, location) VALUES (?, ?)').run(name, location || null)
  const office = db.prepare('SELECT * FROM offices WHERE id = ?').get(result.lastInsertRowid)
  res.json({ data: office })
})

// 更新办公区
router.put('/:id', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const { name, location } = req.body
  db.prepare('UPDATE offices SET name = ?, location = ? WHERE id = ?').run(name, location || null, req.params.id)
  const office = db.prepare('SELECT * FROM offices WHERE id = ?').get(req.params.id)
  res.json({ data: office })
})

// 删除办公区
router.delete('/:id', authMiddleware, roleMiddleware('admin'), (req, res) => {
  console.log('[DEBUG offices DELETE] id:', req.params.id, 'user role:', req.user.role)
  const db = getDB()
  try {
    db.prepare('DELETE FROM offices WHERE id = ?').run(req.params.id)
    console.log('[DEBUG offices DELETE] success')
    res.json({ message: '删除成功' })
  } catch (err) {
    console.log('[DEBUG offices DELETE] error:', err.message)
    res.status(500).json({ message: '删除失败: ' + err.message })
  }
})

module.exports = router
