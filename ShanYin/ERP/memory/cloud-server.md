---
name: cloud-server-deployment
description: 云主机连接和部署信息
type: reference
---

# 云主机信息

| 项目 | 值 |
|------|-----|
| IP | 111.228.6.9 |
| 用户 | root |
| 密码 | koqOUgV\| |

**服务器：** lavm-bk9quy10t9, Ubuntu 24.04.2 LTS, 2C2G

## 部署路径
- Server 路径: `/opt/cs-server/`
- 服务名: `cs-server.service`
- 当前端口: **8001** (旧服务 8000 已废弃)
- nginx 代理: 80 → 8001

## 常用操作
```bash
# 重启服务
systemctl restart cs-server

# 查看日志
journalctl -u cs-server -n 50 --no-pager

# 查看端口
ss -tlnp | grep python
```

## 部署流程（本地 → 云端）
1. 本地 Server 在 `D:/WorkSpace/ShanYin/ERP/CS/Server/`
2. 用 Python + paramiko SFTP 上传（排除 `__pycache__`、`data`、`*.db`、`start.bat`）
3. 重启服务: `systemctl restart cs-server`
4. 旧进程占 8000 端口需手动 `kill -9 <pid>`
5. nginx 配置在 `/etc/nginx/sites-available/cs-server`，改 8000 → 8001 后 `nginx -t && systemctl restart nginx`

## 安全组注意
外网 HTTP 访问需在云控制台开放 80 端口入站规则。
