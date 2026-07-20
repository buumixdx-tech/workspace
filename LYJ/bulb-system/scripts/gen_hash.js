
const bcrypt = require("bcryptjs");
const hash = bcrypt.hashSync("sup123", 10);
console.log("HASH:", hash);
