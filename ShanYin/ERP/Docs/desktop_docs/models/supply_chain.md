# Supply Chain（供应链模块）

## 模块职责

管理与供应商之间的供应链协议，包括定价配置、付款条款模板。是采购类 VC 的父级，用于制定向下传播的规则。

## 核心数据模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `supplier_id` | Integer | 关联供应商 |
| `type` | String | 供应链类型 |
| `pricing_config` | JSON | SKU 与单价的映射配置 |
| `payment_terms` | JSON | 付款条款（期限、比例等），用于生成时间规则 |

## 核心 Action 函数

| 函数 | 文件 | 作用 |
|------|------|------|
| `create_supply_chain_action` | `logic/supply_chain/actions.py` | 创建/更新供应链协议，自动生成付款条款时间规则 |
| `delete_supply_chain_action` | `logic/supply_chain/actions.py` | 删除供应链协议（需无关联 VC） |

## 关键业务逻辑

### 定价配置（pricing_config）

`pricing_config` 是一个 JSON，key 为 SKU 名称，value 为单价。用于：
- 物料采购时查询供应商协议价
- `services.py` 中 `get_sku_agreement_price()` 会优先查询 SC 的定价

### 付款条款与时间规则生成

`payment_terms` 定义付款节点，`advance_business_stage_action` 在 LANDING 阶段调用：

```python
RuleManager.generate_rules_from_payment_terms(payment_terms, related_id, related_type)
```

生成两类时间规则：
- **预付约束**：`CASH_PREPAID → SUBJECT_SHIPPED`（发货前需预付）
- **结算规则**：`SUBJECT_FINISH → SUBJECT_CASH_FINISH`（履约完成后结清）

## 与其他模块的关系

- **→ Supplier**：通过 `supplier_id` 关联
- **→ VC**：SupplyChain 是采购类 VC（`EQUIPMENT_PROCUREMENT`、`MATERIAL_PROCUREMENT`）的父级
- **→ Business**：通过 VC 间接关联 Business
- **→ TimeRule**：可制定模板规则，向下传播到 VC → Logistics

## 事件发布

| 事件 | 触发时机 |
|------|----------|
| `SUPPLY_CHAIN_CREATED` | 创建供应链协议 |

## 开发注意事项

- 删除 SupplyChain 前必须确认无关联 VC
- `pricing_config` 和 `payment_terms` 均为 JSON，需注意 Schema 兼容性
