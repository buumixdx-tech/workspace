# 山银 ERP 10-Skill 架构

## 概述

基于山银 ERP 的 API 模块和业务链，将 AI Agent 能力拆分为 10 个 Skill，每个 Skill 负责特定领域的业务逻辑和数据操作。

> **Analytics 定位说明**：自然语言 → 生成 SQL → 执行复杂查询。
> 基本查询（列表、详情、单维度统计）由各模块自己的 API 实现，不走 analytics。
>
> **时间规则 / 事件系统**：暂不纳入 Skill 体系。

| # | Skill | 职责 | 类型 |
|---|-------|------|------|
| 1 | `shanyin-master` | 主数据管理 | 读写 |
| 2 | `shanyin-business` | 业务 + 附加业务（addon） | 读写 |
| 3 | `shanyin-partner-relations` | 合作方关系 | 读写 |
| 4 | `shanyin-supply` | 供应链 | 读写 |
| 5 | `shanyin-vc` | 虚拟合同 | 读写 |
| 6 | `shanyin-logistics` | 物流运营 | 读写 |
| 7 | `shanyin-cashflow` | 资金操作（流水 + 转账） | 读写 |
| 8 | `shanyin-inventory` | 库存查询 | 只读 |
| 9 | `shanyin-finance-analyst` | 财务视角 SQL 分析 | 只读 |
| 10 | `shanyin-analytics` | 自然语言 SQL 复杂查询（通用） | 只读 |

---

## Skill 1: `shanyin-master` — 主数据管理

**触发词**: 客户/点位/供应商/SKU/合作方/银行账户

**端点模板** (6类主数据统一)：
```
POST /master/create-{entity}      # 创建
POST /master/update-{entities}   # 批量更新
POST /master/delete-{entities}   # 批量删除
GET  /master/{entities}          # 列表 (+ ids/search/page/size)
GET  /master/{entities}/suggest   # 自动补全 (+ q/limit)
GET  /master/{entities}/{id}     # 详情
```

| 实体 | 额外筛选 |
|------|---------|
| 客户 | search |
| 点位 | customer_id, supplier_id, type |
| 供应商 | category, search |
| SKU | supplier_id, type_level1, search |
| 合作方 | type, search |
| 银行账户 | owner_type, owner_id, search |

---

## Skill 2: `shanyin-business` — 业务 + addon

**触发词**: 业务开展/推进/终止、业务阶段、附加业务

**API 端点**:

| 操作 | 方法 | 端点 |
|------|------|------|
| 创建业务 | POST | `/business/create` |
| 推进业务阶段 | POST | `/business/advance-stage` |
| 更新业务状态 | POST | `/business/update-status` |
| 删除业务 | POST | `/business/delete` |
| 查询业务列表 | GET | `/business/list` |
| 业务详情 | GET | `/business/{bid}` |
| 按条件查询业务 | GET | `/business/list?customer_id=&status=&date_from=&date_to=` |
| 模糊搜索业务 | GET | `/business/list?search=` |
| 多客户查询 | GET | `/business/list?customer_ids=1,2,3` |
| 创建附加业务 | POST | `/business/addons/create` |
| 更新附加业务 | POST | `/business/addons/update` |
| 失效附加业务 | POST | `/business/addons/deactivate` |
| 查询业务addon列表 | GET | `/business/addons/list/{business_id}` |
| 查询业务生效addon | GET | `/business/addons/active/{business_id}` |
| 查询addon详情 | GET | `/business/addons/detail/{addon_id}` |

---

## Skill 2b: `shanyin-partner-relations` — 合作方关系

**触发词**: 合作方关系建立与维护

**API 端点**:

| 操作 | 方法 | 端点 |
|------|------|------|
| 创建合作方关系 | POST | `/partner-relations/create` |
| 删除合作方关系 | POST | `/partner-relations/delete` |
| 查询合作方关系 | GET | `/partner-relations/list` |
| 按合作方筛选 | GET | `/partner-relations/list?partner_id=` |
| 按所有者筛选 | GET | `/partner-relations/list?owner_type=&owner_id=` |
| 按合作模式筛选 | GET | `/partner-relations/list?relation_type=` |

---

## Skill 4: `shanyin-supply` — 供应链

**触发词**: 供应链协议、供应链定价、结算条款

**API 端点**:

