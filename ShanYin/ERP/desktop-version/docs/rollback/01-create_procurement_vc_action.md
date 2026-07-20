# create_procurement_vc_action 快照分析

**类型：纯新建（无现有记录被修改）**

---

## 代码路径

```
session.add(new_vc)                  → session.new += {VC}
session.flush()                       → VC.id 分配

RuleManager.sync_from_parent()       → 可能 INSERT TimeRule（条件：父级有模板）
    └→ _upsert_child_rule()
           └→ session.add(TimeRule); session.flush()

if draft_rules:                       → 可能 INSERT TimeRule（条件）
    session.add(TimeRule...)

apply_offset_to_vc()
    ├→ query FinanceAccount           SELECT
    ├→ new_cf = CashFlow(...)
    │   session.add(new_cf)
    │   session.flush()              → CashFlow.id 分配
    └→ finance_module(cf_id)
          └→ record_entries(...)
                ├→ session.add(FinancialJournal)
                ├→ session.flush()   → FinancialJournal.id 分配
                ├→ journal.cash_flow_record = CashFlowLedger  → 关系创建
                ├→ save_voucher()    → JSON 文件
                └→ update_report()   → report.json

    └→ virtual_contract_state_machine()
          （新建 VC 的 Logistics 不存在，subject_status/cash_status 保持初始值 EXE，无实际 UPDATE）

emit_event()
    ├→ session.add(SystemEvent)
    ├→ session.flush()               → SystemEvent.id 分配
    └→ dispatch() → listeners
          └→ inventory_low_stock_listener（EQUIPMENT_PROCUREMENT 不触发，仅 MATERIAL_SUPPLY）
```

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `session.add(new_vc)` | VirtualContract | INSERT | 无条件 |
| 2 | `session.add(TimeRule)` | TimeRule | INSERT | 父级有模板规则时 |
| 3 | `session.add(TimeRule)` | TimeRule | INSERT | `draft_rules` 不为空时 |
| 4 | `session.add(CashFlow)` | CashFlow | INSERT | `apply_offset_to_vc` 中 `balance > 0.01` |
| 5 | `session.add(FinancialJournal)` | FinancialJournal | INSERT | `record_entries` 被调用 |
| 6 | `CashFlowLedger` 关系 | CashFlowLedger | INSERT | `level1=CASH` 时 |
| 7 | `session.add(SystemEvent)` | SystemEvent | INSERT | `emit_event` 无条件执行 |

**文件系统改动：**
- `data/finance/finance-voucher/CashFlow_{id}.json`
- `data/finance/finance-report/report.json`

---

## snapshot_before

```python
{}
```

**原因：** 纯新建 action，没有任何现有记录被修改（UPDATE/DELETE）。VC 创建时 subject_status/cash_status 就已是最终值（EXE），`apply_offset_to_vc` 不会再次修改新建 VC 的状态。

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
                "supply_chain_id": 2,
                "type": "EQUIPMENT_PROCUREMENT",
                "status": "EXE",
                "subject_status": "EXE",
                "cash_status": "EXE",
                "elements": {...},
                "deposit_info": {"should_receive": 5000.0, "total_deposit": 0.0},
                "description": "..."
            }
        },
        {
            "class": "CashFlow",
            "id": 10,
            "data": {
                "id": 10,
                "virtual_contract_id": 5,
                "type": "OFFSET_PAY",
                "amount": 3000.0,
                "transaction_date": "2026-04-10T10:00:00"
            }
        },
        {
            "class": "FinancialJournal",
            "id": 20,
            "data": {
                "id": 20,
                "voucher_no": "CSH-10-ABCD12",
                "account_id": 3,
                "debit": 3000.0,
                "credit": 0.0,
                "ref_type": "CashFlow",
                "ref_id": 10,
                "ref_vc_id": 5
            }
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
            "class": "TimeRule",
            "id": 31,
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

## rollback

```python
# 逆向删除所有新记录（外键约束逆序）
session.delete(SystemEvent)
session.delete(CashFlowLedger)
session.delete(FinancialJournal)
session.delete(CashFlow)
session.delete(TimeRule)
session.delete(VirtualContract)

# 删除 voucher JSON 文件
os.remove("data/finance/finance-voucher/CashFlow_10.json")

# void_report() 清理 report.json
void_report("CashFlow", 10, transaction_date)
```

---

## redo

```python
# 从 snapshot_after 重建所有记录
for record in snapshot_after["records"]:
    ModelClass = globals()[record["class"]]
    obj = ModelClass(**record["data"])
    session.add(obj)
session.flush()

# 重建 voucher JSON
save_voucher(content, "CashFlow_10.json")

# update_report() 幂等追加
update_report(content)
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
