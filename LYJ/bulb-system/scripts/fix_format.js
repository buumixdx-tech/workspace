
const {initDB, getDB, saveDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();

  // Fix replacements.replaced_at - format from ISO to YYYY-MM-DD HH:mm:ss
  // First convert to proper format using substr
  db.db.exec("UPDATE replacements SET replaced_at = substr(replaced_at,1,10)||' '||substr(replaced_at,12,8) WHERE replaced_at LIKE '%T%'");
  saveDB();

  const repl = db.db.exec("SELECT id, replaced_at, created_at FROM replacements");
  console.log("Replacements:");
  repl[0].values.forEach(v => console.log(v));

  process.exit(0);
});
