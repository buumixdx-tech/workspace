
const http = require('http');
const data = JSON.stringify({username:'hf001', password:'hf123'});
const req = http.request({hostname:'localhost',port:3001,path:'/api/auth/login',method:'POST',headers:{'Content-Type':'application/json','Content-Length':data.length}}, res => {
  let body=''; res.on('data',c=>body+=c); res.on('end',()=>{
    const r = JSON.parse(body);
    const token = r.token;
    console.log('TOKEN:' + token);
    
    // Test shipments
    http.get({hostname:'localhost',port:3001,path:'/api/shipments?office_id=3&page=1&page_size=10',headers:{Authorization:'Bearer '+token}}, resp => {
      let b=''; resp.on('data',c=>b+=c); resp.on('end',()=>{
        console.log('SHIPMENTS:' + b);
      });
    });
  });
});
req.write(data); req.end();
