const { initDB } = require('./src/server/db/init')

async function main() {
  await initDB()
  const db = require('./src/server/db/init').getDB()

  const users = db.db.exec('SELECT id, username, role, password_hash, real_name FROM users')
  console.log('Users:', JSON.stringify(users, null, 2))

  process.exit(0)
}

main()
