const { initDB, saveDB } = require('./src/server/db/init')

async function main() {
  await initDB()
  const db = require('./src/server/db/init').getDB()

  // Inventory data: [office_id, sku_id, quantity]
  const inventory = [
    [3, 2, 1],  // 百度大厦 x ELPLP96
    [3, 4, 2],  // 百度大厦 x ELPLP85
    [3, 5, 2],  // 百度大厦 x ELPLP78
    [4, 2, 1],  // 科技园4号楼 x ELPLP96
    [4, 4, 1],  // 科技园4号楼 x ELPLP85
    [4, 5, 2],  // 科技园4号楼 x ELPLP78
    [5, 2, 2],  // 方舟大厦 x ELPLP96
    [5, 4, 2],  // 方舟大厦 x ELPLP85
    [5, 5, 1],  // 方舟大厦 x ELPLP78
  ]

  for (const [office_id, sku_id, quantity] of inventory) {
    // Check if exists
    const existing = db.db.exec(`SELECT * FROM inventory WHERE office_id=${office_id} AND sku_id=${sku_id}`)
    if (existing.length > 0 && existing[0].values.length > 0) {
      db.db.exec(`UPDATE inventory SET quantity=${quantity}, updated_at=CURRENT_TIMESTAMP WHERE office_id=${office_id} AND sku_id=${sku_id}`)
      console.log(`Updated: office ${office_id}, sku ${sku_id} -> ${quantity}`)
    } else {
      db.db.exec(`INSERT INTO inventory (office_id, sku_id, quantity) VALUES (${office_id}, ${sku_id}, ${quantity})`)
      console.log(`Inserted: office ${office_id}, sku ${sku_id} -> ${quantity}`)
    }
  }

  saveDB()
  console.log('Done!')
  process.exit(0)
}

main()
