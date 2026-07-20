const express = require('express')
const multer = require('multer')
const path = require('path')
const { v4: uuidv4 } = require('uuid')
const { getDB } = require('../db/init')
const { authMiddleware, roleMiddleware } = require('../middleware/auth')

const router = express.Router()

// 照片上传配置
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const date = new Date()
    const dir = path.join(__dirname, '../../..', 'uploads', 'replacements',
      date.getFullYear().toString(),
      (date.getMonth() + 1).toString().padStart(2, '0'),
      date.getDate().toString().padStart(2, '0')
    )
    require('fs').mkdirSync(dir, { recursive: true })
    cb(null, dir)
  },
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname)
    cb(null, `replacement_${uuidv4()}${ext}`)
  }
})
const upload = multer({
  storage,
  limits: { fileSize: 5 * 1024 * 1024, files: 5 },
  fileFilter: (req, file, cb) => {
    const allowed = ['.jpg', '.jpeg', '.png', '.gif']
    const ext = path.extname(file.originalname).toLowerCase()
    if (allowed.includes(ext)) {
      cb(null, true)
    } else {
      cb(new Error('只支持 JPG/PNG/GIF 格式'))
    }
  }
})

// 获取更换记录列表
router.get('/', authMiddleware, (req, res) => {
  const db = getDB()
  const { projector_id, from_office_id, start_date, end_date } = req.query

  let sql = `
    SELECT r.*,
           p.asset_code as projector_code,
           mr.name as meeting_room_name,
           s.name as sku_name,
           o.name as from_office_name,
           u.real_name as operator_name
    FROM replacements r
    JOIN projectors p ON r.projector_id = p.id
    LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
    LEFT JOIN skus s ON r.sku_id = s.id
    JOIN offices o ON r.from_office_id = o.id
    JOIN users u ON r.operator_id = u.id
    WHERE 1=1
  `
  const params = []

  if (projector_id) {
    sql += ' AND r.projector_id = ?'
    params.push(projector_id)
  }
  if (from_office_id) {
    sql += ' AND r.from_office_id = ?'
    params.push(from_office_id)
  }
  if (start_date) {
    sql += ' AND r.replaced_at >= ?'
    params.push(start_date)
  }
  if (end_date) {
    sql += ' AND r.replaced_at <= ?'
    params.push(end_date)
  }

  sql += ' ORDER BY r.replaced_at DESC'

  let replacements = db.prepare(sql).all(...params)
  replacements = replacements.map(r => ({
    ...r,
    photos: r.photos ? JSON.parse(r.photos) : []
  }))

  res.json({ data: replacements })
})

// 获取单个更换记录
router.get('/:id', authMiddleware, (req, res) => {
  const db = getDB()
  const replacement = db.prepare(`
    SELECT r.*,
           p.asset_code as projector_code,
           mr.name as meeting_room_name,
           s.name as sku_name,
           o.name as from_office_name,
           u.real_name as operator_name
    FROM replacements r
    JOIN projectors p ON r.projector_id = p.id
    LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
    LEFT JOIN skus s ON r.sku_id = s.id
    JOIN offices o ON r.from_office_id = o.id
    JOIN users u ON r.operator_id = u.id
    WHERE r.id = ?
  `).get(req.params.id)

  if (!replacement) {
    return res.status(404).json({ message: '记录不存在' })
  }

  replacement.photos = replacement.photos ? JSON.parse(replacement.photos) : []
  res.json({ data: replacement })
})

// 创建更换记录
router.post('/', authMiddleware, roleMiddleware('admin', 'facility'), (req, res) => {
  const db = getDB()
  const { projector_id, sku_id, from_office_id, replaced_at, notes } = req.body

  if (!projector_id || !sku_id || !from_office_id) {
    return res.status(400).json({ message: '投影仪、灯泡型号和来源不能为空' })
  }

  // 验证灯泡与投影仪型号的兼容性
  const projector = db.prepare('SELECT sku_id FROM projectors WHERE id = ?').get(projector_id)
  if (!projector) {
    return res.status(400).json({ message: '投影仪不存在' })
  }
  const projectorSku = db.prepare('SELECT compatible_model_ids FROM skus WHERE id = ? AND type = ?').get(projector.sku_id, 'projector')
  if (projectorSku) {
    const compatIds = projectorSku.compatible_model_ids ? JSON.parse(projectorSku.compatible_model_ids) : []
    if (compatIds.length > 0 && !compatIds.includes(parseInt(sku_id))) {
      return res.status(400).json({ message: '该灯泡与投影仪型号不兼容' })
    }
  }

  // 如果来源是本办公区，减少库存
  const targetOffice = db.prepare(`
    SELECT mr.office_id FROM projectors p
    JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
    WHERE p.id = ?
  `).get(projector_id)

  const isLocalSource = targetOffice?.office_id === from_office_id

  if (isLocalSource) {
    const inv = db.prepare('SELECT quantity FROM inventory WHERE office_id = ? AND sku_id = ?').get(from_office_id, sku_id)
    if (!inv || inv.quantity <= 0) {
      return res.status(400).json({ message: '库存不足' })
    }
    db.prepare('UPDATE inventory SET quantity = quantity - 1, updated_at = CURRENT_TIMESTAMP WHERE office_id = ? AND sku_id = ?').run(from_office_id, sku_id)
  }

  db.prepare(`
    INSERT INTO replacements (projector_id, sku_id, from_office_id, operator_id, replaced_at, notes)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(projector_id, sku_id, from_office_id, req.user.id, replaced_at || (() => { const n=new Date(); const p=n=>n.toString().padStart(2,'0'); return `${n.getFullYear()}-${p(n.getMonth()+1)}-${p(n.getDate())} ${p(n.getHours())}:${p(n.getMinutes())}:${p(n.getSeconds())}`; })(), notes || null)

  const replacement = db.prepare(`
    SELECT r.*,
           p.asset_code as projector_code,
           mr.name as meeting_room_name,
           s.name as sku_name,
           o.name as from_office_name,
           u.real_name as operator_name
    FROM replacements r
    JOIN projectors p ON r.projector_id = p.id
    LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id
    LEFT JOIN skus s ON r.sku_id = s.id
    JOIN offices o ON r.from_office_id = o.id
    JOIN users u ON r.operator_id = u.id
    WHERE r.operator_id = ? AND r.projector_id = ? AND r.sku_id = ?
    ORDER BY r.id DESC LIMIT 1
  `).get(req.user.id, projector_id, sku_id)

  if (!replacement) {
    return res.status(500).json({ message: '创建失败' })
  }
  replacement.photos = []
  res.json({ data: replacement })
})

// 上传照片
router.post('/:id/photos', authMiddleware, roleMiddleware('admin', 'facility'), upload.array('photos', 5), (req, res) => {
  const db = getDB()
  const replacement = db.prepare('SELECT * FROM replacements WHERE id = ?').get(req.params.id)
  if (!replacement) {
    return res.status(404).json({ message: '记录不存在' })
  }

  const existingPhotos = replacement.photos ? JSON.parse(replacement.photos) : []
  const newPhotos = req.files.map(f => ({
    filename: f.filename,
    caption: req.body[`caption_${f.fieldname}`] || ''
  }))

  const allPhotos = [...existingPhotos, ...newPhotos]

  db.prepare('UPDATE replacements SET photos = ? WHERE id = ?').run(JSON.stringify(allPhotos), req.params.id)

  res.json({ data: allPhotos })
})

module.exports = router