| 操作 | 方法 | 端点 |
|------|------|------|
| 创建供应链协议 | POST | `/supply-chain/create` |
| 更新供应链协议 | PUT | `/supply-chain/{sc_id}` |
| 删除供应链协议 | DELETE | `/supply-chain/{sc_id}` |
| 查询供应链列表 | GET | `/supply-chain/list` |
| 供应链详情 | GET | `/supply-chain/{sc_id}` |
| 模糊搜索供应链 | GET | `/supply-chain/list?search=` |
| 按供应商筛选 | GET | `/supply-chain/list?supplier_id=` |
| 按状态筛选 | GET | `/supply-chain/list?status=` |
| 按类型筛选 | GET | `/supply-chain/list?type=` |
| 按创建时间筛选 | GET | `/supply-chain/list?date_from=&date_to=` |
| SKU协议价查询 | GET | `/query/sku-agreement-price?sc_id=&business_id=&sku_name=` |

---

## Skill 5: `shanyin-vc` — VC 执行

**触发词**: 虚拟合同/VC、合同要素、采购/供应/退货

**API 端点**:

| 操作 | 方法 | 端点 |
|------|------|------|
| 创建设备采购VC | POST | `/vc/create-procurement` |
| 创建物料供应VC | POST | `/vc/create-material-supply` |
| 创建库存采购VC | POST | `/vc/create-stock-procurement` |
| 创建mat采购VC | POST | `/vc/create-mat-procurement` |
| 创建退货VC | POST | `/vc/create-return` |
| 库存拨付 | POST | `/vc/allocate-inventory` |
| 更新VC | POST | `/vc/update` |
| 删除VC | POST | `/vc/delete` |
| 查询VC列表 | GET | `/vc/list` |
| VC详情 | GET | `/vc/{vc_id}` |
| 模糊搜索VC | GET | `/vc/list?search=` |
| 按客户筛选 | GET | `/vc/list?customer_id=` |
| 按状态筛选 | GET | `/vc/list?status=` |
| 按创建时间筛选 | GET | `/vc/list?date_from=&date_to=` |
| 可退货货品查询 | GET | `/query/returnable-items?vc_id=&direction=` |
| 查询VC状态日志 | GET | `/vc/{vc_id}/status-logs` |
| 查询VC资金流 | GET | `/vc/{vc_id}/cash-flows` |

---

## Skill 6: `shanyin-logistics` — 物流运营

**触发词**: 物流计划、发货、入库、快递

**API 端点**:

| 操作 | 方法 | 端点 |
|------|------|------|
| 创建物流计划 | POST | `/logistics/create-plan` |
| 确认入库 | POST | `/logistics/confirm-inbound` |
| 更新快递信息 | POST | `/logistics/update-express` |
| 更新快递状态 | POST | `/logistics/update-express-status` |
| 批量推进快递 | POST | `/logistics/bulk-progress` |
| 查询物流列表 | GET | `/logistics/list` |
| 物流详情 | GET | `/logistics/{log_id}` |
| 按VC筛选 | GET | `/logistics/list?vc_id=` |
| 按状态筛选 | GET | `/logistics/list?status=` |
| 按创建时间筛选 | GET | `/logistics/list?date_from=&date_to=` |
| 按快递号搜索 | GET | `/logistics/list?tracking_number=` |
| 可退货货品查询 | GET | `/query/returnable-items?vc_id=&direction=` |

---

## Skill 7: `shanyin-cashflow` — 资金操作

**触发词**: 资金流水、收款、付款、转账

**API 端点**:

| 操作 | 方法 | 端点 |
|------|------|------|
| 录入资金流水 | POST | `/finance/create-cashflow` |
| 内部转账 | POST | `/finance/internal-transfer` |
| 外部资金出入 | POST | `/finance/external-fund` |
| 查询资金流列表 | GET | `/finance/cashflows` |
| 资金流详情 | GET | `/finance/cashflows/{cf_id}` |
| 按VC筛选 | GET | `/finance/cashflows?vc_id=` |
| 按多VC筛选 | GET | `/finance/cashflows?vc_ids=1,2,3` |
| 按类型筛选 | GET | `/finance/cashflows?type=` |
| 按付款方筛选 | GET | `/finance/cashflows?payer_id=` |
| 按收款方筛选 | GET | `/finance/cashflows?payee_id=` |
| 按创建时间筛选 | GET | `/finance/cashflows?date_from=&date_to=` |
| 按金额范围筛选 | GET | `/finance/cashflows?amount_min=&amount_max=` |
| 收付款方建议 | GET | `/query/suggested-cashflow-parties?vc_id=&cf_type=` |
| VC收付款进度 | GET | `/query/cashflow-progress?vc_id=` |
| 对方方信息查询 | GET | `/query/counterpart-info?vc_id=` |

