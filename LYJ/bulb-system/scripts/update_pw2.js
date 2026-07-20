
const {initDB, getDB, saveDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  db.db.run("UPDATE users SET password_hash = ? WHERE username = ?", ["$2a$10$D2fapbHjlGun73z3loNlyOOOsfHxJC1ARj1S7AIMhq07n/n0H9ls.", "sp001"]);
  saveDB();
  console.log("Updated. Verifying:");
  const user = db.db.exec("SELECT password_hash FROM users WHERE username = 'sp001'");
  console.log(user[0].values[0][0]);
  process.exit(0);
});
