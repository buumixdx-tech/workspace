const initSqlJs = require('sql.js')
const bcrypt = require('bcryptjs')
const fs = require('fs')
const path = require('path')

const dbPath = path.join(__dirname, '../../..', 'data', 'bulb.db')

let db = null

// 初始化数据库
async function initDB() {
  const SQL = await initSqlJs()

  // 确保 data 目录存在
  const dataDir = path.dirname(dbPath)
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true })
  }

  // 加载已有数据库或创建新数据库
  let sqliteDb
  if (fs.existsSync(dbPath)) {
    const buffer = fs.readFileSync(dbPath)
    sqliteDb = new SQL.Database(buffer)
  } else {
    sqliteDb = new SQL.Database()
  }

  // 使用 Database 包装类
  db = new Database(sqliteDb)

  // 启用外键
  db.exec('PRAGMA foreign_keys = ON')

  // 创建表
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE,
      password_hash TEXT,
      role TEXT NOT NULL CHECK(role IN ('admin', 'asset_manager', 'facility', 'supplier')),
      real_name TEXT,
      phone TEXT,
      email TEXT,
      office_id INTEGER,
      supplier_id INTEGER,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `)

  db.exec(`
    CREATE TABLE IF NOT EXISTS offices (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      location TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `)

  db.exec(`
    CREATE TABLE IF NOT EXISTS meeting_rooms (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      office_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      floor TEXT,
      capacity_normal INTEGER,
      capacity_max INTEGER,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (office_id) REFERENCES offices(id)
    )
  `)

  db.exec(`
    CREATE TABLE IF NOT EXISTS skus (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      type TEXT NOT NULL CHECK(type IN ('bulb', 'projector')),
      specs TEXT,
      compatible_model_ids TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `)

  db.exec(`
    CREATE TABLE IF NOT EXISTS projectors (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      asset_code TEXT UNIQUE NOT NULL,
      meeting_room_id INTEGER,
      sku_id INTEGER NOT NULL,
      status TEXT DEFAULT 'normal' CHECK(status IN ('normal', 'warning', 'offline')),
      notes TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (meeting_room_id) REFERENCES meeting_rooms(id),
      FOREIGN KEY (sku_id) REFERENCES skus(id)
    )
  `)

  db.exec(`
    CREATE TABLE IF NOT EXISTS suppliers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      contact_user_id INTEGER,
      address TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (contact_user_id) REFERENCES users(id)
    )
  `)

  db.exec(`
    CREATE TABLE IF NOT EXISTS inventory (
      office_id INTEGER,
      sku_id INTEGER,
      quantity INTEGER DEFAULT 0,
      min_stock INTEGER,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (office_id, sku_id),
      FOREIGN KEY (office_id) REFERENCES offices(id),
      FOREIGN KEY (sku_id) REFERENCES skus(id)
    )
  `)

  db.exec(`
    CREATE TABLE IF NOT EXISTS replacements (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      projector_id INTEGER NOT NULL,
      sku_id INTEGER NOT NULL,
      from_office_id INTEGER NOT NULL,
      operator_id INTEGER NOT NULL,
      replaced_at DATETIME NOT NULL,
      notes TEXT,
      photos TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (projector_id) REFERENCES projectors(id),
      FOREIGN KEY (sku_id) REFERENCES skus(id),
      FOREIGN KEY (from_office_id) REFERENCES offices(id),
      FOREIGN KEY (operator_id) REFERENCES users(id)
    )
  `)

  db.exec(`
    CREATE TABLE IF NOT EXISTS shipments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      supplier_id INTEGER NOT NULL,
      office_id INTEGER NOT NULL,
      recipient_id INTEGER,
      tracking_number TEXT,
      carrier TEXT,
      items TEXT NOT NULL,
      status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'delivered')),
      storage_at DATETIME,
      notes TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
      FOREIGN KEY (office_id) REFERENCES offices(id),
      FOREIGN KEY (recipient_id) REFERENCES users(id)
    )
  `)

  // 创建索引
  db.exec('CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)')
  db.exec('CREATE INDEX IF NOT EXISTS idx_users_office ON users(office_id)')
  db.exec('CREATE INDEX IF NOT EXISTS idx_meeting_rooms_office ON meeting_rooms(office_id)')
  db.exec('CREATE INDEX IF NOT EXISTS idx_projectors_meeting_room ON projectors(meeting_room_id)')
  db.exec('CREATE INDEX IF NOT EXISTS idx_inventory_office ON inventory(office_id)')
  db.exec('CREATE INDEX IF NOT EXISTS idx_replacements_projector ON replacements(projector_id)')
  db.exec('CREATE INDEX IF NOT EXISTS idx_replacements_operator ON replacements(operator_id)')
  db.exec('CREATE INDEX IF NOT EXISTS idx_shipments_supplier ON shipments(supplier_id)')
  db.exec('CREATE INDEX IF NOT EXISTS idx_shipments_office ON shipments(office_id)')

  // 初始化管理员账户
  initAdmin()

  // 迁移：投影仪-灯泡适配关系从 projectors.bulb_sku_ids 迁移到 skus.compatible_model_ids
  migrateProjectorBulbCompat()

  // 保存数据库
  saveDB()

  return db
}

function initAdmin() {
  const result = db.exec("SELECT id FROM users WHERE role = 'admin'", true)
  if (result.length === 0 || result[0].values.length === 0) {
    const hash = bcrypt.hashSync('admin123', 10)
    db.run("INSERT INTO users (username, password_hash, role, real_name) VALUES (?, ?, 'admin', '系统管理员')", ['admin', hash])
    console.log('默认管理员账户已创建: admin / admin123')
    saveDB()
  }
}

function migrateProjectorBulbCompat() {
  // 检查 projectors 表是否还有 bulb_sku_ids 字段（未迁移的标志）
  const cols = db.db.exec("PRAGMA table_info(projectors)")
  const hasOldField = cols[0]?.values.some(v => v[1] === 'bulb_sku_ids')
  if (!hasOldField) return // 已迁移

  // 检查 skus 表是否有 compatible_model_ids 字段
  const skuCols = db.db.exec("PRAGMA table_info(skus)")
  const hasNewField = skuCols[0]?.values.some(v => v[1] === 'compatible_model_ids')
  if (!hasNewField) {
    db.db.run("ALTER TABLE skus ADD COLUMN compatible_model_ids TEXT")
  }

  // 收集所有投影仪的 sku_id -> [bulb_sku_ids] 映射
  const projectors = db.db.exec("SELECT sku_id, bulb_sku_ids FROM projectors WHERE bulb_sku_ids IS NOT NULL AND bulb_sku_ids != 'null'")
  if (!projectors.length || !projectors[0].values.length) return

  // 按 sku_id 合并 bulb_sku_ids
  const compatMap = {}
  for (const [sku_id, bulb_sku_ids] of projectors[0].values) {
    if (!bulb_sku_ids) continue
    let bulbs
    try { bulbs = JSON.parse(bulb_sku_ids) } catch { continue }
    if (!Array.isArray(bulbs)) continue
    if (!compatMap[sku_id]) compatMap[sku_id] = new Set()
    bulbs.forEach(b => compatMap[sku_id].add(b))
  }

  // 写入 skus 表
  for (const [skuId, bulbSet] of Object.entries(compatMap)) {
    const ids = JSON.stringify([...bulbSet])
    db.db.run("UPDATE skus SET compatible_model_ids = ? WHERE id = ? AND type = 'projector'", [ids, parseInt(skuId)])
  }

  // 重构 projectors 表（SQLite 不支持 DROP COLUMN，需重建）
  const tmp = db.db.exec("SELECT * FROM projectors LIMIT 0")[0]
  const colNames = tmp ? tmp.columns : ['id', 'asset_code', 'meeting_room_id', 'sku_id', 'status', 'notes', 'created_at']
  const colsToKeep = colNames.filter(c => c !== 'bulb_sku_ids')
  const colsStr = colsToKeep.join(', ')

  db.db.run("CREATE TABLE projectors_new AS SELECT " + colsStr + " FROM projectors")
  db.db.run("DROP TABLE projectors")
  db.db.run("ALTER TABLE projectors_new RENAME TO projectors")
  // 重建索引
  db.db.run("CREATE INDEX IF NOT EXISTS idx_projectors_meeting_room ON projectors(meeting_room_id)")

  saveDB()
  console.log('投影仪-灯泡适配关系已迁移到 skus 表')
}

function saveDB() {
  if (db && db.sqliteDb) {
    const data = db.sqliteDb.export()
    const buffer = Buffer.from(data)
    fs.writeFileSync(dbPath, buffer)
  }
}

// 数据库包装对象，提供同步接口
class Database {
  constructor(sqliteDb) {
    this.db = sqliteDb
    this.sqliteDb = sqliteDb
  }

  prepare(sql) {
    return new Statement(this.db, sql)
  }

  exec(sql, returnResult = false) {
    this.db.run(sql)
    saveDB()
    if (returnResult) {
      return this.db.exec(sql)
    }
  }

  run(sql, params = []) {
    if (params.length > 0) {
      this.db.run(sql, params)
    } else {
      this.db.run(sql)
    }
    saveDB()
  }
}

class Statement {
  constructor(db, sql) {
    this.db = db
    this.sql = sql
  }

  run(...params) {
    this.db.run(this.sql, params)
    saveDB()
    const lir = this.db.exec('SELECT last_insert_rowid()')
    return { lastInsertRowid: lir[0]?.values[0]?.[0] || 0 }
  }

  get(...params) {
    const stmt = this.db.prepare(this.sql)
    if (params.length > 0) {
      stmt.bind(params)
    }
    if (stmt.step()) {
      const row = stmt.getAsObject()
      stmt.free()
      return row
    }
    stmt.free()
    return undefined
  }

  all(...params) {
    const result = []
    const stmt = this.db.prepare(this.sql)
    stmt.bind(params)
    while (stmt.step()) {
      result.push(stmt.getAsObject())
    }
    stmt.free()
    return result
  }
}

// 获取数据库实例
function getDB() {
  return db
}

module.exports = { initDB, getDB, saveDB }
