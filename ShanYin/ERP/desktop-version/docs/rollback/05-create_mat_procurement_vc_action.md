# create_mat_procurement_vc_action 快照分析

**类型：纯新建（无现有记录被修改）**

---

## 代码路径

```
session.query(SupplyChain)                       SELECT
session.query(Point)                             SELECT（_get_supplier_warehouse / _get_our_warehouses 等）

session.add(new_vc)                              → session.new += {VC}
session.flush()                                   → VC.id 分配

RuleManager.sync_from_parent()                   → 可能 INSERT TimeRule（条件：无 draft_rules）

apply_offset_to_vc()
    └→ 与 create_procurement_vc_action 相同
          ├→ INSERT CashFlow（条件：balance > 0.01）
          ├→ INSERT FinancialJournal
          ├→ INSERT CashFlowLedger（条件）
          ├→ save_voucher() → JSON 文件
          └→ update_report() → report.json

emit_event()
    ├→ INSERT SystemEvent
    └→ dispatch() → listeners（无库存检查触发）
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
                "supply_chain_id": 3,
                "type": "MATERIAL_PROCUREMENT",
                "status": "EXE",
                "subject_status": "EXE",
                "cash_status": "EXE",
                "elements": {...},
                "description": "物料采购: X项物料"
            }
        },
        {
            "class": "CashFlow",        # 条件
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

| 区别点 | create_procurement_vc_action | create_mat_procurement_vc_action |
|--------|----------------------------|----------------------------------|
| VC.type | EQUIPMENT_PROCUREMENT | MATERIAL_PROCUREMENT |
| business_id | `= payload.business_id` | `= None`（无关联业务） |
| deposit_info | `{should_receive: payload.total_deposit, total_deposit: 0.0}` | 无（不关联押金） |
| draft_rules | 有（可选） | 无 |
