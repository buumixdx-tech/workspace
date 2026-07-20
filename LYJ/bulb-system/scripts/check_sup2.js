
const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  const users = db.db.exec("SELECT id, username, role, supplier_id FROM users WHERE role = 'supplier'");
  console.log("Columns:", users[0].columns);
  users[0].values.forEach(v => console.log(v));
  process.exit(0);
});
