
const {initDB, getDB, saveDB} = require("./src/server/db/init");
const bcrypt = require("bcryptjs");
initDB().then(() => {
  const db = getDB();
  const hash = bcrypt.hashSync("sup123", 10);
  db.db.run("UPDATE users SET password_hash = ? WHERE username = 'sp001'", [hash]);
  saveDB();
  console.log("Password reset for sp001 to sup123");
  process.exit(0);
});
