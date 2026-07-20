# 闪饮 ERP API 客户端开发指南

> 适用于前端客户端、移动端等外部应用接入

---

## 1. 服务地址

| 环境 | 地址 |
|------|------|
| 生产环境 | `http://111.228.6.9` |

---

## 2. 认证流程

### 2.1 登录获取 Token

```
POST /api/v1/auth/login
Content-Type: application/json

{"username": "admin", "password": "admin123"}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGci...",
    "refresh_token": "mn2tmLNq...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

### 2.2 Token 有效期

| Token 类型 | 有效期 |
|-----------|--------|
| Access Token | 1 小时 |
| Refresh Token | 7 天 |

### 2.3 Token 刷新

Access Token 过期后，使用 Refresh Token 获取新 Token：

```
POST /api/v1/auth/refresh
Content-Type: application/json

{"refresh_token": "mn2tmLNq..."}
```

### 2.4 登出（撤销 Refresh Token）

```
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
```

---

## 3. 请求示例

### 3.1 登录

**请求：**
```bash
curl -X POST http://111.228.6.9/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

**响应：**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "mn2tmLNqukqRL-Tb27dSUJcCt1dM5msm...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

### 3.2 带认证的请求

**请求：**
```bash
curl http://111.228.6.9/api/v1/vc/list \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 3.3 获取当前用户信息

```
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

**响应：**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "permissions": {},
    "is_active": true,
    "created_at": "2026-04-29T15:12:01.602624"
  }
}
```

---

## 4. 修改密码

```
PUT /api/v1/auth/me/password
Authorization: Bearer <access_token>
Content-Type: application/json

{"old_password": "admin123", "new_password": "NewPass123!"}
```

---

## 5. API 端点一览

### 5.1 公开端点（无需认证）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/docs` | Swagger UI 文档 |
| GET | `/openapi.json` | OpenAPI JSON 规范 |
| POST | `/api/v1/auth/login` | 用户登录 |
| POST | `/api/v1/auth/refresh` | 刷新 Token |
| POST | `/api/v1/auth/register` | 注册用户（需管理员权限） |

### 5.2 业务端点（需认证）

所有 `/api/v1/*` 下的业务接口均需在 Header 携带：
```
Authorization: Bearer <access_token>
```

| 模块 | 路径前缀 | 说明 |
|------|---------|------|
| 主数据 | `/api/v1/master/*` | 客户、SKU、供应商、点位等 |
| 业务 | `/api/v1/business/*` | 业务单据及流转 |
| 供应链 | `/api/v1/supply_chain/*` | 供应链协议 |
| 虚拟合同 | `/api/v1/vc/*` | 虚拟合同（采购/供应） |
| 物流 | `/api/v1/logistics/*` | 物流计划及入库 |
| 财务 | `/api/v1/finance/*` | 资金流、账户、凭证 |
| 时间规则 | `/api/v1/rules/*` | 时间规则引擎 |
| 查询 | `/api/v1/query/*` | 综合查询 |
| 库存 | `/api/v1/inventory/*` | 设备及物料库存 |
| 事件 | `/api/v1/events/*` | 系统事件 |
| 合作伙伴 | `/api/v1/partner_relations/*` | 合作伙伴关系 |
| 原始查询 | `/api/v1/raw/*` | SQL 原始查询 |

---

## 6. 错误处理

### 6.1 响应格式

**成功：**
```json
{"success": true, "data": {...}, "error": null}
```

**失败：**
```json
{"success": false, "data": null, "error": {"code": "HTTP_401", "message": "未授权访问"}}
```

### 6.2 常见错误码

| HTTP 状态码 | code | 说明 |
|-------------|------|------|
| 401 | HTTP_401 | 未提供 Token / Token 无效或过期 |
| 403 | HTTP_403 | 无权限（需 admin 角色） |
| 404 | NOT_FOUND | 资源不存在 |
| 400 | VALIDATION_ERROR | 请求参数校验失败 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

---

## 7. 代码示例

### 7.1 Python

