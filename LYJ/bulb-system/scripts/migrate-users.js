const { initDB, saveDB } = require('./src/server/db/init')

async function migrate() {
  await initDB()
  const db = require('./src/server/db/init').getDB()

  console.log('Step 1: Rename old table')
  db.db.run('ALTER TABLE users RENAME TO users_old')

  console.log('Step 2: Create new table')
  db.db.run(`
    CREATE TABLE users (
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

  console.log('Step 3: Copy data')
  db.db.run(`
    INSERT INTO users (id, username, password_hash, role, real_name, phone, email, office_id, supplier_id, created_at)
    SELECT id, username, password_hash, role, real_name, phone, email, office_id, supplier_id, created_at FROM users_old
  `)

  console.log('Step 4: Drop old table')
  db.db.run('DROP TABLE users_old')

  console.log('Step 5: Save database')
  saveDB()

  console.log('Migration complete!')
  process.exit(0)
}

migrate()
