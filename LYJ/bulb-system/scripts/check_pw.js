
const {initDB, getDB} = require("./src/server/db/init");
const bcrypt = require("bcryptjs");
initDB().then(() => {
  const db = getDB();
  const user = db.db.exec("SELECT password_hash FROM users WHERE username = 'sp001'");
  const hash = user[0].values[0][0];
  console.log("Hash:", hash);
  console.log("sup123:", bcrypt.compareSync("sup123", hash));
  console.log("supplier123:", bcrypt.compareSync("supplier123", hash));
  console.log("sp001:", bcrypt.compareSync("sp001", hash));
  process.exit(0);
});