```python
import requests
import time

BASE_URL = "http://111.228.6.9"

class ShanYinAPI:
    def __init__(self):
        self.access_token = None
        self.refresh_token = None

    def login(self, username: str, password: str):
        resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
            "username": username,
            "password": password
        })
        data = resp.json()
        if data["success"]:
            self.access_token = data["data"]["access_token"]
            self.refresh_token = data["data"]["refresh_token"]
        return data

    def refresh(self):
        if not self.refresh_token:
            raise Exception("No refresh token")
        resp = requests.post(f"{BASE_URL}/api/v1/auth/refresh", json={
            "refresh_token": self.refresh_token
        })
        data = resp.json()
        if data["success"]:
            self.access_token = data["data"]["access_token"]
            self.refresh_token = data["data"]["refresh_token"]
        return data

    def headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    def get(self, path: str, params: dict = None):
        resp = requests.get(f"{BASE_URL}{path}", headers=self.headers(), params=params)
        return resp.json()

    def post(self, path: str, json: dict = None):
        resp = requests.post(f"{BASE_URL}{path}", headers=self.headers(), json=json)
        return resp.json()

    def put(self, path: str, json: dict = None):
        resp = requests.put(f"{BASE_URL}{path}", headers=self.headers(), json=json)
        return resp.json()


# 使用示例
api = ShanYinAPI()
api.login("admin", "admin123")

# 获取 VC 列表
vcs = api.get("/api/v1/vc/list")
print(vcs)

# 获取当前用户
me = api.get("/api/v1/auth/me")
print(me)

# 获取客户列表
customers = api.get("/api/v1/master/customers")
print(customers)
```

### 7.2 JavaScript / TypeScript

```javascript
const BASE_URL = "http://111.228.6.9";

class ShanYinAPI {
  constructor() {
    this.accessToken = null;
    this.refreshToken = null;
  }

  async login(username, password) {
    const resp = await fetch(`${BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const data = await resp.json();
    if (data.success) {
      this.accessToken = data.data.access_token;
      this.refreshToken = data.data.refresh_token;
    }
    return data;
  }

  async refresh() {
    const resp = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: this.refreshToken })
    });
    const data = await resp.json();
    if (data.success) {
      this.accessToken = data.data.access_token;
      this.refreshToken = data.data.refresh_token;
    }
    return data;
  }

  headers() {
    return { "Authorization": `Bearer ${this.accessToken}` };
  }

  async get(path, params) {
    const url = new URL(`${BASE_URL}${path}`);
    if (params) Object.keys(params).forEach(k => url.searchParams.set(k, params[k]));
    const resp = await fetch(url, { headers: this.headers() });
    return resp.json();
  }

  async post(path, body) {
    const resp = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.headers() },
      body: JSON.stringify(body)
    });
    return resp.json();
  }
}

// 使用示例
const api = new ShanYinAPI();
await api.login("admin", "admin123");

const vcs = await api.get("/api/v1/vc/list");
console.log(vcs);

const me = await api.get("/api/v1/auth/me");
console.log(me);
```

### 7.3 Curl 完整示例

```bash
#!/bin/bash
BASE_URL="http://111.228.6.9"

# 1. 登录
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}')

TOKEN=$(echo $LOGIN_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
REFRESH=$(echo $LOGIN_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['refresh_token'])")

echo "Token: ${TOKEN:0:40}..."

# 2. 获取用户信息
curl -s "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $TOKEN"

# 3. 获取 VC 列表
curl -s "$BASE_URL/api/v1/vc/list" \
  -H "Authorization: Bearer $TOKEN"

# 4. 获取客户列表
curl -s "$BASE_URL/api/v1/master/customers" \
  -H "Authorization: Bearer $TOKEN"

# 5. Token 刷新（1小时后）
curl -s -X POST "$BASE_URL/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH\"}"
```

---

## 8. Token 自动刷新封装（推荐）

```python
import requests
import time

class AutoRefreshAPI(ShanYinAPI):
    def request(self, method, path, **kwargs):
        """自动处理 Token 刷新"""
        resp = requests.request(method, f"{BASE_URL}{path}", headers=self.headers(), **kwargs)

        # Token 过期，尝试刷新
        if resp.status_code == 401:
            self.refresh()
            resp = requests.request(method, f"{BASE_URL}{path}", headers=self.headers(), **kwargs)

        return resp.json()
```

---

## 9. 注意事项

1. **密码安全**：生产环境中请修改 admin 默认密码
2. **Token 存储**：Access Token 建议存放在内存或安全存储中，Refresh Token 需持久化存储
3. **HTTPS**：当前部署为 HTTP，生产环境建议配置 HTTPS
4. **CORS**：API 仅允许指定来源，生产环境前端需正确配置
5. **权限控制**：当前 `permissions` 字段已预留，暂未启用细粒度权限控制
