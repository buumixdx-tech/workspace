# 数据验证约束完整清单

> 文档生成时间: 2026-01-04
> 适用版本: ShanYin Business System v2
> 架构层级: 双层验证体系 (Schema + Guard)

---

## 📐 架构总览

系统采用**两层验证架构**，确保数据在进入核心业务逻辑之前经过严格校验：

| 层级 | 名称 | 实现位置 | 职责 | 错误处理 |
|-----|------|---------|------|---------|
| **Layer 1** | 契约层 (Schema) | `logic/actions/schema.py` | 静态、无状态校验 | 抛出 `pydantic.ValidationError` |
| **Layer 2** | 守卫层 (Guard) | 各 Action 函数内部 | 动态、有状态校验 | 返回 `ActionResult(success=False)` |

---

## 🔷 第一层：契约层约束 (Schema Validation)

### 1. VCItemSchema (虚拟合同明细项)

| 字段 | 约束类型 | 约束规则 | 错误提示 |
|------|---------|---------|---------|
| `sku_name` | Field + Validator | `min_length=1`，自动 `.strip()` | 品类名称不能为空 |
| `qty` | Field | `gt=0` | 数量必须大于零 |
| `price` | Field | `ge=0` | 单价不能为负 |
| `deposit` | Field | `ge=0`，默认 0.0 | 押金不能为负 |
| `point_name`, `sn` | Validator | 自动 `.strip()` | - |

### 2. CreateProcurementVCSchema (设备采购执行单)

| 字段/规则 | 约束类型 | 约束规则 | 错误提示 |
|----------|---------|---------|---------|
| `total_amt` | Field | `ge=0` | 总金额不能为负 |
| `total_deposit` | Field | `ge=0` | 总押金不能为负 |
| **金额一致性** | ModelValidator | `sum(qty*price) == total_amt` (±0.01) | 总计金额 ¥X 与明细计算值 ¥Y 不符 |
| **押金一致性** | ModelValidator | `sum(qty*deposit) == total_deposit` (±0.01) | 总计押金 ¥X 与明细计算值 ¥Y 不符 |

### 3. CreateReturnVCSchema (退货执行单)

| 字段 | 约束类型 | 约束规则 | 错误提示 |
|------|---------|---------|---------|
| `goods_amount` | Field | `ge=0` | 货款金额不能为负 |
| `deposit_amount` | Field | `ge=0` | 押金金额不能为负 |
| `logistics_cost` | Field | `ge=0` | 物流费不能为负 |
| `total_refund` | Field | `ge=0` | 总退款不能为负 |

### 4. CreateMatProcurementVCSchema (物料采购执行单)

| 字段 | 约束类型 | 约束规则 | 错误提示 |
|------|---------|---------|---------|
| `total_amt` | Field | `gt=0` | 采购总额必须大于零 |

### 5. CreateCashFlowSchema (资金流水)

| 字段/规则 | 约束类型 | 约束规则 | 错误提示 |
|----------|---------|---------|---------|
| `amount` | Field | `gt=0` | 金额必须大于零 |
| **自转拦截** | ModelValidator | `payer_id != payee_id` | 付款账户与收款账户不能相同 |

### 6. InternalTransferSchema (内部划拨)

| 字段/规则 | 约束类型 | 约束规则 | 错误提示 |
|----------|---------|---------|---------|
| `amount` | Field | `gt=0` | 划拨金额必须大于零 |
| **自转拦截** | ModelValidator | `from_acc_id != to_acc_id` | 转出账户与转入账户不能相同 |

### 7. ExternalFundSchema (外部出入金)

| 字段 | 约束类型 | 约束规则 | 错误提示 |
|------|---------|---------|---------|
| `amount` | Field | `gt=0` | 金额必须大于零 |
| `external_entity` | Field | `min_length=1` | 外部实体名称不能为空 |

### 8. TimeRuleSchema (时间规则)

| 字段 | 约束类型 | 约束规则 | 错误提示 |
|------|---------|---------|---------|
| `offset` | Field | `ge=0` | 偏移量不能为负 |

