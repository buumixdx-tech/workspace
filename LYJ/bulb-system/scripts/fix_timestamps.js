
const {initDB, getDB, saveDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();

  // Fix shipments - add 8 hours
  const shipments = db.db.exec("SELECT id, created_at, updated_at FROM shipments");
  console.log("Shipments before fix:");
  shipments[0].values.forEach(v => console.log(v));

  // Use datetime function to add 8 hours
  db.db.run("UPDATE shipments SET created_at = datetime(created_at, '+8 hours'), updated_at = datetime(updated_at, '+8 hours')");
  saveDB();

  const fixed = db.db.exec("SELECT id, created_at, updated_at FROM shipments");
  console.log("Shipments after fix:");
  fixed[0].values.forEach(v => console.log(v));

  process.exit(0);
});
