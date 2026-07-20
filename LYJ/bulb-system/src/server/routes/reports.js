const express = require('express')
const { getDB } = require('../db/init')
const { authMiddleware, roleMiddleware } = require('../middleware/auth')

const router = express.Router()

// 库存汇总报表
router.get('/inventory', authMiddleware, roleMiddleware('admin', 'asset_manager'), (req, res) => {
  const db = getDB()
  const report = db.prepare(`
    SELECT o.name as office_name, s.name as sku_name, s.type as sku_type,
           i.quantity, i.min_stock
    FROM inventory i
    JOIN offices o ON i.office_id = o.id
    JOIN skus s ON i.sku_id = s.id
    ORDER BY o.name, s.type, s.name
  `).all()

  res.json({ data: report })
})

// 消耗趋势报表
router.get('/consumption', authMiddleware, roleMiddleware('admin', 'asset_manager'), (req, res) => {
  const db = getDB()
  const { start_date, end_date } = req.query

  let sql = `
    SELECT strftime('%Y-%m', r.replaced_at) as month,
           s.name as sku_name,
           COUNT(*) as count
    FROM replacements r
    JOIN skus s ON r.sku_id = s.id
    WHERE s.type = 'bulb'
  `
  const params = []

  if (start_date) {
    sql += ' AND r.replaced_at >= ?'
    params.push(start_date)
  }
  if (end_date) {
    sql += ' AND r.replaced_at <= ?'
    params.push(end_date)
  }

  sql += ' GROUP BY strftime("%Y-%m", r.replaced_at), s.name ORDER BY month DESC, s.name'

  const report = db.prepare(sql).all(...params)
  res.json({ data: report })
})

// 成本分析报表
router.get('/cost', authMiddleware, roleMiddleware('admin', 'asset_manager'), (req, res) => {
  const db = getDB()
  const report = db.prepare(`
    SELECT o.name as office_name, s.name as sku_name,
           COUNT(*) as count, s.unit_price,
           COUNT(*) * COALESCE(s.unit_price, 0) as total_cost
    FROM replacements r
    JOIN skus s ON r.sku_id = s.id
    JOIN projectors p ON r.projector_id = p.id
    LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
    LEFT JOIN offices o ON mr.office_id = o.id
    GROUP BY o.name, s.name
    ORDER BY o.name, total_cost DESC
  `).all()

  res.json({ data: report })
})

// 投影仪状况报表
router.get('/projector-status', authMiddleware, roleMiddleware('admin', 'asset_manager'), (req, res) => {
  const db = getDB()
  const report = db.prepare(`
    SELECT p.status, COUNT(*) as count
    FROM projectors p
    GROUP BY p.status
  `).all()

  const total = db.prepare('SELECT COUNT(*) as total FROM projectors').get()

  res.json({ data: { status: report, total: total.total } })
})

// 调拨记录报表
router.get('/transfers', authMiddleware, roleMiddleware('admin', 'asset_manager'), (req, res) => {
  const db = getDB()
  const { start_date, end_date } = req.query

  let sql = `
    SELECT r.replaced_at, r.notes,
           p.asset_code as projector_code,
           mr.name as meeting_room_name,
           o_from.name as from_office_name,
           o_to.name as to_office_name,
           s.name as sku_name,
           u.real_name as operator_name
    FROM replacements r
    JOIN projectors p ON r.projector_id = p.id
    LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
    LEFT JOIN offices o_to ON mr.office_id = o_to.id
    JOIN offices o_from ON r.from_office_id = o_from.id
    JOIN skus s ON r.sku_id = s.id
    JOIN users u ON r.operator_id = u.id
    WHERE o_from.id != o_to.id
  `
  const params = []

  if (start_date) {
    sql += ' AND r.replaced_at >= ?'
    params.push(start_date)
  }
  if (end_date) {
    sql += ' AND r.replaced_at <= ?'
    params.push(end_date)
  }

  sql += ' ORDER BY r.replaced_at DESC'

  const report = db.prepare(sql).all(...params)
  res.json({ data: report })
})

module.exports = router
