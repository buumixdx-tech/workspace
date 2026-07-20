const express = require('express')
const { getDB } = require('../db/init')
const { authMiddleware, roleMiddleware } = require('../middleware/auth')

const router = express.Router()

// 获取投影仪列表
router.get('/', authMiddleware, (req, res) => {
  const db = getDB()
  const { office_id } = req.query
  let projectors

  if (req.user.role === 'facility' || office_id) {
    const targetOffice = office_id || req.user.office_id
    projectors = db.prepare(`
      SELECT p.*, mr.name as meeting_room_name, o.name as office_name, s.name as sku_name, s.compatible_model_ids
      FROM projectors p
      LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
      LEFT JOIN offices o ON mr.office_id = o.id
      LEFT JOIN skus s ON p.sku_id = s.id
      WHERE mr.office_id = ?
      ORDER BY p.asset_code
    `).all(targetOffice)
  } else {
    projectors = db.prepare(`
      SELECT p.*, mr.name as meeting_room_name, o.name as office_name, s.name as sku_name, s.compatible_model_ids
      FROM projectors p
      LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
      LEFT JOIN offices o ON mr.office_id = o.id
      LEFT JOIN skus s ON p.sku_id = s.id
      ORDER BY o.name, mr.name, p.asset_code
    `).all()
  }

  // 附加兼容灯泡信息（通过投影仪型号 SKU 的 compatible_model_ids）
  const allBulbSkus = db.prepare('SELECT id, name, type FROM skus WHERE type = ?').all('bulb')
  projectors = projectors.map(p => {
    const compatIds = p.compatible_model_ids ? JSON.parse(p.compatible_model_ids) : []
    const bulbs = allBulbSkus.filter(b => compatIds.includes(b.id))
    return { ...p, compatible_bulb_skus: bulbs }
  })

  res.json({ data: projectors })
})

// 获取单个投影仪
router.get('/:id', authMiddleware, (req, res) => {
  const db = getDB()
  const projector = db.prepare(`
    SELECT p.*, mr.name as meeting_room_name, o.name as office_name, s.name as sku_name, s.compatible_model_ids
    FROM projectors p
    LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
    LEFT JOIN offices o ON mr.office_id = o.id
    LEFT JOIN skus s ON p.sku_id = s.id
    WHERE p.id = ?
  `).get(req.params.id)

  if (!projector) {
    return res.status(404).json({ message: '投影仪不存在' })
  }

  // 通过投影仪型号 SKU 的 compatible_model_ids 获取兼容灯泡
  const compatIds = projector.compatible_model_ids ? JSON.parse(projector.compatible_model_ids) : []
  if (compatIds.length > 0) {
    const placeholders = compatIds.map(() => '?').join(',')
    const bulbs = db.prepare(`SELECT id, name, type FROM skus WHERE id IN (${placeholders})`).all(...compatIds)
    projector.compatible_bulb_skus = bulbs
  } else {
    projector.compatible_bulb_skus = []
  }

  res.json({ data: projector })
})

// 创建投影仪
router.post('/', authMiddleware, roleMiddleware('admin', 'facility'), (req, res) => {
  const db = getDB()
  const { asset_code, meeting_room_id, sku_id, status, notes } = req.body

  if (!asset_code || !sku_id) {
    return res.status(400).json({ message: '资产编码和型号不能为空' })
  }

  if (!/^\d{6}$/.test(asset_code)) {
    return res.status(400).json({ message: '资产编码必须是6位数字' })
  }

  try {
    db.prepare(`
      INSERT INTO projectors (asset_code, meeting_room_id, sku_id, status, notes)
      VALUES (?, ?, ?, ?, ?)
    `).run(
      asset_code,
      meeting_room_id || null,
      sku_id,
      status || 'normal',
      notes || null
    )

    const projector = db.prepare(`
      SELECT p.*, mr.name as meeting_room_name, o.name as office_name, s.name as sku_name
      FROM projectors p
      LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
      LEFT JOIN offices o ON mr.office_id = o.id
      LEFT JOIN skus s ON p.sku_id = s.id
      WHERE p.asset_code = ?
    `).get(asset_code)

    projector.compatible_bulb_skus = []
    res.json({ data: projector })
  } catch (err) {
    if (err.message.includes('UNIQUE')) {
      return res.status(400).json({ message: '资产编码已存在' })
    }
    throw err
  }
})

// 更新投影仪
router.put('/:id', authMiddleware, roleMiddleware('admin', 'facility'), (req, res) => {
  const db = getDB()
  const { meeting_room_id, sku_id, status, notes } = req.body

  const projector = db.prepare('SELECT * FROM projectors WHERE id = ?').get(req.params.id)
  if (!projector) {
    return res.status(404).json({ message: '投影仪不存在' })
  }

  db.prepare(`
    UPDATE projectors SET meeting_room_id = ?, sku_id = ?, status = ?, notes = ?
    WHERE id = ?
  `).run(
    meeting_room_id ?? projector.meeting_room_id,
    sku_id ?? projector.sku_id,
    status ?? projector.status,
    notes ?? projector.notes,
    req.params.id
  )

  const updated = db.prepare(`
    SELECT p.*, mr.name as meeting_room_name, o.name as office_name, s.name as sku_name
    FROM projectors p
    LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
    LEFT JOIN offices o ON mr.office_id = o.id
    LEFT JOIN skus s ON p.sku_id = s.id
    WHERE p.id = ?
  `).get(req.params.id)

  updated.compatible_bulb_skus = []
  res.json({ data: updated })
})

// 更新投影仪状态
router.put('/:id/status', authMiddleware, roleMiddleware('admin', 'facility'), (req, res) => {
  const db = getDB()
  const { status } = req.body
  if (!['normal', 'warning', 'offline'].includes(status)) {
    return res.status(400).json({ message: '无效的状态' })
  }

  const projector = db.prepare('SELECT * FROM projectors WHERE id = ?').get(req.params.id)
  if (!projector) {
    return res.status(404).json({ message: '投影仪不存在' })
  }

  db.prepare('UPDATE projectors SET status = ? WHERE id = ?').run(status, req.params.id)

  const updated = db.prepare(`
    SELECT p.*, mr.name as meeting_room_name, o.name as office_name, s.name as sku_name
    FROM projectors p
    LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
    LEFT JOIN offices o ON mr.office_id = o.id
    LEFT JOIN skus s ON p.sku_id = s.id
    WHERE p.id = ?
  `).get(req.params.id)

  res.json({ data: updated })
})

// 删除投影仪
router.delete('/:id', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  db.prepare('DELETE FROM projectors WHERE id = ?').run(req.params.id)
  res.json({ message: '删除成功' })
})

module.exports = router
