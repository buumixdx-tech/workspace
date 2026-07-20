# create_material_supply_vc_action 快照分析

**类型：纯新建（无现有记录被修改）**

---

## 代码路径

```
session.query(Business)                          SELECT
session.query(Point)                             SELECT（_get_customer_points）
session.query(MaterialInventory)                 SELECT（_get_warehouses_with_sku_stock）
validate_inventory_availability()                SELECT（无DB改动）

session.add(new_vc)                              → session.new += {VC}
session.flush()                                   → VC.id 分配

RuleManager.sync_from_parent()                   → 可能 INSERT TimeRule（条件）
    └→ session.add(TimeRule); session.flush()

if draft_rules:                                  → 可能 INSERT TimeRule

apply_offset_to_vc()
    └→ 与 create_procurement_vc_action 完全相同
          ├→ INSERT CashFlow（条件）
          ├→ INSERT FinancialJournal
          ├→ INSERT CashFlowLedger（条件）
          ├→ save_voucher() → JSON 文件
          └→ update_report() → report.json

emit_event()
    ├→ INSERT SystemEvent
    └→ dispatch()
          └→ inventory_low_stock_listener（MATERIAL_SUPPLY 会触发库存检查）
```

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `session.add(new_vc)` | VirtualContract | INSERT | 无条件 |
| 2 | `session.add(TimeRule)` | TimeRule | INSERT | 父级有模板时 |
| 3 | `session.add(TimeRule)` | TimeRule | INSERT | `draft_rules` 不为空时 |
| 4 | `session.add(CashFlow)` | CashFlow | INSERT | `apply_offset_to_vc` 中 `balance > 0.01` |
| 5 | `session.add(FinancialJournal)` | FinancialJournal | INSERT | `record_entries` |
| 6 | `CashFlowLedger` 关系 | CashFlowLedger | INSERT | `level1=CASH` |
| 7 | `session.add(SystemEvent)` | SystemEvent | INSERT | 无条件 |

**注意：** `inventory_low_stock_listener` 是纯内存操作，不涉及 DB 改动。

**文件系统改动：**
- `data/finance/finance-voucher/CashFlow_{id}.json`
- `data/finance/finance-report/report.json`

---

## snapshot_before

```python
{}
```

**原因：** 纯新建 action，无任何现有记录被修改。

---

## snapshot_after

```python
{
    "records": [
        {
            "class": "VirtualContract",
            "id": 5,
            "data": {
                "id": 5,
                "business_id": 1,
                "type": "MATERIAL_SUPPLY",
                "status": "EXE",
                "subject_status": "EXE",
                "cash_status": "EXE",
                "elements": {...},
                "description": "..."
            }
        },
        {
            "class": "CashFlow",        # 条件：balance > 0.01
            "id": 10,
            "data": {...}
        },
        {
            "class": "FinancialJournal",
            "id": 20,
            "data": {...}
        },
        {
            "class": "CashFlowLedger",
            "id": 21,
            "data": {...}
        },
        {
            "class": "TimeRule",
            "id": 30,
            "data": {...}
        },
        {
            "class": "SystemEvent",
            "id": 40,
            "data": {...}
        }
    ],
    "files": [
        {
            "path": "data/finance/finance-voucher/CashFlow_10.json",
            "content": {...}
        }
    ]
}
```

---

## begin_transaction 调用时机

```
session.add(new_vc); session.flush()
apply_offset_to_vc(...); session.flush()
emit_event(...); session.flush()

create_operation_record(..., snapshot_before={}, snapshot_after=serialize_all_records(session))
session.commit()
```

---

## 与 create_procurement_vc_action 的区别

| 区别点 | create_procurement_vc_action | create_material_supply_vc_action |
|--------|----------------------------|----------------------------------|
| VC.type | EQUIPMENT_PROCUREMENT | MATERIAL_SUPPLY |
| deposit_info | `{should_receive, total_deposit}` | 无（不关联押金） |
| inventory_low_stock_listener | 不触发 | 触发（检查库存水位） |
| 校验 | `_get_supplier_warehouse` | `validate_inventory_availability` |

DB 改动结构相同。
