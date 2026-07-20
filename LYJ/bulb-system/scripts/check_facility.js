
const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  const users = db.db.exec("SELECT id, username, real_name, office_id, role FROM users WHERE role = 'facility'");
  console.log("Facility users:");
  users[0].values.forEach(v => console.log(v));
  process.exit(0);
});
