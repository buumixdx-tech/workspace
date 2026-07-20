
const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  // Raw query without any formatting
  const r = db.db.exec("SELECT id, office_id, status, created_at, datetime(created_at) as dt FROM shipments ORDER BY id DESC LIMIT 3");
  console.log("Columns:", r[0].columns);
  r[0].values.forEach(v => console.log(JSON.stringify(v)));
  
  // Check what now() returns
  const now = db.db.exec("SELECT datetime('now'), datetime('localtime'), CURRENT_TIMESTAMP");
  console.log("now():", now[0].values[0]);
  process.exit(0);
});
