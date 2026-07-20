const express = require('express')
const { getDB } = require('../db/init')
const { authMiddleware, roleMiddleware } = require('../middleware/auth')

const router = express.Router()

// 获取供应商列表
router.get('/', authMiddleware, (req, res) => {
  const db = getDB()
  const suppliers = db.prepare(`
    SELECT sp.id, sp.name, sp.contact_user_id, sp.address, sp.created_at,
           u.real_name as contact_name, u.phone as contact_phone, u.email as contact_email
    FROM suppliers sp
    LEFT JOIN users u ON sp.contact_user_id = u.id
    ORDER BY sp.name
  `).all()
  res.json({ data: suppliers })
})

// 获取单个供应商
router.get('/:id', authMiddleware, (req, res) => {
  const db = getDB()
  const supplier = db.prepare(`
    SELECT sp.id, sp.name, sp.contact_user_id, sp.address, sp.created_at,
           u.real_name as contact_name, u.phone as contact_phone, u.email as contact_email
    FROM suppliers sp
    LEFT JOIN users u ON sp.contact_user_id = u.id
    WHERE sp.id = ?
  `).get(req.params.id)
  if (!supplier) {
    return res.status(404).json({ message: '供应商不存在' })
  }
  res.json({ data: supplier })
})

// 创建供应商
router.post('/', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const { name, contact_user_id, address } = req.body
  if (!name) {
    return res.status(400).json({ message: '名称不能为空' })
  }

  db.prepare(`
    INSERT INTO suppliers (name, contact_user_id, address)
    VALUES (?, ?, ?)
  `).run(name, contact_user_id || null, address || null)

  const supplier = db.prepare(`
    SELECT sp.id, sp.name, sp.contact_user_id, sp.address, sp.created_at,
           u.real_name as contact_name, u.phone as contact_phone, u.email as contact_email
    FROM suppliers sp
    LEFT JOIN users u ON sp.contact_user_id = u.id
    WHERE sp.name = ?
  `).get(name)
  res.json({ data: supplier })
})

// 更新供应商
router.put('/:id', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const { name, contact_user_id, address } = req.body

  const supplier = db.prepare('SELECT * FROM suppliers WHERE id = ?').get(req.params.id)
  if (!supplier) {
    return res.status(404).json({ message: '供应商不存在' })
  }

  db.prepare(`
    UPDATE suppliers SET name = ?, contact_user_id = ?, address = ?
    WHERE id = ?
  `).run(
    name ?? supplier.name,
    contact_user_id ?? supplier.contact_user_id,
    address ?? supplier.address,
    req.params.id
  )

  const updated = db.prepare(`
    SELECT sp.id, sp.name, sp.contact_user_id, sp.address, sp.created_at,
           u.real_name as contact_name, u.phone as contact_phone, u.email as contact_email
    FROM suppliers sp
    LEFT JOIN users u ON sp.contact_user_id = u.id
    WHERE sp.id = ?
  `).get(req.params.id)
  res.json({ data: updated })
})

// 删除供应商
router.delete('/:id', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  db.prepare('DELETE FROM suppliers WHERE id = ?').run(req.params.id)
  res.json({ message: '删除成功' })
})

module.exports = router
