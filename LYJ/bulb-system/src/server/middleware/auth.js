const jwt = require('jsonwebtoken')
const { getDB } = require('../db/init')

const JWT_SECRET = process.env.JWT_SECRET || 'bulb-system-secret-key'

// 验证 JWT token
function authMiddleware(req, res, next) {
  console.log('[DEBUG auth] path:', req.path, 'authHeader:', req.headers.authorization ? 'present' : 'missing')
  const authHeader = req.headers.authorization
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ message: '未登录' })
  }

  const token = authHeader.split(' ')[1]
  try {
    const decoded = jwt.verify(token, JWT_SECRET)
    const user = getDB().prepare(`
      SELECT u.*, o.name as office_name, s.name as supplier_name
      FROM users u
      LEFT JOIN offices o ON u.office_id = o.id
      LEFT JOIN suppliers s ON u.supplier_id = s.id
      WHERE u.id = ?
    `).get(decoded.userId)

    if (!user) {
      return res.status(401).json({ message: '用户不存在' })
    }
    req.user = user
    next()
  } catch (err) {
    return res.status(401).json({ message: 'token 无效' })
  }
}

// 角色权限验证
function roleMiddleware(...roles) {
  return (req, res, next) => {
    if (!roles.includes(req.user.role)) {
      return res.status(403).json({ message: '权限不足' })
    }
    next()
  }
}

// 生成 token
function generateToken(userId) {
  return jwt.sign({ userId }, JWT_SECRET, { expiresIn: '7d' })
}

module.exports = { authMiddleware, roleMiddleware, generateToken }
