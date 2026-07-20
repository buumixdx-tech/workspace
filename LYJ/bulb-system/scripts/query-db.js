const { initDB } = require('./src/server/db/init')

async function main() {
  await initDB()
  const db = require('./src/server/db/init').getDB()

  const skus = db.db.exec("SELECT id, name, type FROM skus WHERE type='bulb' ORDER BY id")
  console.log('SKUs:', JSON.stringify(skus, null, 2))

  const offices = db.db.exec("SELECT id, name FROM offices ORDER BY id")
  console.log('Offices:', JSON.stringify(offices, null, 2))

  process.exit(0)
}

main()
