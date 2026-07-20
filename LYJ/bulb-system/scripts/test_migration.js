const { initDB } = require('./src/server/db/init');

async function main() {
  await initDB();
  const db = require('./src/server/db/init').getDB();

  const skusCols = db.db.exec('PRAGMA table_info(skus)');
  console.log('SKUs columns:', skusCols[0]?.values.map(v => v[1]));

  const projCols = db.db.exec('PRAGMA table_info(projectors)');
  console.log('Projectors columns:', projCols[0]?.values.map(v => v[1]));

  const compat = db.db.exec('SELECT id, name, type, compatible_model_ids FROM skus WHERE type="projector"');
  console.log('Projector SKUs:', JSON.stringify(compat, null, 2));

  const projectors = db.db.exec('SELECT id, asset_code, sku_id, bulb_sku_ids FROM projectors LIMIT 5');
  console.log('Projectors (before drop):', JSON.stringify(projectors, null, 2));

  process.exit(0);
}

main();