# create_stock_procurement_vc_action 快照分析

**类型：纯新建（无现有记录被修改）**

---

## 代码路径

```
session.query(SupplyChain)                       SELECT
session.query(Point)                             SELECT（_get_supplier_warehouse / _get_our_warehouses 等）

session.add(new_vc)                              → session.new += {VC}
session.flush()                                   → VC.id 分配

RuleManager.sync_from_parent()                   → 可能 INSERT TimeRule

apply_offset_to_vc()
    └→ 与 create_procurement_vc_action 相同
          ├→ INSERT CashFlow（条件）
          ├→ INSERT FinancialJournal
          ├→ INSERT CashFlowLedger（条件）
          ├→ save_voucher() → JSON 文件
          └→ update_report() → report.json

emit_event()
    └→ INSERT SystemEvent
```

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `session.add(new_vc)` | VirtualContract | INSERT | 无条件 |
| 2 | `session.add(TimeRule)` | TimeRule | INSERT | 父级有模板规则时 |
| 3 | `session.add(CashFlow)` | CashFlow | INSERT | `apply_offset_to_vc` 中 `balance > 0.01` |
| 4 | `session.add(FinancialJournal)` | FinancialJournal | INSERT | `record_entries` |
| 5 | `CashFlowLedger` 关系 | CashFlowLedger | INSERT | `level1=CASH` |
| 6 | `session.add(SystemEvent)` | SystemEvent | INSERT | 无条件 |

**文件系统改动：**
- `data/finance/finance-voucher/CashFlow_{id}.json`
- `data/finance/finance-report/report.json`

---

## snapshot_before

```python
{}
```

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
                "business_id": None,
                "supply_chain_id": 2,
                "type": "STOCK_PROCUREMENT",
                "status": "EXE",
                "subject_status": "EXE",
                "cash_status": "EXE",
                "deposit_info": {"should_receive": 0.0, "total_deposit": 0.0},
                "elements": {...},
                "description": "库存采购: X项设备"
            }
        },
        {
            "class": "CashFlow",
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
    "files": [...]
}
```

---

## 与 create_procurement_vc_action 的关键区别

| 区别点 | create_procurement_vc_action | create_stock_procurement_vc_action |
|--------|----------------------------|--------------------------------------|
| VC.type | EQUIPMENT_PROCUREMENT | STOCK_PROCUREMENT |
| business_id | `= payload.business_id` | `= None`（不关联业务） |
| deposit_info | 有实际值 | `{should_receive: 0.0, total_deposit: 0.0}` |
| draft_rules | 有（可选） | 无 |
