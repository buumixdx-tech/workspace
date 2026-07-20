const { initDB, getDB, saveDB } = require('./src/server/db/init');

async function main() {
  await initDB();
  const db = getDB();

  // Find projectors with null ids
  const nullProjectors = db.db.exec("SELECT id, asset_code FROM projectors WHERE id IS NULL");
  console.log('Projectors with NULL ids:', JSON.stringify(nullProjectors, null, 2));

  // Get the max id
  const maxIdResult = db.db.exec("SELECT MAX(id) FROM projectors");
  let maxId = maxIdResult[0]?.values[0]?.[0] || 0;
  console.log('Current max id:', maxId);

  // Assign new ids to null projectors
  const nullAssets = nullProjectors[0]?.values || [];
  for (const [oldId, assetCode] of nullAssets) {
    maxId++;
    console.log(`Updating ${assetCode}: NULL -> ${maxId}`);
    db.db.run("UPDATE projectors SET id = ? WHERE asset_code = ? AND id IS NULL", [maxId, assetCode]);
  }

  // Verify
  const remaining = db.db.exec("SELECT id, asset_code FROM projectors WHERE id IS NULL");
  console.log('Remaining null ids:', remaining[0]?.values?.length || 0);

  saveDB();
  console.log('Done!');
  process.exit(0);
}

main();