
const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  const r = db.db.exec("SELECT id, created_at, replaced_at FROM replacements LIMIT 3");
  console.log("Format comparison:");
  r[0].values.forEach(v => console.log('id:', v[0], 'created:', v[1], '(' + v[1].length + ')', 'replaced:', v[2], '(' + v[2].length + ')'));
  process.exit(0);
});
