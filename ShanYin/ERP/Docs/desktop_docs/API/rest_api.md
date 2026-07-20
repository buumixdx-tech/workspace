# 闪饮 ERP REST API 手册

> [!IMPORTANT]
> 本文档覆盖 FastAPI 路由层的所有 HTTP API 端点，按 Pattern 分类。
>
> **Base URL:** `http://localhost:8000/api/v1`

---

## Pattern 分类

| Pattern | 说明 | 端点示例 |
|---------|------|---------|
| **List** | 分页列表查询 | `GET /business`, `GET /master/customers` |
| **Batch** | 批量更新 | `POST /master/update-customers` |
| **Bulk** | 批量操作 | `POST /logistics/bulk-progress` |
| **Search** | 模糊搜索 | `GET /finance/cash-flows/search` |
| **Aggregate** | 统计聚合 | `GET /business/stats` |
| **Suggested** | 自动补全 | `GET /master/customers/suggest` |
| **SSE** | 实时推送 | `GET /events/stream` |

---

## 1. 业务 (Business)

### 查询端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/business` | 业务列表 |
| GET | `/business/stats` | 业务统计 |
| GET | `/business/{bid}` | 业务详情 |

**列表参数：**
- `ids`: 多值查询，如 `"1,2,3"`
- `customer_id`: 按客户精确过滤
- `customer_ids`: 多客户查询，如 `"1,2,3"`
- `status`: 按状态过滤
- `date_from`, `date_to`: 创建时间范围，格式 `YYYY-MM-DD`
- `search`: 按客户名称模糊搜索
- `page`, `size`: 分页，默认 `size=50`

**统计返回：**
```json
{
  "success": true,
  "data": {
    "total": 16,
    "by_status": {"业务开展": 4, "业务终止": 10},
    "by_customer": {"客户A": 1, "客户B": 2}
  }
}
```

### 写操作端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/business/create` | 创建业务 |
| POST | `/business/update-status` | 更新业务状态 |
| POST | `/business/delete` | 删除业务 |
| POST | `/business/advance-stage` | 推进业务阶段 |

---

## 2. 主数据 (Master Data)

### 客户 (Customers)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/master/customers` | 客户列表 |
| GET | `/master/customers/suggest` | 客户名称自动补全 |
| GET | `/master/customers/{cid}` | 客户详情 |
| POST | `/master/create-customer` | 创建客户 |
| POST | `/master/update-customers` | 批量更新客户 |
| POST | `/master/delete-customers` | 批量删除客户 |

### 点位 (Points)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/master/points` | 点位列表 |
| GET | `/master/points/suggest` | 点位名称自动补全 |
| GET | `/master/points/{pid}` | 点位详情 |
| POST | `/master/create-point` | 创建点位 |
| POST | `/master/update-points` | 批量更新点位 |
| POST | `/master/delete-points` | 批量删除点位 |

### 供应商 (Suppliers)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/master/suppliers` | 供应商列表 |
| GET | `/master/suppliers/suggest` | 供应商名称自动补全 |
| GET | `/master/suppliers/{sid}` | 供应商详情 |
| POST | `/master/create-supplier` | 创建供应商 |
| POST | `/master/update-suppliers` | 批量更新供应商 |
| POST | `/master/delete-suppliers` | 批量删除供应商 |

### SKU

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/master/skus` | SKU列表 |
| GET | `/master/skus/suggest` | SKU名称自动补全 |
| GET | `/master/skus/{sku_id}` | SKU详情 |
| POST | `/master/create-sku` | 创建SKU |
| POST | `/master/update-skus` | 批量更新SKU |
| POST | `/master/delete-skus` | 批量删除SKU |

### 合作方 (Partners)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/master/partners` | 合作方列表 |
| GET | `/master/partners/suggest` | 合作方名称自动补全 |
| POST | `/master/create-partner` | 创建合作方 |
| POST | `/master/update-partners` | 批量更新合作方 |
| POST | `/master/delete-partners` | 批量删除合作方 |

