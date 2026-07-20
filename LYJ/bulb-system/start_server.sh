#!/bin/bash
cd /var/www/bulb-system
pkill -f "node src/server" 2>/dev/null
sleep 1
nohup env NODE_ENV=production node src/server/index.js > /var/log/bulb-server.log 2>&1 &
sleep 3
curl -s http://localhost:3001/api/health
