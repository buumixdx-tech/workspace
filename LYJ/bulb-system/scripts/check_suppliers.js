
const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  const users = db.db.exec("SELECT id, username, role FROM users WHERE role = 'supplier'");
  console.log("Suppliers:");
  users[0].values.forEach(v => console.log(v));
  process.exit(0);
});
