const express = require('express')
const bcrypt = require('bcryptjs')
const { getDB, saveDB } = require('../db/init')
const { authMiddleware, generateToken } = require('../middleware/auth')

const router = express.Router()

// 登录
router.post('/login', (req, res) => {
  const { username, password } = req.body
  if (!username || !password) {
    return res.status(400).json({ message: '用户名和密码不能为空' })
  }

  const db = getDB()
  const stmt = db.prepare(`
    SELECT u.*, o.name as office_name, s.name as supplier_name
    FROM users u
    LEFT JOIN offices o ON u.office_id = o.id
    LEFT JOIN suppliers s ON u.supplier_id = s.id
    WHERE u.username = ?
  `)
  const user = stmt.get(username)

  if (!user) {
    return res.status(401).json({ message: '用户名或密码错误' })
  }

  const valid = bcrypt.compareSync(password, user.password_hash)
  if (!valid) {
    return res.status(401).json({ message: '用户名或密码错误' })
  }

  const token = generateToken(user.id)
  const { password_hash, ...userData } = user
  res.json({ token, data: userData })
})

// 登出
router.post('/logout', authMiddleware, (req, res) => {
  res.json({ message: '登出成功' })
})

// 获取当前用户
router.get('/me', authMiddleware, (req, res) => {
  res.json({ data: req.user })
})

module.exports = router