### 合作方关系 (Partner Relations)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/master/partner-relations` | 合作方关系列表 |
| POST | `/master/create-partner-relation` | 创建合作方关系 |
| POST | `/master/delete-partner-relations` | 批量删除合作方关系 |

### 银行账户 (Bank Accounts)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/master/bank-accounts` | 银行账户列表 |
| GET | `/master/bank-accounts/{account_id}` | 银行账户详情 |
| POST | `/master/create-bank-account` | 创建银行账户 |
| POST | `/master/update-bank-accounts` | 批量更新银行账户 |

---

## 3. 虚拟合同 (Virtual Contract)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/vc` | VC列表 |
| GET | `/vc/stats` | VC统计 |
| GET | `/vc/{vc_id}` | VC详情 |

**列表参数：**
- `ids`: 多值查询
- `type`: VC类型（设备采购/物料供应/物料采购/设备采购(库存)/库存拨付/退货）
- `status`: VC状态
- `business_id`: 按业务过滤
- `date_from`, `date_to`: 创建时间范围

---

## 4. 供应链 (Supply Chain)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/supply-chain` | 供应链列表 |
| GET | `/supply-chain/stats` | 供应链统计 |
| GET | `/supply-chain/suggest` | 供应链自动补全 |
| GET | `/supply-chain/items` | 供应链SKU明细 |
| GET | `/supply-chain/{sc_id}` | 供应链详情 |
| POST | `/supply-chain/create` | 创建供应链 |
| PUT | `/supply-chain/{sc_id}` | 更新供应链 |
| DELETE | `/supply-chain/{sc_id}` | 删除供应链 |

**列表参数：**
- `ids`: 多值查询
- `supplier_id`, `supplier_ids`: 按供应商过滤
- `type`: 类型（设备/物料）
- `date_from`, `date_to`: 创建时间范围
- `search`: 按供应商名称模糊搜索

**统计返回：**
```json
{
  "success": true,
  "data": {
    "total": 10,
    "by_type": {"物料": 6, "设备": 4}
  }
}
```

---

## 5. 物流 (Logistics)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/logistics` | 物流列表 |
| GET | `/logistics/stats` | 物流统计 |
| GET | `/logistics/{log_id}` | 物流详情 |
| POST | `/logistics/create-plan` | 创建物流计划 |
| POST | `/logistics/confirm-inbound` | 确认入库 |
| POST | `/logistics/update-express` | 更新快递信息 |
| POST | `/logistics/update-express-status` | 更新快递状态 |
| POST | `/logistics/bulk-progress` | 批量推进快递状态 |

**列表参数：**
- `ids`: 多值查询
- `vc_id`: 按VC过滤
- `status`: 物流状态
- `date_from`, `date_to`: 创建时间范围
- `tracking_number`: 快递单号模糊搜索

**统计返回：**
```json
{
  "success": true,
  "data": {
    "total": 10,
    "by_status": {"已发货": 8, "已签收": 1, "在途中": 1}
  }
}
```

---

## 6. 财务 (Finance)

### 资金流 (CashFlow)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/finance/cashflows` | 资金流列表 |
| GET | `/finance/cash-flows` | 资金流列表(kebab-case) |
| GET | `/finance/cash-flows/search` | 资金流模糊搜索 |
| GET | `/finance/cashflows/{cf_id}` | 资金流详情 |
| GET | `/finance/stats` | 资金流统计 |
| POST | `/finance/create-cashflow` | 录入资金流水 |
| POST | `/finance/internal-transfer` | 内部转账 |
| POST | `/finance/external-fund` | 外部资金出入 |

**列表参数：**
- `ids`: 多值查询
- `vc_id`, `vc_ids`: 按VC过滤
- `type`: 资金流类型（预付/履约/押金/退还押金/退款）
- `payer_id`, `payee_id`: 按账户过滤
- `date_from`, `date_to`: 交易时间范围
- `amount_min`, `amount_max`: 金额范围

**Search 参数：**
- `q`: 搜索关键字（匹配 description 字段）
- `type`, `date_from`, `date_to`: 可选过滤条件

