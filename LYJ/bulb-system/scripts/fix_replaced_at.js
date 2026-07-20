
const {initDB, getDB, saveDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();

  // Fix replacements.replaced_at (ISO format UTC -> CST)
  db.db.run("UPDATE replacements SET replaced_at = datetime(replaced_at, '+8 hours') WHERE replaced_at IS NOT NULL");
  saveDB();

  const repl = db.db.exec("SELECT id, replaced_at, created_at FROM replacements");
  console.log("Replacements:");
  repl[0].values.forEach(v => console.log(v));

  process.exit(0);
});
