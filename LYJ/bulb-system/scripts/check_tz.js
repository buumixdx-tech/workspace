
const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  const now = db.db.exec("SELECT datetime('now'), CURRENT_TIMESTAMP");
  console.log("now():", now[0].values[0]);
  process.exit(0);
});