**统计返回：**
```json
{
  "success": true,
  "data": {
    "total_count": 100,
    "total_amount": 500000.0,
    "by_type": {
      "预付": {"count": 50, "total": 200000.0},
      "履约": {"count": 50, "total": 300000.0}
    }
  }
}
```

### 会计科目 (Accounts)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/finance/accounts` | 会计科目列表 |

**参数：**
- `ids`: 多值查询
- `category`: 科目类别（资产/负债/权益/损益）
- `counterpart_type`: 对手方类型（客户/供应商/合作伙伴/内部）

### 建议端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/finance/suggest/cashflow-parties` | 建议的收付款方 |

**参数：**
- `vc_id`: VC ID
- `cf_type`: 资金流类型

---

## 7. 库存 (Inventory)

### 设备库存 (Equipment)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/inventory/equipment` | 设备库存列表 |
| GET | `/inventory/equipment/search` | 设备库存模糊搜索 |
| GET | `/inventory/stats` | 库存统计 |

**列表参数：**
- `ids`: 多值查询
- `vc_id`: 按VC过滤
- `point_id`: 按点位过滤
- `operational_status`: 运营状态（库存/运营/处置）

**Search 参数：**
- `q`: 搜索关键字（匹配 SN 序列号）
- `operational_status`: 可选，按运营状态过滤

### 物料库存 (Material)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/inventory/material` | 物料库存列表 |

**列表参数：**
- `ids`: 多值查询
- `sku_id`: 按SKU过滤
- `warehouse_point_id`: 按仓库点位过滤（基于 stock_distribution JSON）

**统计返回：**
```json
{
  "success": true,
  "data": {
    "equipment": {
      "total": 100,
      "by_status": {"库存": 30, "运营": 65, "处置": 5}
    },
    "material": {
      "total_value": 500000.0,
      "total_quantity": 10000.0,
      "by_sku": [
        {"sku_id": 1, "name": "物料A", "qty": 5000.0, "value": 250000.0}
      ]
    }
  }
}
```

---

## 8. 事件 (Events)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/events` | 事件列表 |
| GET | `/events/stream` | 事件实时推送(SSE) |

---

## 9. 时间规则 (Rules)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/rules` | 时间规则列表 |
| POST | `/rules` | 创建时间规则 |
| PUT | `/rules/{rule_id}` | 更新时间规则 |
| DELETE | `/rules/{rule_id}` | 删除时间规则 |

---

## 10. 附加业务 (Addon Business)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/addon-business` | 附加业务列表 |
| GET | `/addon-business/active` | 生效中的附加业务 |
| GET | `/addon-business/{addon_id}` | 附加业务详情 |
| POST | `/addon-business/create` | 创建附加业务 |
| POST | `/addon-business/update` | 更新附加业务 |
| POST | `/addon-business/deactivate` | 失效附加业务 |

---

## 11. 业务查询 (Query)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/query/returnable-items` | 可退货项目 |
| GET | `/query/sku-agreement-price` | SKU协议价格 |
| POST | `/query/inventory-availability` | 库存可用性校验 |
| GET | `/query/cashflow-progress` | 资金流进度 |
| GET | `/query/counterpart-info` | 交易对手信息 |

---

## 12. 系统 (System)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/system/status` | 系统状态看板 |
| GET | `/system/tools` | AI Agent 工具清单 |

---

## 13. SQL 查询

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/sql/query` | 执行只读SQL查询 |

---

## 通用响应格式

**成功：**
```json
{
  "success": true,
  "data": { ... }
}
```

**错误：**
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述"
  }
}
```

---

## 分页响应格式

List 和 Search 端点返回分页结果：

```json
{
  "success": true,
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "size": 50
  }
}
```

---

## 参数命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 主键多值 | `ids` | `ids=1,2,3` |
| 外键多值 | `{entity}_ids` | `vc_ids=1,2,3` |
| 日期范围 | `date_from`, `date_to` | `date_from=2026-04-01` |
| 金额范围 | `amount_min`, `amount_max` | `amount_min=1000` |
| 搜索(List) | `search` | `search=张三` |
| 搜索(Suggest) | `q` | `q=张` |
| 分页 | `page`, `size` | `page=1, size=50` |
