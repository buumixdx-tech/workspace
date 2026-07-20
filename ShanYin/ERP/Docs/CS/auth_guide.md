# 闪饮 ERP API 认证指南

## 1. 认证流程

**登录获取 Token：**
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

## 2. Token 使用

客户端请求时在 Header 携带：
```
Authorization: Bearer <access_token>
```

## 3. Token 有效期

| Token 类型 | 有效期 |
|-----------|--------|
| Access Token | 1 小时 |
| Refresh Token | 7 天 |

## 4. Token 刷新

Access Token 过期后，用 Refresh Token 换新 Token：
```
POST /api/v1/auth/refresh
Content-Type: application/json

{"refresh_token": "mn2tmLNq..."}
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

## 5. 登出

```
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
```

## 6. 端点分类

| 端点 | 认证要求 |
|------|---------|
| `GET /docs` | 公开 |
| `POST /api/v1/auth/login` | 公开 |
| `POST /api/v1/auth/refresh` | 公开 |
| `POST /api/v1/auth/register` | 公开 |
| 其他所有 `/api/v1/*` | 需 Bearer Token |

## 7. 错误响应

| 状态码 | 说明 |
|-------|------|
| 401 | 未提供 Token / Token 无效或过期 |
| 403 | 无权限（需 admin 角色） |

**401 响应示例：**
```json
{"success": false, "data": null, "error": {"code": "HTTP_401", "message": "未授权访问"}}
```

## 8. 用户管理（仅管理员）

### 获取用户列表
```
GET /api/v1/auth/users
Authorization: Bearer <admin_token>
```

### 创建用户
```
POST /api/v1/auth/register
Authorization: Bearer <admin_token>
Content-Type: application/json

{"username": "user1", "password": "password123", "role": "user"}
```

### 修改密码
```
PUT /api/v1/auth/password
Authorization: Bearer <access_token>
Content-Type: application/json

{"old_password": "oldpass", "new_password": "newpass"}
```

### 获取当前用户
```
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

## 9. 完整调用示例

### Python 示例
```python
import requests

BASE_URL = "http://111.228.6.9"

# 1. 登录
resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
    "username": "admin",
    "password": "admin123"
})
token = resp.json()["data"]["access_token"]

# 2. 带 Token 请求
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get(f"{BASE_URL}/api/v1/vc/list", headers=headers)
print(resp.json())

# 3. Token 过期后刷新
resp = requests.post(f"{BASE_URL}/api/v1/auth/refresh", json={
    "refresh_token": refresh_token
})
```

### JavaScript 示例
```javascript
const BASE_URL = "http://111.228.6.9";

// 1. 登录
const loginResp = await fetch(`${BASE_URL}/api/v1/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username: "admin", password: "admin123" })
});
const { data } = await loginResp.json();
const token = data.access_token;

// 2. 带 Token 请求
const vcResp = await fetch(`${BASE_URL}/api/v1/vc/list`, {
  headers: { "Authorization": `Bearer ${token}` }
});
const vcData = await vcResp.json();
console.log(vcData);
```
