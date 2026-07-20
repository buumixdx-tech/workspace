const express = require('express')
const cors = require('cors')
const path = require('path')
const fs = require('fs')

// 初始化数据库
const { initDB, getDB, saveDB } = require('./db/init')

// 创建 Express 应用
const app = express()
const PORT = process.env.PORT || 3001

// 中间件
app.use(cors())
app.use(express.json())

// 确保上传目录存在
const uploadsDir = path.join(__dirname, '..', '..', 'uploads')
if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true })
}

// 静态文件服务
app.use('/uploads', express.static(path.join(__dirname, '..', '..', 'uploads')))
app.use(express.static(path.join(__dirname, '..', 'dist')))

// 路由（延迟加载，等数据库初始化完成）
let authRoutes, officesRoutes, meetingRoomsRoutes, skusRoutes, projectorsRoutes
let suppliersRoutes, inventoryRoutes, replacementsRoutes, shipmentsRoutes
let usersRoutes, reportsRoutes, importRoutes

// 健康检查
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() })
})

// 错误处理
app.use((err, req, res, next) => {
  console.error(err.stack)
  res.status(500).json({ message: '服务器内部错误' })
})

// 启动服务器
async function start() {
  await initDB()
  console.log('数据库初始化完成')

  // 路由（需要数据库准备好后加载）
  authRoutes = require('./routes/auth')
  officesRoutes = require('./routes/offices')
  meetingRoomsRoutes = require('./routes/meetingRooms')
  skusRoutes = require('./routes/skus')
  projectorsRoutes = require('./routes/projectors')
  suppliersRoutes = require('./routes/suppliers')
  inventoryRoutes = require('./routes/inventory')
  replacementsRoutes = require('./routes/replacements')
  shipmentsRoutes = require('./routes/shipments')
  usersRoutes = require('./routes/users')
  reportsRoutes = require('./routes/reports')
  importRoutes = require('./routes/import')

  app.use('/api/auth', authRoutes)
  app.use('/api/offices', officesRoutes)
  app.use('/api/meeting-rooms', meetingRoomsRoutes)
  app.use('/api/skus', skusRoutes)
  app.use('/api/projectors', projectorsRoutes)
  app.use('/api/suppliers', suppliersRoutes)
  app.use('/api/inventory', inventoryRoutes)
  app.use('/api/replacements', replacementsRoutes)
  app.use('/api/shipments', shipmentsRoutes)
  app.use('/api/users', usersRoutes)
  app.use('/api/reports', reportsRoutes)
  app.use('/api/import', importRoutes)

  // SPA 路由 - 所有非 API 路由返回 index.html
  app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, '..', 'dist', 'index.html'))
  })

  app.listen(PORT, () => {
    console.log(`服务器运行在 http://localhost:${PORT}`)
    console.log(`默认管理员账户: admin / admin123`)
  })
}

start().catch(err => {
  console.error('启动失败:', err)
  process.exit(1)
})
