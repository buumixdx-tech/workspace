const { initDB } = require('./src/server/db/init');

async function main() {
  await initDB();
  const db = require('./src/server/db/init').getDB();

  console.log('SKUs:', JSON.stringify(db.db.exec("SELECT * FROM skus WHERE type='bulb'"), null, 2));
  console.log('Offices:', JSON.stringify(db.db.exec("SELECT * FROM offices"), null, 2));
  console.log('Inventory:', JSON.stringify(db.db.exec("SELECT * FROM inventory"), null, 2));

  process.exit(0);
}

main();