### 9. AdvanceBusinessStageSchema (业务阶段推进)

| 字段/规则 | 约束类型 | 约束规则 | 错误提示 |
|----------|---------|---------|---------|
| `next_status` | FieldValidator | 必须是 BusinessStatus 枚举值之一 | 非法业务阶段状态: X |
| **ACTIVE 前置条件** | ModelValidator | 进入 ACTIVE 时必须提供 `payment_terms` | 业务正式开展前必须配置结算条款 |
| **预付比例范围** | ModelValidator | `0 <= prepayment_ratio <= 1` | 预付款比例必须在 0 到 1 之间 |

### 10. 主数据 Schema

#### CustomerSchema (客户)

| 字段 | 约束类型 | 约束规则 |
|------|---------|---------|
| `name` | Field + Validator | `min_length=1`，自动 `.strip()` |

#### PointSchema (点位)

| 字段 | 约束类型 | 约束规则 |
|------|---------|---------|
| `name` | Field + Validator | `min_length=1`，自动 `.strip()` |
| `address` | Field + Validator | `min_length=1`，自动 `.strip()` |
| `receiving_address` | Field + Validator | `min_length=1`，自动 `.strip()` |

#### SupplierSchema (供应商)

| 字段 | 约束类型 | 约束规则 |
|------|---------|---------|
| `name` | Field + Validator | `min_length=1`，自动 `.strip()` |
| `address` | Field + Validator | `min_length=1`，自动 `.strip()` |

#### SKUSchema (品类)

| 字段 | 约束类型 | 约束规则 |
|------|---------|---------|
| `name` | Field + Validator | `min_length=1`，自动 `.strip()` |
| `model` | Validator | 自动 `.strip()` |

---

## 🛡️ 第二层：守卫层约束 (Business Guard)

### 1. 设备采购执行单创建 (`create_procurement_vc_action`)

| 守卫规则 | 检查逻辑 | 错误提示 |
|---------|---------|---------|
| **业务项目存在** | `session.query(Business).get(id)` | 未找到关联业务项目 |
| **项目状态校验** | `biz.status in [ACTIVE, LANDING]` | 项目当前状态为 X，不允许下达采购单 |
| **供应链协议存在** | `session.query(SupplyChain).get(id)` | 未找到供应链协议 |
| **协议类型匹配** | `sc.type == EQUIPMENT` | 该协议类型不属于设备供应，无法用于设备采购 |

### 2. 物料供应执行单创建 (`create_material_supply_vc_action`)

| 守卫规则 | 检查逻辑 | 错误提示 |
|---------|---------|---------|
| **业务项目存在** | `session.query(Business).get(id)` | 未找到关联业务项目 |
| **项目状态校验** | `biz.status == ACTIVE` | 项目尚未正式开展 (当前状态: X)，无法进行物料供应 |
| **库存充足性** | `validate_inventory_availability()` | 库存严重不足: 【仓库】的 SKU: 申请 X, 当前存量 Y |

### 3. 退货执行单创建 (`create_return_vc_action`)

| 守卫规则 | 检查逻辑 | 错误提示 |
|---------|---------|---------|
| **目标合同存在** | `session.query(VC).get(id)` | 未找到目标虚拟合同 |
| **目标单状态校验** | `subject_status in [EXE, FINISH]` | 原单标的状态为 X，此时无法发起退货 |
| **超量退货拦截** | 遍历 `return_items`，对比 `allowed_map` | 退货越界: SKU (点位:X) 申请退货 Y，而最大可退仅 Z |

### 4. 物料采购执行单创建 (`create_mat_procurement_vc_action`)

| 守卫规则 | 检查逻辑 | 错误提示 |
|---------|---------|---------|
| **供应链协议存在** | `session.query(SupplyChain).get(id)` | 未找到物料供应链协议 |
| **协议类型匹配** | `sc.type == MATERIAL` | 该协议类型非物料采购专用 |

