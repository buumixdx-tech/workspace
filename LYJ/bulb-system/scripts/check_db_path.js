const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  console.log('DB path:', db.dbBackend ? db.dbBackend.filename : 'unknown');
  const r = db.db.exec("SELECT id, projector_id, sku_id, replaced_at, operator_id FROM replacements ORDER BY id");
  console.log('Count:', r[0].values.length);
  r[0].values.forEach(v => console.log(v));
  process.exit(0);
});