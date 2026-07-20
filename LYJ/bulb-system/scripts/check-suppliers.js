const { initDB } = require('./src/server/db/init')

async function check() {
  await initDB()
  const db = require('./src/server/db/init').getDB()

  const r = db.db.exec('PRAGMA table_info(suppliers)')
  console.log('Table structure:', JSON.stringify(r, null, 2))

  const suppliers = db.db.exec('SELECT * FROM suppliers')
  console.log('Suppliers:', JSON.stringify(suppliers, null, 2))

  process.exit(0)
}

check()
