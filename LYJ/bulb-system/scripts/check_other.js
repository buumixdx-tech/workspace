
const {initDB, getDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();

  // Check replacements
  const repl = db.db.exec("SELECT id, replaced_at, created_at FROM replacements LIMIT 3");
  console.log("Replacements:");
  repl[0].values.forEach(v => console.log(v));

  // Check inventory
  const inv = db.db.exec("SELECT id, updated_at FROM inventory LIMIT 3");
  console.log("Inventory:");
  inv[0].values.forEach(v => console.log(v));

  process.exit(0);
});
