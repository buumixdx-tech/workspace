const express = require('express')
const { getDB } = require('../db/init')
const { authMiddleware, roleMiddleware } = require('../middleware/auth')

const router = express.Router()

// 获取会议室列表
router.get('/', authMiddleware, (req, res) => {
  const db = getDB()
  let rooms
  if (req.user.role === 'facility') {
    rooms = db.prepare(`
      SELECT mr.*, o.name as office_name
      FROM meeting_rooms mr
      JOIN offices o ON mr.office_id = o.id
      WHERE mr.office_id = ?
      ORDER BY mr.name
    `).all(req.user.office_id)
  } else {
    rooms = db.prepare(`
      SELECT mr.*, o.name as office_name
      FROM meeting_rooms mr
      JOIN offices o ON mr.office_id = o.id
      ORDER BY o.name, mr.name
    `).all()
  }
  res.json({ data: rooms })
})

// 获取单个会议室
router.get('/:id', authMiddleware, (req, res) => {
  const db = getDB()
  const room = db.prepare(`
    SELECT mr.*, o.name as office_name
    FROM meeting_rooms mr
    JOIN offices o ON mr.office_id = o.id
    WHERE mr.id = ?
  `).get(req.params.id)
  if (!room) {
    return res.status(404).json({ message: '会议室不存在' })
  }
  res.json({ data: room })
})

// 创建会议室
router.post('/', authMiddleware, roleMiddleware('admin', 'facility'), (req, res) => {
  const db = getDB()
  const { office_id, name, floor, capacity_normal, capacity_max } = req.body

  if (req.user.role === 'facility' && req.user.office_id !== office_id) {
    return res.status(403).json({ message: '权限不足' })
  }

  if (!office_id || !name) {
    return res.status(400).json({ message: '办公区和名称不能为空' })
  }

  db.prepare(`
    INSERT INTO meeting_rooms (office_id, name, floor, capacity_normal, capacity_max)
    VALUES (?, ?, ?, ?, ?)
  `).run(office_id, name, floor || null, capacity_normal || null, capacity_max || null)

  const room = db.prepare(`
    SELECT mr.*, o.name as office_name
    FROM meeting_rooms mr
    JOIN offices o ON mr.office_id = o.id
    WHERE mr.id = last_insert_rowid()
  `).get()

  res.json({ data: room })
})

// 更新会议室
router.put('/:id', authMiddleware, roleMiddleware('admin', 'facility'), (req, res) => {
  const db = getDB()
  const { name, floor, capacity_normal, capacity_max } = req.body

  const room = db.prepare('SELECT * FROM meeting_rooms WHERE id = ?').get(req.params.id)
  if (!room) {
    return res.status(404).json({ message: '会议室不存在' })
  }

  if (req.user.role === 'facility' && req.user.office_id !== room.office_id) {
    return res.status(403).json({ message: '权限不足' })
  }

  db.prepare(`
    UPDATE meeting_rooms SET name = ?, floor = ?, capacity_normal = ?, capacity_max = ?
    WHERE id = ?
  `).run(name || room.name, floor ?? room.floor, capacity_normal ?? room.capacity_normal, capacity_max ?? room.capacity_max, req.params.id)

  const updated = db.prepare(`
    SELECT mr.*, o.name as office_name
    FROM meeting_rooms mr
    JOIN offices o ON mr.office_id = o.id
    WHERE mr.id = ?
  `).get(req.params.id)

  res.json({ data: updated })
})

// 删除会议室
router.delete('/:id', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  db.prepare('DELETE FROM meeting_rooms WHERE id = ?').run(req.params.id)
  res.json({ message: '删除成功' })
})

module.exports = router
