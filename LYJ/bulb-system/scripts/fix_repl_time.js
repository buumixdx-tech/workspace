
const {initDB, getDB, saveDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();

  // Fix replacements - the created_at has the issue (stored as UTC)
  // replaced_at is user-provided so leave it alone
  // But created_at is auto-generated and has 8 hour offset
  db.db.run("UPDATE replacements SET created_at = datetime(created_at, '+8 hours') WHERE created_at IS NOT NULL");
  saveDB();

  const repl = db.db.exec("SELECT id, replaced_at, created_at FROM replacements");
  console.log("Replacements after fix:");
  repl[0].values.forEach(v => console.log(v));

  process.exit(0);
});
