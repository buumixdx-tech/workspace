const express = require('express')
const { getDB } = require('../db/init')
const { authMiddleware, roleMiddleware } = require('../middleware/auth')

const router = express.Router()

// 获取库存列表
router.get('/', authMiddleware, (req, res) => {
  const db = getDB()
  const { office_id, sku_type } = req.query
  let inventory

  if (office_id) {
    inventory = db.prepare(`
      SELECT i.*, o.name as office_name, s.name as sku_name, s.type as sku_type
      FROM inventory i
      JOIN offices o ON i.office_id = o.id
      JOIN skus s ON i.sku_id = s.id
      WHERE i.office_id = ?
      ORDER BY s.type, s.name
    `).all(office_id)
  } else if (sku_type) {
    inventory = db.prepare(`
      SELECT i.*, o.name as office_name, s.name as sku_name, s.type as sku_type
      FROM inventory i
      JOIN offices o ON i.office_id = o.id
      JOIN skus s ON i.sku_id = s.id
      WHERE s.type = ?
      ORDER BY o.name, s.name
    `).all(sku_type)
  } else {
    inventory = db.prepare(`
      SELECT i.*, o.name as office_name, s.name as sku_name, s.type as sku_type
      FROM inventory i
      JOIN offices o ON i.office_id = o.id
      JOIN skus s ON i.sku_id = s.id
      ORDER BY o.name, s.type, s.name
    `).all()
  }

  res.json({ data: inventory })
})

// 获取库存警戒列表（SKU 级别，保留）
router.get('/alerts', authMiddleware, (req, res) => {
  const db = getDB()
  const alerts = db.prepare(`
    SELECT i.*, o.name as office_name, s.name as sku_name
    FROM inventory i
    JOIN offices o ON i.office_id = o.id
    JOIN skus s ON i.sku_id = s.id
    WHERE i.min_stock IS NOT NULL AND i.quantity <= i.min_stock
    ORDER BY o.name, s.name
  `).all()
  res.json({ data: alerts })
})

// 获取办公区灯泡库存告警（按办公区聚合，灯泡总量 < 5 触发）
router.get('/office-alerts', authMiddleware, (req, res) => {
  const db = getDB()
  const alerts = db.prepare(`
    SELECT o.id as office_id, o.name as office_name,
           COALESCE(SUM(i.quantity), 0) as total_bulb_quantity
    FROM offices o
    LEFT JOIN inventory i ON o.id = i.office_id
    LEFT JOIN skus s ON i.sku_id = s.id AND s.type = 'bulb'
    GROUP BY o.id, o.name
    HAVING total_bulb_quantity < 5
    ORDER BY o.name
  `).all()
  res.json({ data: alerts })
})

// 更新库存
router.put('/', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const { office_id, sku_id, quantity, min_stock } = req.body
  if (!office_id || !sku_id) {
    return res.status(400).json({ message: '办公区和 SKU 不能为空' })
  }

  const existing = db.prepare('SELECT * FROM inventory WHERE office_id = ? AND sku_id = ?').get(office_id, sku_id)

  const now = new Date()
  const pad = n => n.toString().padStart(2, '0')
  const shanghaiTs = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`

  if (existing) {
    db.prepare(`
      UPDATE inventory SET quantity = ?, min_stock = ?, updated_at = ?
      WHERE office_id = ? AND sku_id = ?
    `).run(quantity, min_stock ?? existing.min_stock, shanghaiTs, office_id, sku_id)
  } else {
    db.prepare(`
      INSERT INTO inventory (office_id, sku_id, quantity, min_stock, updated_at)
      VALUES (?, ?, ?, ?, ?)
    `).run(office_id, sku_id, quantity, min_stock, shanghaiTs)
  }

  const updated = db.prepare(`
    SELECT i.*, o.name as office_name, s.name as sku_name
    FROM inventory i
    JOIN offices o ON i.office_id = o.id
    JOIN skus s ON i.sku_id = s.id
    WHERE i.office_id = ? AND i.sku_id = ?
  `).get(office_id, sku_id)

  res.json({ data: updated })
})

module.exports = router
