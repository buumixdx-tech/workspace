
const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();

  // Check all tables with datetime fields
  const tables = [
    {name: 'shipments', cols: ['created_at', 'updated_at', 'storage_at']},
    {name: 'replacements', cols: ['replaced_at', 'created_at']},
    {name: 'inventory', cols: ['updated_at']},
    {name: 'users', cols: ['created_at']},
    {name: 'offices', cols: ['created_at']},
    {name: 'meeting_rooms', cols: ['created_at']},
    {name: 'skus', cols: ['created_at']},
    {name: 'suppliers', cols: ['created_at']},
  ];

  tables.forEach(t => {
    const colList = t.cols.join(', ');
    const rows = db.db.exec("SELECT id, " + colList + " FROM " + t.name + " LIMIT 3");
    if (rows.length > 0 && rows[0].values.length > 0) {
      console.log(t.name + ": " + JSON.stringify(rows[0].values));
    }
  });

  process.exit(0);
});
