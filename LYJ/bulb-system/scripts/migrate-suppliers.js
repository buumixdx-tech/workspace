const { initDB, saveDB } = require('./src/server/db/init')

async function migrate() {
  await initDB()
  const db = require('./src/server/db/init').getDB()

  console.log('Step 1: Rename old table')
  db.db.run('ALTER TABLE suppliers RENAME TO suppliers_old')

  console.log('Step 2: Create new table')
  db.db.run(`
    CREATE TABLE suppliers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      contact_user_id INTEGER,
      address TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (contact_user_id) REFERENCES users(id)
    )
  `)

  console.log('Step 3: Copy data')
  db.db.run(`
    INSERT INTO suppliers (id, name, address, created_at)
    SELECT id, name, address, created_at FROM suppliers_old
  `)

  console.log('Step 4: Drop old table')
  db.db.run('DROP TABLE suppliers_old')

  console.log('Step 5: Save database')
  saveDB()

  console.log('Migration complete!')
  process.exit(0)
}

migrate()
