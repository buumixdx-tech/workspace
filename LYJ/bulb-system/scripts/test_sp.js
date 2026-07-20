
const http = require('http');
const data = JSON.stringify({username: 'sp001', password: 'sup123'});
const options = {
  hostname: 'localhost', port: 3001, path: '/api/auth/login',
  method: 'POST', headers: {'Content-Type': 'application/json', 'Content-Length': data.length}
};
const req = http.request(options, res => {
  let body = ''; res.on('data', c => body += c);
  res.on('end', () => console.log('Status:', res.statusCode, 'Body:', body));
});
req.on('error', e => console.error(e));
req.write(data); req.end();
