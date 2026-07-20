# 闪饮 ERP 云端部署文档

## 服务器信息

| 项目 | 值 |
|------|-----|
| IP地址 | 111.228.51.56 |
| SSH端口 | 22 |
| 用户名 | root |
| 密码 | `pUUkenQ^` |

---

## 应用架构

```
Internet (80端口)
    │
    ▼
┌───────────────┐
│   Nginx       │  ← 反向代理 + 静态资源服务
│  (端口 80)    │
└───────┬───────┘
        │               /shanyinerp/* → 前端静态资源
        │               /shanyinerp/api/* → 转发到后端
        ▼
┌───────────────┐
│  FastAPI      │  ← 后端API服务
│ (127.0.0.1:8001) │
└───────────────┘
```

## 访问地址

| 应用 | 地址 |
|------|------|
| 前端页面 | http://111.228.51.56/shanyinerp/ |
| 登录账号 | admin / admin123 |

---

## Nginx 配置

### 配置文件位置
- 主配置：`/etc/nginx/sites-available/shanyinerp`
- 启用链接：`/etc/nginx/sites-enabled/0-shanyinerp`（优先于 bulb-system）
- 静态资源：`/var/www/shanyinerp/`

### 路径重写规则
- 前端：`/shanyinerp/*` → `/var/www/shanyinerp/*`
- API代理：`/shanyinerp/api/*` → `http://127.0.0.1:8001/api/*`

### 注意事项
Nginx `sites-enabled` 目录中配置按文件名字母顺序加载。`0-shanyinerp` 优先于 `bulb-system.conf`，确保闪饮ERP的路由优先匹配。

---

## 部署命令

### 前端构建与部署

```bash
# 1. 本地构建
cd D:/workspace/shanyin/erp/CS/Client
npm run build

# 2. 上传到云端
python3 << 'PYEOF'
import paramiko
import tarfile
import io

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('111.228.51.56', username='root', password='pUUkenQ^', timeout=30)

dist_path = 'D:/workspace/shanyin/erp/CS/Client/dist'
tar_buffer = io.BytesIO()
with tarfile.open(fileobj=tar_buffer, mode='w|gz') as tar:
    tar.add(dist_path, arcname='.')
tar_buffer.seek(0)

sftp = client.open_sftp()
sftp.putfo(tar_buffer, '/tmp/shanyinerp.tar.gz')
sftp.close()

stdin, stdout, stderr = client.exec_command(
    'cd /var/www/shanyinerp && rm -rf assets index.html && '
    'tar -xzf /tmp/shanyinerp.tar.gz && rm /tmp/shanyinerp.tar.gz'
)
print(stdout.read().decode('utf-8', errors='replace'))
client.close()
print("Done!")
PYEOF
```

### Nginx 管理

```bash
# 测试配置
nginx -t

# 重启 Nginx
systemctl restart nginx

# 查看 Nginx 状态
systemctl status nginx

# 查看 Nginx 错误日志
tail -50 /var/log/nginx/error.log
```

### 后端管理

```bash
# 查看 uvicorn 进程
ps aux | grep uvicorn | grep -v grep

# 查看后端日志
tail -50 /tmp/server.log

# 重启后端（需要手动执行）
cd /opt/shanyin-erp && bash -c "CORS_ORIGINS= DISABLE_CORS=1 exec python3 -m uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8001" > /tmp/server.log 2>&1 &
```

---

## 测试接口

```bash
# 测试登录
curl -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  "http://111.228.51.56/shanyinerp/api/v1/auth/login"

# 测试虚拟合同列表（需先获取token）
TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  "http://111.228.51.56/shanyinerp/api/v1/auth/login" | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

curl -H "Authorization: Bearer $TOKEN" \
  "http://111.228.51.56/shanyinerp/api/v1/vc/list?size=5"
```

---

## 多应用共存

当前服务器同时运行多个应用，通过URL路径前缀区分：

| 应用 | 路径 | 静态资源目录 |
|------|------|-------------|
| 闪饮ERP | `/shanyinerp/*` | `/var/www/shanyinerp/` |
| 其他应用 | `/asset/*` | `/var/www/bulb-system/src/dist/` |

---

## 故障排查

### 1. 前端 404
检查 Nginx 是否加载了 shanyinerp 配置：
```bash
ls -la /etc/nginx/sites-enabled/
```
确认 `0-shanyinerp` 存在。

### 2. API 404
检查 Nginx 是否正常运行：
```bash
systemctl status nginx
ps aux | grep nginx | grep -v grep
```

### 3. 登录跳转错误
如果 URL 变成 `/shanyinerp/shanyinerp/login`，说明 BrowserRouter basename 配置重复，检查 `App.tsx` 中的 `BrowserRouter basename="/shanyinerp"` 和 `client.ts` 中的 `BASE_URL` 使用是否冲突。

### 4. 后端无响应
检查 uvicorn 是否在运行：
```bash
ps aux | grep uvicorn | grep -v grep
netstat -tlnp | grep 8001
```

---

## 文件结构

```
云端 /var/www/
├── shanyinerp/          # 闪饮ERP前端构建产物
│   ├── index.html
│   └── assets/
└── bulb-system/         # 其他应用

云端 /opt/
└── shanyin-erp/         # 后端代码目录

云端 /etc/nginx/
├── sites-available/
│   ├── shanyinerp       # 闪饮ERP Nginx配置
│   └── bulb-system       # 其他应用配置
└── sites-enabled/
    ├── 0-shanyinerp     # 闪饮ERP（优先加载）
    └── bulb-system.conf  # 其他应用
```
