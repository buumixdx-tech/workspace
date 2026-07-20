
const {initDB, getDB} = require("./src/server/db/init");
const bcrypt = require("bcryptjs");
initDB().then(() => {
  const db = getDB();
  const stmt = db.prepare("SELECT * FROM users WHERE username = ?");
  const user = stmt.get("sp001");
  console.log("User:", user);
  console.log("Password valid:", bcrypt.compareSync("sup123", user.password_hash));
  process.exit(0);
});
