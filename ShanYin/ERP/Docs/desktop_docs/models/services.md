# Services（跨模块业务服务层）

## 模块职责

`services.py` 是系统的跨模块业务计算层，封装了不涉及数据写入的纯计算逻辑，供 UI 层和 API 层调用。确保 UI 仅负责展示，核心业务计算不分散在各处。

## 核心函数

### normalize_item_data

将混乱的字典 Key 统一为系统标准格式（统一使用 snake_case）。

```python
normalize_item_data(item: dict) -> dict
```

返回字段：`sku_id`, `sku_name`, `qty`, `price`, `receiving_point_id`, `receiving_point_name`, `sn`, `deposit`, `shipping_point_name`, `target_point_id`, `target_point_name`, `shipping_point_id`

---

### format_item_list_preview

将 Item 列表转换为用户易读的预览文本。

```python
format_item_list_preview(items: list) -> str
```

格式：`"设备A x10 | 物料B x5"`

---

### get_returnable_items

计算一个 VC 的可退货明细（核心函数）。

```python
get_returnable_items(session, target_vc_id, return_direction) -> list
```

**逻辑：**
1. 获取原始 VC elements
2. 搜集所有已发起退货单，计算锁定量
3. 设备按 SN 锁定，物料按仓库分布扣减
4. 返回剩余可退货明细

**VC 类型差异：**
- 设备采购退货：按 `operational_status` 过滤可用设备
- 物料采购退货：按仓库分布计算可退数量
- 物料供应退货：从 points 结构中按 `receiving_point_id` 分组扣减

---

### get_sku_agreement_price

获取 SKU 在特定业务 + 供应链环境下的协议单价与押金。

```python
get_sku_agreement_price(session, sc_id, business_id, sku_name) -> (unit_price, deposit, sku_type)
```

**优先级：**
1. `Business.details.pricing[str(sku_id)].price`（客户约定价，key 为 sku_id）
2. `SupplyChain.pricing_config[sku_name]`（供应链协议价，key 为 SKU 名称）
3. 默认 0.0

---

### validate_inventory_availability

统一校验库存充足性。

```python
validate_inventory_availability(session, request_items) -> (is_valid: bool, error_messages: list)
```

`request_items`：`list of (sku_name, warehouse_name, requested_qty)`

---

### get_counterpart_info

识别 VC 对应的交易对手类型与 ID（核心函数）。

```python
get_counterpart_info(session, vc) -> (counterpart_type, counterpart_id)
```

**穿透逻辑：**
- 退货 VC → 穿透 `related_vc_id` 找原始 VC
- 设备/物料采购 → 对手方为 Supplier
- 物料供应 → 对手方为 Customer

**CounterpartType：**
- `CUSTOMER` — 渠道客户
- `SUPPLIER` — 供应商
- `PARTNER` — 合作伙伴
- `BANK_ACCOUNT` — 银行账户

---

### get_suggested_cashflow_parties

根据 VC 类型和款项性质建议付款方和收款方。

```python
get_suggested_cashflow_parties(session, vc, cf_type=None) -> (payer_type, payer_id, payee_type, payee_id)
```

**场景判断逻辑：**
| VC 类型 | 款项类型 | 付款方 | 收款方 |
|---------|----------|--------|--------|
| 设备采购 | `DEPOSIT` | Customer | 我方 |
| 设备采购 | `RETURN_DEPOSIT` | 我方 | Customer |
| 物料供应 | 任意 | Customer | 我方 |
| 物料采购/设备采购 | 货款 | 我方 | Supplier |
| 退货（向供应商退） | 退款 | Supplier | 我方 |
| 退货（客户退回） | 退款 | 我方 | Customer |

---

### format_vc_items_for_display

将 VC 的 `elements` 转换为 UI 友好的展示格式。

```python
format_vc_items_for_display(vc) -> (display_type: str, items_list: list)
```

---

### calculate_cashflow_progress

计算 VC 的资金流进度，并计算实时应付金额（扣除冲抵池余额）。

```python
calculate_cashflow_progress(session, vc, existing_cfs) -> dict
```

**返回结构：**
```python
{
    'is_return': bool,
    'goods': {
        'total': float,       # 总额
        'paid': float,       # 已付（含冲抵）
        'balance': float,    # 剩余
        'pool': float,       # 冲抵池余额
        'due': float,        # 实时应付
        'label': str
    },
    'deposit': {
        'should': float,
        'received': float,
        'remaining': float
    },
    'payment_terms': dict
}
```

**冲抵池余额计算：**
- 预收客户（`PRE_COLLECTION`）：`credit_sum - debit_sum`
- 预付供应商（`PREPAYMENT`）：`debit_sum - credit_sum`

---

### get_account_balance

获取特定会计科目的实时余额。

```python
get_account_balance(session, level1_name, cp_type=None, cp_id=None) -> float
```

**返回值：** `Debit - Credit`（正数=借方余额，负数=贷方余额）

---

### get_logistics_finance_context

构造物流记账所需的领域事实 Context。

```python
get_logistics_finance_context(session, logistics_id) -> dict
```

**返回字段：**
- `logistics` / `vc` — 关联对象
- `cp_type` / `cp_id` — 对手方
- `total_amount` — 合同总额
- `is_return` — 是否退货
- `items_cost` — 物料成本（自动核算）
- `can_process` — 是否可触发财务
- `is_duplicate` — 是否重复记账

---

### get_cashflow_finance_context

构造现金流记账所需的领域事实 Context。

```python
get_cashflow_finance_context(session, cash_flow_id) -> dict
```

**返回字段：**
- `cf` / `vc` — 关联对象
- `cp_type` / `cp_id` — 对手方
- `is_income` — 是否为收入
- `ar_ap_amt` — 应记账的 AR/AP 金额
- `pre_amt` — 应记账的预付金额
- `our_bank_id` — 我方银行账户 ID
- `can_process` — 是否可触发财务

## 调用方向

```
UI 层 / API 层
    ↓ 调用
services.py（纯计算，无写入）
    ↓ 查询
models.py（只读）
```

services 层**不直接调用 Action 层**，仅通过 models 层读取数据，进行业务计算后返回结果。

## 开发注意事项

- services 层所有函数均为只读或纯计算，不涉及 `session.commit()`
- `get_counterpart_info` 和 `get_suggested_cashflow_parties` 的穿透逻辑是理解资金流向的关键
- `calculate_cashflow_progress` 中冲抵池方向判断依赖 `AccountLevel1` 的借贷方向配置
