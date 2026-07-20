const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  console.log('replacements count:');
  const r = db.db.exec("SELECT COUNT(*) FROM replacements");
  console.log(r[0].values);

  console.log('All replacements:');
  const r2 = db.db.exec("SELECT id, projector_id, sku_id, replaced_at FROM replacements ORDER BY id");
  console.log('columns:', r2[0].columns);
  r2[0].values.forEach(v => console.log(v));

  console.log('Skus:');
  const r3 = db.db.exec("SELECT id, name, type FROM skus ORDER BY id");
  r3[0].values.forEach(v => console.log(v));

  process.exit(0);
});
