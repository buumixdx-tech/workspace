
const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  const tables = ['offices', 'meeting_rooms', 'skus', 'projectors', 'suppliers', 'users', 'inventory', 'replacements', 'shipments'];
  tables.forEach(t => {
    const r = db.db.exec("PRAGMA table_info(" + t + ")");
    const cols = r[0].values.map(v => v[1]).join(', ');
    console.log(t + ": " + cols);
  });
  process.exit(0);
});
