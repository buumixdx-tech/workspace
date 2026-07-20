const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  const r = db.db.exec("SELECT id, projector_id, sku_id, replaced_at, operator_id FROM replacements");
  console.log(r[0].columns);
  r[0].values.forEach(v => console.log(v));
  process.exit(0);
});