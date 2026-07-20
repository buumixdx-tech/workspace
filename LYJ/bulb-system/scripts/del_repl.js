const {initDB, getDB, saveDB} = require("./src/server/db/init");
initDB().then(() => {
  const db = getDB();
  db.db.run('DELETE FROM replacements WHERE id = 1');
  saveDB();
  console.log('Deleted id=1');
  process.exit(0);
});