### 5. 业务阶段推进 (`advance_business_stage_action`)

| 守卫规则 | 检查逻辑 | 错误提示 |
|---------|---------|---------|
| **业务记录存在** | `session.query(Business).get(id)` | 未找到业务记录 |
| **状态机跳转合法性** | `next_status in valid_transitions[old_status]` | 非法状态跳转：不能从 X 直接进入 Y |

**合法跳转路径定义：**
```
DRAFT       → [EVALUATION, TERMINATED]
EVALUATION  → [FEEDBACK, LANDING, TERMINATED]
FEEDBACK    → [LANDING, TERMINATED]
LANDING     → [ACTIVE, TERMINATED]
ACTIVE      → [PAUSED, TERMINATED, FINISHED]
PAUSED      → [ACTIVE, TERMINATED]
```

### 6. 入库确认 (`confirm_inbound_action`)

| 守卫规则 | 检查逻辑 | 错误提示 |
|---------|---------|---------|
| **物流记录存在** | `session.query(Logistics).get(id)` | 未找到物流记录 |
| **重复入库拦截** | `log.status != FINISH` | 该物流单已完成入库，请勿重复操作 |
| **SN 唯一性校验** | `sn_list` 与 `equipment_inventory.sn` 无交集 | SN 冲突：以下序列号已存在于系统库存中 [...] |

### 7. 资金流水录入 (`create_cash_flow_action`)

| 守卫规则 | 检查逻辑 | 错误提示 |
|---------|---------|---------|
| **关联合同存在** | `session.query(VC).get(id)` | 未找到关联虚拟合同 |
| **资金状态校验** | `vc.cash_status != FINISH` | 该合同资金状态已完成，无法再录入流水 |
| **付款账户存在** | `session.query(BankAccount).get(payer_id)` | 付款账号 (ID:X) 不存在 |
| **收款账户存在** | `session.query(BankAccount).get(payee_id)` | 收款账号 (ID:X) 不存在 |

### 8. 内部划拨 (`internal_transfer_action`)

| 守卫规则 | 检查逻辑 | 错误提示 |
|---------|---------|---------|
| **源账户存在** | `session.query(BankAccount).get(from_id)` | 源账号不存在 |
| **目标账户存在** | `session.query(BankAccount).get(to_id)` | 目标账号不存在 |

---

## 📊 约束统计

| 类别 | 数量 |
|------|------|
| **Layer 1: Field 约束** | 17 |
| **Layer 1: FieldValidator** | 8 |
| **Layer 1: ModelValidator** | 5 |
| **Layer 2: 存在性校验** | 12 |
| **Layer 2: 状态校验** | 5 |
| **Layer 2: 业务规则校验** | 4 |
| **总计** | **51** |

---

## 🔄 错误处理流程

```
┌─────────────┐    ValidationError    ┌──────────────────┐
│  UI 提交    │ ─────────────────────→│ Pydantic 捕获    │
│  表单数据   │                       │ 显示字段级错误   │
└─────────────┘                       └──────────────────┘
       │
       │ Schema 验证通过
       ▼
┌─────────────┐    ActionResult       ┌──────────────────┐
│  调用       │    (success=False)    │ UI 层捕获        │
│  Action     │ ─────────────────────→│ st.error(...)    │
└─────────────┘                       └──────────────────┘
       │
       │ Guard 验证通过
       ▼
┌─────────────┐
│  执行核心   │
│  业务逻辑   │
└─────────────┘
```

---

## 📁 相关源文件

| 文件 | 用途 |
|------|------|
| `logic/actions/schema.py` | 所有 Pydantic Schema 定义 |
| `logic/actions/vc_actions.py` | VC 创建相关 Guard |
| `logic/actions/business_actions.py` | 业务阶段推进 Guard |
| `logic/actions/logistics_actions.py` | 物流入库 Guard |
| `logic/actions/finance_actions.py` | 资金流水 Guard |
| `logic/constants.py` | 状态枚举定义 |
