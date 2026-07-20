const express = require('express')
const bcrypt = require('bcryptjs')
const { getDB } = require('../db/init')
const { authMiddleware, roleMiddleware } = require('../middleware/auth')

const router = express.Router()

// 获取用户列表
router.get('/', authMiddleware, (req, res) => {
  const db = getDB()
  const { role } = req.query
  let users

  if (role) {
    users = db.prepare(`
      SELECT u.id, u.username, u.role, u.real_name, u.phone, u.email, u.office_id, u.supplier_id,
             o.name as office_name, s.name as supplier_name, u.created_at
      FROM users u
      LEFT JOIN offices o ON u.office_id = o.id
      LEFT JOIN suppliers s ON u.supplier_id = s.id
      WHERE u.role = ?
      ORDER BY u.role, u.username
    `).all(role)
  } else {
    // 非 admin 只能看自己和同角色的用户
    if (req.user.role !== 'admin') {
      return res.status(403).json({ message: '权限不足' })
    }
    users = db.prepare(`
      SELECT u.id, u.username, u.role, u.real_name, u.phone, u.email, u.office_id, u.supplier_id,
             o.name as office_name, s.name as supplier_name, u.created_at
      FROM users u
      LEFT JOIN offices o ON u.office_id = o.id
      LEFT JOIN suppliers s ON u.supplier_id = s.id
      ORDER BY u.role, u.username
    `).all()
  }

  res.json({ data: users })
})

// 获取单个用户
router.get('/:id', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const user = db.prepare(`
    SELECT u.id, u.username, u.role, u.real_name, u.phone, u.email, u.office_id, u.supplier_id,
           o.name as office_name, s.name as supplier_name, u.created_at
    FROM users u
    LEFT JOIN offices o ON u.office_id = o.id
    LEFT JOIN suppliers s ON u.supplier_id = s.id
    WHERE u.id = ?
  `).get(req.params.id)

  if (!user) {
    return res.status(404).json({ message: '用户不存在' })
  }
  res.json({ data: user })
})

// 创建用户
router.post('/', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const { username, password, role, real_name, phone, email, office_id, supplier_id } = req.body

  if (!role) {
    return res.status(400).json({ message: '角色不能为空' })
  }

  if (!['admin', 'asset_manager', 'facility', 'supplier'].includes(role)) {
    return res.status(400).json({ message: '无效的角色' })
  }

  // 用户名和密码必须同时存在或同时为空
  if ((username && !password) || (!username && password)) {
    return res.status(400).json({ message: '用户名和密码必须同时填写或同时为空' })
  }

  if (office_id) {
    const office = db.prepare('SELECT id FROM offices WHERE id = ?').get(office_id)
    if (!office) {
      return res.status(400).json({ message: '办公区不存在' })
    }
  }

  if (supplier_id) {
    const supplier = db.prepare('SELECT id FROM suppliers WHERE id = ?').get(supplier_id)
    if (!supplier) {
      return res.status(400).json({ message: '供应商不存在' })
    }
  }

  const hash = password ? bcrypt.hashSync(password, 10) : null

  try {
    db.prepare(`
      INSERT INTO users (username, password_hash, role, real_name, phone, email, office_id, supplier_id)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(username || null, hash, role, real_name || null, phone || null, email || null, office_id || null, supplier_id || null)

    // 获取刚插入的用户（通过real_name + role + created_at最近来定位，因为没有username时无法用username查询）
    const user = db.prepare(`
      SELECT u.id, u.username, u.role, u.real_name, u.phone, u.email, u.office_id, u.supplier_id,
             o.name as office_name, s.name as supplier_name, u.created_at
      FROM users u
      LEFT JOIN offices o ON u.office_id = o.id
      LEFT JOIN suppliers s ON u.supplier_id = s.id
      WHERE u.real_name IS ? AND u.role = ?
      ORDER BY u.id DESC LIMIT 1
    `).get(real_name || null, role)

    res.json({ data: user })
  } catch (err) {
    if (err.message.includes('UNIQUE')) {
      return res.status(400).json({ message: '用户名已存在' })
    }
    throw err
  }
})

// 更新用户
router.put('/:id', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const { role, real_name, phone, email, office_id, supplier_id, password } = req.body

  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id)
  if (!user) {
    return res.status(404).json({ message: '用户不存在' })
  }

  if (password) {
    const hash = bcrypt.hashSync(password, 10)
    db.prepare('UPDATE users SET role = ?, real_name = ?, phone = ?, email = ?, office_id = ?, supplier_id = ?, password_hash = ? WHERE id = ?')
      .run(role || user.role, real_name || user.real_name, phone || user.phone, email || user.email, office_id ?? user.office_id, supplier_id ?? user.supplier_id, hash, req.params.id)
  } else {
    db.prepare('UPDATE users SET role = ?, real_name = ?, phone = ?, email = ?, office_id = ?, supplier_id = ? WHERE id = ?')
      .run(role || user.role, real_name || user.real_name, phone || user.phone, email || user.email, office_id ?? user.office_id, supplier_id ?? user.supplier_id, req.params.id)
  }

  const updated = db.prepare(`
    SELECT u.id, u.username, u.role, u.real_name, u.phone, u.email, u.office_id, u.supplier_id,
           o.name as office_name, s.name as supplier_name, u.created_at
    FROM users u
    LEFT JOIN offices o ON u.office_id = o.id
    LEFT JOIN suppliers s ON u.supplier_id = s.id
    WHERE u.id = ?
  `).get(req.params.id)

  res.json({ data: updated })
})

// 重置用户名和密码
router.put('/:id/password', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const { username, password } = req.body

  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id)
  if (!user) {
    return res.status(404).json({ message: '用户不存在' })
  }

  // 用户名和密码不能同时为空
  if (!username && !password) {
    return res.status(400).json({ message: '用户名和密码不能同时为空' })
  }

  // 如果提供了用户名，检查是否与其他用户冲突
  if (username && username !== user.username) {
    const existing = db.prepare('SELECT id FROM users WHERE username = ? AND id != ?').get(username, req.params.id)
    if (existing) {
      return res.status(400).json({ message: '用户名已存在' })
    }
  }

  if (password) {
    const hash = bcrypt.hashSync(password, 10)
    db.prepare('UPDATE users SET username = ?, password_hash = ? WHERE id = ?')
      .run(username || user.username, hash, req.params.id)
  } else {
    db.prepare('UPDATE users SET username = ? WHERE id = ?')
      .run(username || user.username, req.params.id)
  }

  const updated = db.prepare(`
    SELECT u.id, u.username, u.role, u.real_name, u.phone, u.email, u.office_id, u.supplier_id,
           o.name as office_name, s.name as supplier_name, u.created_at
    FROM users u
    LEFT JOIN offices o ON u.office_id = o.id
    LEFT JOIN suppliers s ON u.supplier_id = s.id
    WHERE u.id = ?
  `).get(req.params.id)

  res.json({ data: updated })
})

// 删除用户
router.delete('/:id', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  if (req.params.id == req.user.id) {
    return res.status(400).json({ message: '不能删除自己' })
  }

  db.prepare('DELETE FROM users WHERE id = ?').run(req.params.id)
  res.json({ message: '删除成功' })
})

module.exports = router
