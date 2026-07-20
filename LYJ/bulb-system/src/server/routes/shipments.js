const express = require('express')
const { getDB } = require('../db/init')
const { authMiddleware, roleMiddleware } = require('../middleware/auth')

const router = express.Router()

// 获取发货记录列表
router.get('/', authMiddleware, (req, res) => {
  const db = getDB()
  const { office_id, status, supplier_id, recipient_id, page = 1, page_size = 10 } = req.query

  let sql = `
    SELECT sh.*,
           s.name as supplier_name,
           o.name as office_name,
           u.real_name as recipient_name
    FROM shipments sh
    JOIN suppliers s ON sh.supplier_id = s.id
    JOIN offices o ON sh.office_id = o.id
    LEFT JOIN users u ON sh.recipient_id = u.id
    WHERE 1=1
  `
  const params = []

  if (office_id) {
    sql += ' AND sh.office_id = ?'
    params.push(office_id)
  }
  if (status) {
    sql += ' AND sh.status = ?'
    params.push(status)
  }
  if (supplier_id) {
    sql += ' AND sh.supplier_id = ?'
    params.push(supplier_id)
  }
  if (recipient_id) {
    sql += ' AND sh.recipient_id = ?'
    params.push(recipient_id)
  }

  // Count total
  let countSql = `
    SELECT COUNT(*) as total
    FROM shipments sh
    WHERE 1=1
  `
  if (office_id) countSql += ' AND sh.office_id = ?'
  if (status) countSql += ' AND sh.status = ?'
  if (supplier_id) countSql += ' AND sh.supplier_id = ?'
  if (recipient_id) countSql += ' AND sh.recipient_id = ?'

  const countParams = []
  if (office_id) countParams.push(office_id)
  if (status) countParams.push(status)
  if (supplier_id) countParams.push(supplier_id)
  if (recipient_id) countParams.push(recipient_id)

  const totalResult = db.prepare(countSql).get(...countParams)
  const total = totalResult?.total || 0

  const pageNum = parseInt(page)
  const pageSize = parseInt(page_size)
  const offset = (pageNum - 1) * pageSize

  sql += ` ORDER BY sh.created_at DESC LIMIT ${pageSize} OFFSET ${offset}`

  let shipments = db.prepare(sql).all(...params)

  shipments = shipments.map(sh => {
    const items = JSON.parse(sh.items || '[]')
    const itemsWithNames = items.map(item => {
      const sku = db.prepare('SELECT name FROM skus WHERE id = ?').get(item.sku_id)
      return { ...item, sku_name: sku?.name || '未知' }
    })
    return { ...sh, items: JSON.stringify(itemsWithNames) }
  })

  res.json({
    data: shipments,
    total,
    page: pageNum,
    page_size: pageSize,
    total_pages: Math.ceil(total / pageSize)
  })
})

// 获取单个发货记录
router.get('/:id', authMiddleware, (req, res) => {
  const db = getDB()
  const shipment = db.prepare(`
    SELECT sh.*,
           s.name as supplier_name,
           o.name as office_name,
           u.real_name as recipient_name
    FROM shipments sh
    JOIN suppliers s ON sh.supplier_id = s.id
    JOIN offices o ON sh.office_id = o.id
    LEFT JOIN users u ON sh.recipient_id = u.id
    WHERE sh.id = ?
  `).get(req.params.id)

  if (!shipment) {
    return res.status(404).json({ message: '发货记录不存在' })
  }

  const items = JSON.parse(shipment.items || '[]')
  const itemsWithNames = items.map(item => {
    const sku = db.prepare('SELECT name FROM skus WHERE id = ?').get(item.sku_id)
    return { ...item, sku_name: sku?.name || '未知' }
  })
  shipment.items = JSON.stringify(itemsWithNames)

  res.json({ data: shipment })
})

// 供应商查看自己的发货
router.get('/supplier/:supplierId', authMiddleware, (req, res) => {
  const db = getDB()
  const supplier = db.prepare('SELECT supplier_id FROM users WHERE id = ?').get(req.params.supplierId)
  if (!supplier || !supplier.supplier_id) {
    return res.status(400).json({ message: '无效的供应商用户' })
  }

  const shipments = db.prepare(`
    SELECT sh.*,
           s.name as supplier_name,
           o.name as office_name,
           u.real_name as recipient_name
    FROM shipments sh
    JOIN suppliers s ON sh.supplier_id = s.id
    JOIN offices o ON sh.office_id = o.id
    LEFT JOIN users u ON sh.recipient_id = u.id
    WHERE sh.supplier_id = ?
    ORDER BY sh.created_at DESC
  `).all(supplier.supplier_id)

  res.json({ data: shipments })
})

// 创建发货记录
router.post('/', authMiddleware, roleMiddleware('admin', 'supplier'), (req, res) => {
  const db = getDB()
  const { office_id, recipient_id, carrier, tracking_number, items, notes } = req.body

  if (req.user.role === 'supplier') {
    if (!req.user.supplier_id) {
      return res.status(400).json({ message: '供应商用户未关联供应商' })
    }
  }

  if (!office_id || !items || items.length === 0) {
    return res.status(400).json({ message: '收货办公区和发货明细不能为空' })
  }

  for (const item of items) {
    if (!item.sku_id || !item.quantity || item.quantity <= 0) {
      return res.status(400).json({ message: '发货明细格式错误' })
    }
  }

  const supplier_id = req.user.role === 'supplier' ? req.user.supplier_id : items[0].supplier_id

  // Generate Shanghai timezone timestamp
  const now = new Date()
  const pad = n => n.toString().padStart(2, '0')
  const shanghaiTs = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`

  db.prepare(`
    INSERT INTO shipments (supplier_id, office_id, recipient_id, carrier, tracking_number, items, notes, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    supplier_id,
    office_id,
    recipient_id || null,
    carrier || null,
    tracking_number || null,
    JSON.stringify(items),
    notes || null,
    shanghaiTs,
    shanghaiTs
  )

  const shipment = db.prepare(`
    SELECT sh.*,
           s.name as supplier_name,
           o.name as office_name,
           u.real_name as recipient_name
    FROM shipments sh
    JOIN suppliers s ON sh.supplier_id = s.id
    JOIN offices o ON sh.office_id = o.id
    LEFT JOIN users u ON sh.recipient_id = u.id
    WHERE sh.id = last_insert_rowid()
  `).get()

  res.json({ data: shipment })
})