---

## Skill 8: `shanyin-inventory` — 库存查询

**触发词**: 设备库存、物料库存、SN码

**API 端点**:

| 操作 | 方法 | 端点 |
|------|------|------|
| 查询设备库存 | GET | `/inventory/equipment` |
| 按VC筛选设备 | GET | `/inventory/equipment?vc_id=` |
| 按点位筛选设备 | GET | `/inventory/equipment?point_id=` |
| 按SKU筛选设备 | GET | `/inventory/equipment?sku_id=` |
| 按运营状态筛选 | GET | `/inventory/equipment?operational_status=` |
| 按设备状态筛选 | GET | `/inventory/equipment?device_status=` |
| 按SN码模糊搜索 | GET | `/inventory/equipment?sn=` |
| 按押金范围筛选 | GET | `/inventory/equipment?deposit_amount_min=&deposit_amount_max=` |
| 查询物料库存 | GET | `/inventory/material` |
| 物料库存三场景 | GET | 见下方说明 |
| 库存可用性校验 | POST | `/query/inventory-availability` |

**物料库存三场景**:
1. `sku_id + warehouse_point_id` → 返回该SKU在该仓库的库存数量
2. 只有 `sku_id` → 返回该SKU所有仓库的库存分布
3. 只有 `warehouse_point_id` → 返回该仓库下所有SKU的库存（仅返回有库存的）

---

## Skill 9: `shanyin-finance-analyst` — 财务视角 SQL 分析

**触发词**: 财务报表、会计科目、凭证、应收应付、账龄分析、资金分析

**职责说明**：从财务会计视角执行 SQL 查询，关注科目余额、凭证流水、应收应付、资金进出。

**API 端点**:

| 操作 | 方法 | 端点 |
|------|------|------|
| 执行财务 SQL 查询 | POST | `/sql/query` |

---

## Skill 10: `shanyin-analytics` — 自然语言 SQL 复杂查询

**触发词**: 复杂统计、跨表查询、数据分析、生成报表、按任意维度汇总

**职责说明**：将自然语言查询意图转换为 SQL，执行复杂分析查询。

- 基本列表/详情查询 → 各模块自己的 API
- 复杂聚合/跨表/多维度 → 走 analytics

**API 端点**:

| 操作 | 方法 | 端点 |
|------|------|------|
| 执行复杂 SQL 查询 | POST | `/sql/query` |

---

## Skill 边界说明

```
shanyin-master              ← 6类主数据的 CRUD，无业务逻辑
shanyin-business            ← 业务生命周期 + addon 政策，关联 master/vc
shanyin-partner-relations   ← 合作方关系，关联 master/partner
shanyin-supply              ← 供应链协议，关联 supplier/master
shanyin-vc                  ← 虚拟合同执行，关联 business/supply_chain/master
shanyin-logistics           ← 物流运营，关联 vc/inventory
shanyin-cashflow            ← 资金流 + 转账，关联 vc/master
shanyin-inventory           ← 库存只读查询，关联 vc/logistics
shanyin-finance-analyst     ← 财务会计视角 SQL，科目/凭证/应收应付
shanyin-analytics           ← 自然语言 SQL 复杂查询（通用）
```

---

## API Pattern 约定

| Pattern | 说明 | 适用场景 |
|---------|------|----------|
| List | 分页列表查询 | 资源列表，带过滤条件 |
| Detail | 单条详情查询 | 查看具体记录 |
| Create | 创建资源 | POST 带 body |
| Update | 更新资源（批量） | POST 带 body 数组 |
| Delete | 删除资源（批量） | POST 带 body 数组 |
| Search | 模糊搜索 | `?search=` 或 `?q=` |
| Suggested | 自动补全 | `?q=` 返回建议列表 |
| Aggregate | 统计聚合 | 返回计数/求和/分组 |
| Bulk | 批量操作 | 一次处理多条记录 |

---

## 参数命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 主键多值 | `ids` | `ids=1,2,3` |
| 外键多值 | `{entity}_ids` | `vc_ids=1,2,3` |
| 日期范围 | `date_from`, `date_to` | `date_from=2026-04-01` |
| 金额范围 | `amount_min`, `amount_max` | `amount_min=1000` |
| 搜索 | `search` 或 `q` | `search=张三`（List）/ `q=张`（Suggest） |
| 分页 | `page`, `size` | `page=1, size=50` |
| 模糊搜索 | `?q=` | Suggest 端点专用 |
