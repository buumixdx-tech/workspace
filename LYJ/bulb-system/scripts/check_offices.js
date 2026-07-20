
const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  const r = db.db.exec("PRAGMA table_info(offices)");
  console.log("Offices columns:");
  r[0].values.forEach(v => console.log(v));
  process.exit(0);
});
