const express = require('express')
const multer = require('multer')
const XLSX = require('xlsx')
const { getDB } = require('../db/init')
const { authMiddleware, roleMiddleware } = require('../middleware/auth')
const bcrypt = require('bcryptjs')

const router = express.Router()

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 }
})

// 校验错误类
class ValidationError extends Error {
  constructor(message, rowNum) {
    super(message)
    this.rowNum = rowNum
    this.type = 'ValidationError'
  }
}

// 辅助函数：根据名称查FK，必须存在否则报错
function lookupFK(db, table, nameCol, nameVal, label, rowNum) {
  if (!nameVal) return null
  const row = db.prepare(`SELECT id FROM ${table} WHERE ${nameCol} = ?`).get(nameVal)
  if (!row) {
    throw new ValidationError(`${label}「${nameVal}」不存在`, rowNum)
  }
  return row.id
}

async function importData(type, req, res) {
  if (!req.file) {
    return res.status(400).json({ message: '请上传文件' })
  }

  const workbook = XLSX.read(req.file.buffer, { type: 'buffer' })
  const sheetName = workbook.SheetNames[0]
  const data = XLSX.utils.sheet_to_json(workbook.Sheets[sheetName])

  if (data.length === 0) {
    return res.status(400).json({ message: '文件为空' })
  }

  const db = getDB()
  let count = 0
  const errors = []

  try {
    switch (type) {
      case 'offices':
        for (let i = 0; i < data.length; i++) {
          const row = data[i]
          const rowNum = i + 2
          try {
            const name = row['名称'] || row['name']
            const location = row['位置'] || row['location']

            if (!name) {
              errors.push(`行 ${rowNum}: 缺少必填字段「名称」`)
              continue
            }
            if (location && typeof location !== 'string') {
              errors.push(`行 ${rowNum}: 「位置」必须为文本`)
              continue
            }

            const existing = db.prepare('SELECT id FROM offices WHERE name = ?').get(name)
            if (existing) {
              db.prepare('UPDATE offices SET location = ? WHERE name = ?').run(location || null, name)
            } else {
              db.prepare('INSERT INTO offices (name, location) VALUES (?, ?)').run(name, location || null)
            }
            count++
          } catch (e) {
            errors.push(`行 ${rowNum}: ${e.message}`)
          }
        }
        break

      case 'meeting_rooms':
        for (let i = 0; i < data.length; i++) {
          const row = data[i]
          const rowNum = i + 2
          try {
            const name = row['会议室名称'] || row['name']
            const office_name = row['所属办公区名称'] || row['office_name']
            const floor = row['楼层'] || row['floor']
            const capacity_normal = row['正常容纳人数'] || row['capacity_normal']
            const capacity_max = row['最大容纳人数'] || row['capacity_max']

            if (!name) {
              errors.push(`行 ${rowNum}: 缺少必填字段「会议室名称」`)
              continue
            }
            if (!office_name) {
              errors.push(`行 ${rowNum}: 缺少必填字段「所属办公区名称」`)
              continue
            }

            // FK校验：办公区必须存在
            const office_id = lookupFK(db, 'offices', 'name', office_name, '办公区', rowNum)

            if (capacity_normal !== undefined && capacity_normal !== '' && isNaN(parseInt(capacity_normal))) {
              errors.push(`行 ${rowNum}: 「正常容纳人数」必须为数字`)
              continue
            }
            if (capacity_max !== undefined && capacity_max !== '' && isNaN(parseInt(capacity_max))) {
              errors.push(`行 ${rowNum}: 「最大容纳人数」必须为数字`)
              continue
            }

            const existing = db.prepare('SELECT id FROM meeting_rooms WHERE office_id = ? AND name = ?').get(office_id, name)
            if (existing) {
              db.prepare('UPDATE meeting_rooms SET floor = ?, capacity_normal = ?, capacity_max = ? WHERE id = ?')
                .run(floor || null, parseInt(capacity_normal) || null, parseInt(capacity_max) || null, existing.id)
            } else {
              db.prepare('INSERT INTO meeting_rooms (office_id, name, floor, capacity_normal, capacity_max) VALUES (?, ?, ?, ?, ?)')
                .run(office_id, name, floor || null, parseInt(capacity_normal) || null, parseInt(capacity_max) || null)
            }
            count++
          } catch (e) {
            if (e.type === 'ValidationError') {
              errors.push(`行 ${e.rowNum}: ${e.message}`)
            } else {
              errors.push(`行 ${rowNum}: ${e.message}`)
            }
          }
        }
        break

      case 'skus':
        const validSkuTypes = ['bulb', 'projector']
        for (let i = 0; i < data.length; i++) {
          const row = data[i]
          const rowNum = i + 2
          try {
            const name = row['型号名称'] || row['name']
            const skuType = row['类型'] || row['type']
            const specs = row['规格参数(JSON)'] || row['specs']

            if (!name) {
              errors.push(`行 ${rowNum}: 缺少必填字段「型号名称」`)
              continue
            }
            if (!skuType) {
              errors.push(`行 ${rowNum}: 缺少必填字段「类型」`)
              continue
            }
            if (!validSkuTypes.includes(skuType)) {
              errors.push(`行 ${rowNum}: 「类型」值「${skuType}」不在允许范围内（${validSkuTypes.join('、')}）`)
              continue
            }

            const existing = db.prepare('SELECT id FROM skus WHERE name = ?').get(name)
            if (existing) {
              db.prepare('UPDATE skus SET type = ?, specs = ? WHERE name = ?').run(skuType, specs || null, name)
            } else {
              db.prepare('INSERT INTO skus (name, type, specs) VALUES (?, ?, ?)').run(name, skuType, specs || null)
            }
            count++
          } catch (e) {
            errors.push(`行 ${rowNum}: ${e.message}`)
          }
        }
        break

      case 'projectors':
        const validStatuses = ['normal', 'repair', 'scrapped']
        for (let i = 0; i < data.length; i++) {
          const row = data[i]
          const rowNum = i + 2
          try {
            const asset_code = row['资产编码'] || row['asset_code']
            const sku_name = row['投影仪SKU名称'] || row['sku_name']
            const meeting_room_name = row['所属会议室'] || row['meeting_room']
            const status = row['状态'] || row['status'] || 'normal'
            const notes = row['备注'] || row['notes']

            if (!asset_code) {
              errors.push(`行 ${rowNum}: 缺少必填字段「资产编码」`)
              continue
            }
            if (!sku_name) {
              errors.push(`行 ${rowNum}: 缺少必填字段「投影仪SKU名称」`)
              continue
            }
            if (!validStatuses.includes(status)) {
              errors.push(`行 ${rowNum}: 「状态」值「${status}」不在允许范围内（${validStatuses.join('、')}）`)
              continue
            }

            // FK校验：投影仪SKU必须存在且类型为projector
            const sku = db.prepare("SELECT id FROM skus WHERE name = ? AND type = 'projector'").get(sku_name)
            if (!sku) {
              errors.push(`行 ${rowNum}: 投影仪SKU「${sku_name}」不存在或类型不是投影仪`)
              continue
            }

            // FK校验（可选）：会议室
            let meeting_room_id = null
            if (meeting_room_name) {
              meeting_room_id = lookupFK(db, 'meeting_rooms', 'name', meeting_room_name, '会议室', rowNum)
            }

            const existing = db.prepare('SELECT id FROM projectors WHERE asset_code = ?').get(asset_code)
            if (existing) {
              db.prepare('UPDATE projectors SET meeting_room_id = ?, sku_id = ?, status = ?, notes = ? WHERE asset_code = ?')
                .run(meeting_room_id, sku.id, status, notes || null, asset_code)
            } else {
              db.prepare('INSERT INTO projectors (asset_code, meeting_room_id, sku_id, status, notes) VALUES (?, ?, ?, ?, ?)')
                .run(asset_code, meeting_room_id, sku.id, status, notes || null)
            }
            count++
          } catch (e) {
            if (e.type === 'ValidationError') {
              errors.push(`行 ${e.rowNum}: ${e.message}`)
            } else {
              errors.push(`行 ${rowNum}: ${e.message}`)
            }
          }
        }
        break

      case 'suppliers':
        for (let i = 0; i < data.length; i++) {
          const row = data[i]
          const rowNum = i + 2
          try {
            const name = row['供应商名称'] || row['name']
            const address = row['地址'] || row['address']

            if (!name) {
              errors.push(`行 ${rowNum}: 缺少必填字段「供应商名称」`)
              continue
            }

            const existing = db.prepare('SELECT id FROM suppliers WHERE name = ?').get(name)
            if (existing) {
              db.prepare('UPDATE suppliers SET address = ? WHERE name = ?').run(address || null, name)
            } else {
              db.prepare('INSERT INTO suppliers (name, address) VALUES (?, ?)').run(name, address || null)
            }
            count++
          } catch (e) {
            errors.push(`行 ${rowNum}: ${e.message}`)
          }
        }
        break

      case 'users':
        const validRoles = ['admin', 'asset_manager', 'facility', 'supplier']
        for (let i = 0; i < data.length; i++) {
          const row = data[i]
          const rowNum = i + 2
          try {
            const username = row['用户名'] || row['username']
            const password = row['密码'] || row['password']
            const role = row['角色'] || row['role']
            const real_name = row['姓名'] || row['real_name']
            const phone = row['手机'] || row['phone']
            const email = row['邮箱'] || row['email']
            const office_name = row['所属办公区名称'] || row['office_name']
            const supplier_name = row['供应商名称'] || row['supplier_name']

            if (!username) {
              errors.push(`行 ${rowNum}: 缺少必填字段「用户名」`)
              continue
            }
            if (!password) {
              errors.push(`行 ${rowNum}: 缺少必填字段「密码」`)
              continue
            }
            if (!role) {
              errors.push(`行 ${rowNum}: 缺少必填字段「角色」`)
              continue
            }
            if (!validRoles.includes(role)) {
              errors.push(`行 ${rowNum}: 「角色」值「${role}」不在允许范围内（${validRoles.join('、')}）`)
              continue
            }

            // FK校验（可选）：办公区
            let office_id = null
            if (office_name) {
              office_id = lookupFK(db, 'offices', 'name', office_name, '办公区', rowNum)
            }

            // FK校验（可选）：供应商
            let supplier_id = null
            if (supplier_name) {
              supplier_id = lookupFK(db, 'suppliers', 'name', supplier_name, '供应商', rowNum)
            }

            const hash = bcrypt.hashSync(password, 10)

            const existing = db.prepare('SELECT id FROM users WHERE username = ?').get(username)
            if (existing) {
              db.prepare('UPDATE users SET role = ?, real_name = ?, phone = ?, email = ?, office_id = ?, supplier_id = ? WHERE username = ?')
                .run(role, real_name || null, phone || null, email || null, office_id, supplier_id, username)
            } else {
              db.prepare('INSERT INTO users (username, password_hash, role, real_name, phone, email, office_id, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)')
                .run(username, hash, role, real_name || null, phone || null, email || null, office_id, supplier_id)
            }
            count++
          } catch (e) {
            if (e.type === 'ValidationError') {
              errors.push(`行 ${e.rowNum}: ${e.message}`)
            } else {
              errors.push(`行 ${rowNum}: ${e.message}`)
            }
          }
        }
        break

      case 'inventory':
        for (let i = 0; i < data.length; i++) {
          const row = data[i]
          const rowNum = i + 2
          try {
            const office_name = row['办公区名称'] || row['office_name']
            const sku_name = row['SKU名称'] || row['sku_name']
            const quantity = row['数量'] || row['quantity']
            const min_stock = row['警戒线'] || row['min_stock']

            if (!office_name) {
              errors.push(`行 ${rowNum}: 缺少必填字段「办公区名称」`)
              continue
            }
            if (!sku_name) {
              errors.push(`行 ${rowNum}: 缺少必填字段「SKU名称」`)
              continue
            }
            if (quantity === undefined || quantity === '' || isNaN(parseInt(quantity))) {
              errors.push(`行 ${rowNum}: 「数量」必须为数字`)
              continue
            }
            if (min_stock !== undefined && min_stock !== '' && isNaN(parseInt(min_stock))) {
              errors.push(`行 ${rowNum}: 「警戒线」必须为数字`)
              continue
            }

            // FK校验：办公区必须存在
            const office_id = lookupFK(db, 'offices', 'name', office_name, '办公区', rowNum)
            // FK校验：SKU必须存在
            const sku_id = lookupFK(db, 'skus', 'name', sku_name, 'SKU', rowNum)

            const existing = db.prepare('SELECT id FROM inventory WHERE office_id = ? AND sku_id = ?').get(office_id, sku_id)
            const now = new Date()
            const pad = n => String(n).padStart(2, '0')
            const shanghaiTs = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`

            if (existing) {
              db.prepare('UPDATE inventory SET quantity = ?, min_stock = ?, updated_at = ? WHERE office_id = ? AND sku_id = ?')
                .run(parseInt(quantity), parseInt(min_stock) || null, shanghaiTs, office_id, sku_id)
            } else {
              db.prepare('INSERT INTO inventory (office_id, sku_id, quantity, min_stock, updated_at) VALUES (?, ?, ?, ?, ?)')
                .run(office_id, sku_id, parseInt(quantity), parseInt(min_stock) || null, shanghaiTs)
            }
            count++
          } catch (e) {
            if (e.type === 'ValidationError') {
              errors.push(`行 ${e.rowNum}: ${e.message}`)
            } else {
              errors.push(`行 ${rowNum}: ${e.message}`)
            }
          }
        }
        break

      default:
        return res.status(400).json({ message: '不支持的导入类型' })
    }

    if (errors.length > 0) {
      return res.status(400).json({
        data: { count, errors: errors.slice(0, 20) },
        message: `导入失败，共 ${errors.length} 个错误`
      })
    }

    res.json({
      data: { count },
      message: `成功导入 ${count} 条记录`
    })
  } catch (err) {
    res.status(500).json({ message: '导入失败: ' + err.message })
  }
}

router.post('/offices', authMiddleware, roleMiddleware('admin', 'asset_manager'), upload.single('file'), (req, res) => importData('offices', req, res))
router.post('/meeting_rooms', authMiddleware, roleMiddleware('admin', 'asset_manager'), upload.single('file'), (req, res) => importData('meeting_rooms', req, res))
router.post('/skus', authMiddleware, roleMiddleware('admin', 'asset_manager'), upload.single('file'), (req, res) => importData('skus', req, res))
router.post('/projectors', authMiddleware, roleMiddleware('admin', 'asset_manager'), upload.single('file'), (req, res) => importData('projectors', req, res))
router.post('/suppliers', authMiddleware, roleMiddleware('admin', 'asset_manager'), upload.single('file'), (req, res) => importData('suppliers', req, res))
router.post('/users', authMiddleware, roleMiddleware('admin'), upload.single('file'), (req, res) => importData('users', req, res))
router.post('/inventory', authMiddleware, roleMiddleware('admin'), upload.single('file'), (req, res) => importData('inventory', req, res))

// 导出
router.get('/export/:type', authMiddleware, roleMiddleware('admin'), (req, res) => {
  const db = getDB()
  const { type } = req.params

  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  const ts = `${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}`

  const workbook = XLSX.utils.book_new()
  let filename = `${ts}_全部数据.xlsx`

  if (type === '__all__') {
    // 所有类型分Sheet
    const sheets = [
      { name: '办公区', sql: 'SELECT id, name, location, created_at FROM offices ORDER BY id' },
      { name: '会议室', sql: `SELECT mr.id, o.name as office_name, mr.name, mr.floor, mr.capacity_normal, mr.capacity_max, mr.created_at FROM meeting_rooms mr JOIN offices o ON mr.office_id = o.id ORDER BY mr.id` },
      { name: 'SKU', sql: 'SELECT id, name, type, specs, compatible_model_ids, created_at FROM skus ORDER BY id' },
      { name: '投影仪', sql: `SELECT p.id, p.asset_code, mr.name as meeting_room_name, o.name as office_name, s.name as projector_sku_name, p.status, p.notes, p.created_at FROM projectors p LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id LEFT JOIN offices o ON mr.office_id = o.id JOIN skus s ON p.sku_id = s.id ORDER BY p.id` },
      { name: '供应商', sql: 'SELECT id, name, address, created_at FROM suppliers ORDER BY id' },
      { name: '用户', sql: `SELECT u.id, u.username, u.role, u.real_name, u.phone, u.email, o.name as office_name, s.name as supplier_name, u.created_at FROM users u LEFT JOIN offices o ON u.office_id = o.id LEFT JOIN suppliers s ON u.supplier_id = s.id ORDER BY u.id` },
      { name: '库存', sql: `SELECT o.name as office_name, s.name as sku_name, s.type as sku_type, i.quantity, i.min_stock, i.updated_at FROM inventory i JOIN offices o ON i.office_id = o.id JOIN skus s ON i.sku_id = s.id ORDER BY o.id, s.id` },
      { name: '更换记录', sql: `SELECT r.id, p.asset_code as projector_code, mr.name as meeting_room_name, s.name as bulb_sku_name, r.replaced_at, r.notes, u.real_name as operator_name, r.created_at FROM replacements r JOIN projectors p ON r.projector_id = p.id LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id JOIN skus s ON r.sku_id = s.id JOIN users u ON r.operator_id = u.id ORDER BY r.id DESC` },
      { name: '供货记录', sql: `SELECT sh.id, sh.status, sup.name as supplier_name, o.name as office_name, u.real_name as recipient_name, sh.carrier, sh.tracking_number, sh.items, sh.notes, sh.created_at, sh.storage_at FROM shipments sh JOIN suppliers sup ON sh.supplier_id = sup.id JOIN offices o ON sh.office_id = o.id LEFT JOIN users u ON sh.recipient_id = u.id ORDER BY sh.id DESC` },
    ]

    for (const sheet of sheets) {
      const data = db.prepare(sheet.sql).all()
      const worksheet = XLSX.utils.json_to_sheet(data)
      XLSX.utils.book_append_sheet(workbook, worksheet, sheet.name)
    }
  } else {
    let data, sheetName
    switch (type) {
      case 'offices':
        data = db.prepare('SELECT id, name, location, created_at FROM offices ORDER BY id').all()
        sheetName = '办公区'
        break
      case 'meeting_rooms':
        data = db.prepare(`SELECT mr.id, o.name as office_name, mr.name, mr.floor, mr.capacity_normal, mr.capacity_max, mr.created_at FROM meeting_rooms mr JOIN offices o ON mr.office_id = o.id ORDER BY mr.id`).all()
        sheetName = '会议室'
        break
      case 'skus':
        data = db.prepare('SELECT id, name, type, specs, compatible_model_ids, created_at FROM skus ORDER BY id').all()
        sheetName = 'SKU'
        break
      case 'projectors':
        data = db.prepare(`SELECT p.id, p.asset_code, mr.name as meeting_room_name, o.name as office_name, s.name as projector_sku_name, p.status, p.notes, p.created_at FROM projectors p LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id LEFT JOIN offices o ON mr.office_id = o.id JOIN skus s ON p.sku_id = s.id ORDER BY p.id`).all()
        sheetName = '投影仪'
        break
      case 'suppliers':
        data = db.prepare('SELECT id, name, address, created_at FROM suppliers ORDER BY id').all()
        sheetName = '供应商'
        break
      case 'users':
        data = db.prepare(`SELECT u.id, u.username, u.role, u.real_name, u.phone, u.email, o.name as office_name, s.name as supplier_name, u.created_at FROM users u LEFT JOIN offices o ON u.office_id = o.id LEFT JOIN suppliers s ON u.supplier_id = s.id ORDER BY u.id`).all()
        sheetName = '用户'
        break
      case 'inventory':
        data = db.prepare(`SELECT o.name as office_name, s.name as sku_name, s.type as sku_type, i.quantity, i.min_stock, i.updated_at FROM inventory i JOIN offices o ON i.office_id = o.id JOIN skus s ON i.sku_id = s.id ORDER BY o.id, s.id`).all()
        sheetName = '库存'
        break
      case 'replacements':
        data = db.prepare(`SELECT r.id, p.asset_code as projector_code, mr.name as meeting_room_name, s.name as bulb_sku_name, r.replaced_at, r.notes, u.real_name as operator_name, r.created_at FROM replacements r JOIN projectors p ON r.projector_id = p.id LEFT JOIN meeting_rooms mr ON p.meeting_room_id = mr.id JOIN skus s ON r.sku_id = s.id JOIN users u ON r.operator_id = u.id ORDER BY r.id DESC`).all()
        sheetName = '更换记录'
        break
      case 'shipments':
        data = db.prepare(`SELECT sh.id, sh.status, sup.name as supplier_name, o.name as office_name, u.real_name as recipient_name, sh.carrier, sh.tracking_number, sh.items, sh.notes, sh.created_at, sh.storage_at FROM shipments sh JOIN suppliers sup ON sh.supplier_id = sup.id JOIN offices o ON sh.office_id = o.id LEFT JOIN users u ON sh.recipient_id = u.id ORDER BY sh.id DESC`).all()
        sheetName = '供货记录'
        break
      default:
        return res.status(400).json({ message: '不支持的导出类型' })
    }
    const worksheet = XLSX.utils.json_to_sheet(data)
    XLSX.utils.book_append_sheet(workbook, worksheet, sheetName)
    filename = `${sheetName}_${ts}.xlsx`
  }

  const buffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' })

  res.setHeader('Content-Disposition', `attachment; filename*=UTF-8''${encodeURIComponent(filename)}`)
  res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
  res.send(buffer)
})

module.exports = router
