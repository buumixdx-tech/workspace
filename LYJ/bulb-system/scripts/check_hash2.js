
const {initDB, getDB} = require("./src/server/db/init");
const bcrypt = require("bcryptjs");
initDB().then(() => {
  const db = getDB();
  const user = db.db.exec("SELECT password_hash FROM users WHERE username = 'sp001'");
  console.log("Hash in DB:", user[0].values[0][0]);
  console.log("sup123 valid:", bcrypt.compareSync("sup123", user[0].values[0][0]));
  process.exit(0);
});
