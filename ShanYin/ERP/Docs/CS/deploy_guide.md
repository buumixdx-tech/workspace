# 闪饮 ERP Server 部署指南

## 1. 本地启动

```bash
cd D:\WorkSpace\ShanYin\ERP\CS\Server

# 安装依赖（首次）
pip install -r requirements.txt

# 启动服务
python -m uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000
```

访问：`http://127.0.0.1:8000/docs`

---

## 2. 云主机启动

### 2.1 SSH 连接

```bash
ssh root@111.228.6.9
```

### 2.2 进入目录

```bash
cd /opt/cs-server
```

### 2.3 停止旧进程

```bash
fuser -k 8000/tcp
```

### 2.4 启动服务

```bash
nohup python3 -m uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8000 > /var/log/cs-server.log 2>&1 &
```

### 2.5 确认运行

```bash
# 检查进程
ps aux | grep uvicorn | grep -v grep

# 检查端口
netstat -tlnp | grep 8000
```

### 2.6 查看日志

```bash
tail -f /var/log/cs-server.log
```

---

## 3. 服务管理命令

| 操作 | 命令 |
|------|------|
| 停止服务 | `fuser -k 8000/tcp` |
| 重启服务 | 先停止，再启动 |
| 查看日志 | `tail -f /var/log/cs-server.log` |
| 查看端口占用 | `netstat -tlnp \| grep 8000` |
| 查看进程 | `ps aux \| grep uvicorn \| grep -v grep` |

---

## 4. Nginx 反向代理（云主机）

nginx 已配置在 80 端口，代理到 8000：

| 外部地址 | 代理到 |
|---------|--------|
| `http://111.228.6.9/docs` | Swagger UI 文档 |
| `http://111.228.6.9/openapi.json` | OpenAPI JSON |
| `http://111.228.6.9/api/*` | 业务 API |

nginx 已在开机时自动启动，无需手动管理。

---

## 5. 代码更新流程

### 5.1 本地修改

在 `D:\WorkSpace\ShanYin\ERP\CS\Server\` 下修改代码。

### 5.2 上传到云主机

```bash
# 上传单个文件
scp -o StrictHostKeyChecking=no D:\WorkSpace\ShanYin\ERP\CS\Server\api\app.py root@111.228.6.9:/opt/cs-server/api/app.py

# 上传整个目录
scp -r -o StrictHostKeyChecking=no D:\WorkSpace\ShanYin\ERP\CS\Server\ root@111.228.6.9:/opt/cs-server/
```

### 5.3 重启服务

```bash
ssh root@111.228.6.9 'fuser -k 8000/tcp; sleep 1; cd /opt/cs-server && nohup python3 -m uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8000 > /var/log/cs-server.log 2>&1 &'
```

---

## 6. 数据库

- 位置：`/opt/cs-server/data/business_system.db`
- 类型：SQLite
- 自动创建：首次启动时自动初始化表结构

---

## 7. 日志

- 服务日志：`/var/log/cs-server.log`
- nginx 日志：`/var/log/nginx/access.log`、`/var/log/nginx/error.log`

---

## 8. 防火墙配置

如遇端口无法访问，在云主机执行：

```bash
# 清除京东云防火墙规则
iptables -F JDCLOUDHIDS_IN_LIVE
iptables -P INPUT ACCEPT
```