// 更新发货记录
router.put('/:id', authMiddleware, roleMiddleware('admin', 'supplier'), (req, res) => {
  const db = getDB()
  const shipment = db.prepare('SELECT * FROM shipments WHERE id = ?').get(req.params.id)
  if (!shipment) {
    return res.status(404).json({ message: '发货记录不存在' })
  }

  if (req.user.role === 'supplier' && shipment.supplier_id !== req.user.supplier_id) {
    return res.status(403).json({ message: '权限不足' })
  }

  const { carrier, tracking_number, items, notes } = req.body

  const now = new Date()
  const pad = n => n.toString().padStart(2, '0')
  const shanghaiTs = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`

  db.prepare(`
    UPDATE shipments SET carrier = ?, tracking_number = ?, items = ?, notes = ?, updated_at = ?
    WHERE id = ?
  `).run(
    carrier ?? shipment.carrier,
    tracking_number ?? shipment.tracking_number,
    items ? JSON.stringify(items) : shipment.items,
    notes ?? shipment.notes,
    shanghaiTs,
    req.params.id
  )

  const updated = db.prepare(`
    SELECT sh.*,
           s.name as supplier_name,
           o.name as office_name,
           u.real_name as recipient_name
    FROM shipments sh
    JOIN suppliers s ON sh.supplier_id = s.id
    JOIN offices o ON sh.office_id = o.id
    LEFT JOIN users u ON sh.recipient_id = u.id
    WHERE sh.id = ?
  `).get(req.params.id)

  res.json({ data: updated })
})

// 录入物流信息
router.put('/:id/tracking', authMiddleware, roleMiddleware('admin', 'supplier'), (req, res) => {
  const db = getDB()
  const shipment = db.prepare('SELECT * FROM shipments WHERE id = ?').get(req.params.id)
  if (!shipment) {
    return res.status(404).json({ message: '发货记录不存在' })
  }

  if (req.user.role === 'supplier' && shipment.supplier_id !== req.user.supplier_id) {
    return res.status(403).json({ message: '权限不足' })
  }

  const { carrier, tracking_number } = req.body

  const now = new Date()
  const pad = n => n.toString().padStart(2, '0')
  const shanghaiTs = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`

  db.prepare(`
    UPDATE shipments SET carrier = ?, tracking_number = ?, updated_at = ?
    WHERE id = ?
  `).run(carrier || null, tracking_number || null, shanghaiTs, req.params.id)

  const updated = db.prepare(`
    SELECT sh.*,
           s.name as supplier_name,
           o.name as office_name,
           u.real_name as recipient_name
    FROM shipments sh
    JOIN suppliers s ON sh.supplier_id = s.id
    JOIN offices o ON sh.office_id = o.id
    LEFT JOIN users u ON sh.recipient_id = u.id
    WHERE sh.id = ?
  `).get(req.params.id)

  res.json({ data: updated })
})

// 确认入库
router.post('/:id/deliver', authMiddleware, roleMiddleware('admin', 'facility'), (req, res) => {
  const db = getDB()
  const shipment = db.prepare('SELECT * FROM shipments WHERE id = ?').get(req.params.id)
  if (!shipment) {
    return res.status(404).json({ message: '发货记录不存在' })
  }

  if (shipment.status === 'delivered') {
    return res.status(400).json({ message: '已经入库' })
  }

  const now = new Date()
  const pad = n => n.toString().padStart(2, '0')
  const shanghaiTs = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`

  const items = JSON.parse(shipment.items || '[]')
  for (const item of items) {
    const existing = db.prepare('SELECT * FROM inventory WHERE office_id = ? AND sku_id = ?').get(shipment.office_id, item.sku_id)
    if (existing) {
      db.prepare('UPDATE inventory SET quantity = quantity + ?, updated_at = ? WHERE office_id = ? AND sku_id = ?').run(item.quantity, shanghaiTs, shipment.office_id, item.sku_id)
    } else {
      db.prepare('INSERT INTO inventory (office_id, sku_id, quantity, updated_at) VALUES (?, ?, ?, ?)').run(shipment.office_id, item.sku_id, item.quantity, shanghaiTs)
    }
  }

  db.prepare(`
    UPDATE shipments SET status = 'delivered', storage_at = ?, updated_at = ?
    WHERE id = ?
  `).run(shanghaiTs, shanghaiTs, req.params.id)

  const updated = db.prepare(`
    SELECT sh.*,
           s.name as supplier_name,
           o.name as office_name,
           u.real_name as recipient_name
    FROM shipments sh
    JOIN suppliers s ON sh.supplier_id = s.id
    JOIN offices o ON sh.office_id = o.id
    LEFT JOIN users u ON sh.recipient_id = u.id
    WHERE sh.id = ?
  `).get(req.params.id)

  res.json({ data: updated })
})

module.exports = router
