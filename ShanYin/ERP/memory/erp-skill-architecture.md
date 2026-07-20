---
name: erp-skill-architecture
description: ERP skill 中央代理架构设计
type: project
---

# ERP Skill 架构设计

## 推荐方案：中央 API 代理 skill

```
skills/
├── erp-api/              # 中央 API 代理
│   ├── api_client.py     # 封装所有 API 调用（URL、认证、错误处理）
│   └── manifest.yml
├── erp-business/         # 业务域 skill，调用 erp-api
├── erp-vc/               # VC skill，调用 erp-api
├── erp-finance/          # 财务 skill，调用 erp-api
└── ...
```

## API 地址
- 云端: `http://111.228.6.9` (通过 nginx 80 端口)
- 本地开发: `http://localhost:8001` 或 `http://localhost:8000`

## API 基础 URL
所有 skill 统一从 `erp-api` 获取配置，不硬编码 URL。
