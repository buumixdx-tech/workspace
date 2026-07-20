
const http = require('http');
const token = 'TOKEN:eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjIsImlhdCI6MTc3ODMyMzEwNywiZXhwIjoxNzc4OTI3OTA3fQ.aPhwiwOEP3DhYic3wsS3xfek6e8DxU0j29_RJ_RSgAk';
function get(path, cb) {
  http.get({hostname:'localhost',port:3001,path,headers:{Authorization:'Bearer '+token}}, res => {
    let body=''; res.on('data',c=>body+=c); res.on('end',()=>cb(JSON.parse(body)));
  }).on('error',e=>console.error(e));
}
get('/api/shipments?office_id=3&page=1&page_size=10', r => {
  console.log(JSON.stringify(r));
});
