
const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  const shipments = db.db.exec("SELECT id, office_id, status, created_at, updated_at FROM shipments ORDER BY id DESC LIMIT 5");
  console.log("Columns:", shipments[0].columns);
  shipments[0].values.forEach(v => console.log(v));
  process.exit(0);
});
