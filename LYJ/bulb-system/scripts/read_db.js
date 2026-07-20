
const sqlite3 = require('sqlite3').verbose();
const db = new sqlite3.Database('/var/www/bulb-system/data/bulb.db');
db.all("SELECT id, projector_id, sku_id, replaced_at, operator_id FROM replacements ORDER BY id", [], (err, rows) => {
  if (err) console.error(err);
  else {
    console.log("Count:", rows.length);
    rows.forEach(r => console.log(r));
  }
  db.close();
});
