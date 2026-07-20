
const http = require('http');

const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjQsImlhdCI6MTc3ODMyMTA5NSwiZXhwIjoxNzc4OTI1ODk1fQ.rBPm9wy3swhDKGOqpfkBWgMHlqG8kYtOZMpGfMtshoY';

function get(path, callback) {
  const options = {
    hostname: 'localhost', port: 3001, path: path,
    headers: { 'Authorization': 'Bearer ' + token }
  };
  http.get(options, res => {
    let body = ''; res.on('data', c => body += c);
    res.on('end', () => callback(JSON.parse(body)));
  }).on('error', e => console.error(e));
}

get('/api/offices', r => console.log('Offices:', r.data?.length));
get('/api/skus?type=bulb', r => console.log('Bulb skus:', r.data?.length));
get('/api/users?role=facility', r => console.log('Facilities:', r.data?.length));
