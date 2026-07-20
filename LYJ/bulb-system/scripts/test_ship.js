
const http = require('http');
const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjIsImlhdCI6MTc3ODMyMTYxNSwiZXhwIjoxNzc4OTI2NDE1fQ.PljnOP5LqKXaQb2WOsMq0cF8F2h8d_9mGZV5rB1zK8Q';

function get(path, cb) {
  http.get({hostname:'localhost',port:3001,path,headers:{Authorization:'Bearer '+token}}, res => {
    let body=''; res.on('data',c=>body+=c); res.on('end',()=>cb(JSON.parse(body)));
  }).on('error',e=>console.error(e));
}

get('/api/shipments?office_id=3&status=delivered&page=1&page_size=10', r => {
  console.log('Total:', r.total, 'Page:', r.page, 'Data count:', r.data?.length);
  if (r.data?.length > 0) console.log('First item:', r.data[0].id, r.data[0].created_at);
});
