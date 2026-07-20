# internal_transfer_action 快照分析

**类型：纯新建（无现有记录被修改）**

---

## 代码路径

```
session.query(BankAccount)                          SELECT（from_acc）
session.query(BankAccount)                          SELECT（to_acc）

record_entries(session, v_no, None, "InternalTransfer", 0, entries, date)
    ├→ query FinanceAccount                        SELECT
    ├→ session.add(FinancialJournal) × 2           ← INSERT × 2（debit + credit）
    ├→ session.flush()                            → FinancialJournal 获得 ID
    ├→ if level1 == CASH:
    │   journal.cash_flow_record = CashFlowLedger ← INSERT CashFlowLedger × 2
    ├→ save_voucher() → JSON 文件
    └→ update_report() → report.json

emit_event()
    └→ INSERT SystemEvent
```

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `session.add(FinancialJournal)` | FinancialJournal | INSERT | 无条件（debit 条目） |
| 2 | `session.add(FinancialJournal)` | FinancialJournal | INSERT | 无条件（credit 条目） |
| 3 | `CashFlowLedger` 关系 | CashFlowLedger | INSERT | `level1=CASH` 时（每个条目） |
| 4 | `session.add(SystemEvent)` | SystemEvent | INSERT | 无条件 |

**文件系统改动：**
- `data/finance/finance-voucher/InternalTransfer_{id}.json`
- `data/finance/finance-report/report.json`

---

## snapshot_before

```python
{}
```

**原因：** 纯新建，无现有记录被修改。

---

## snapshot_after

```python
{
    "records": [
        {
            "class": "FinancialJournal",
            "id": 20,
            "data": {
                "id": 20,
                "voucher_no": "TRF-XXXXXX",
                "account_id": 5,
                "debit": 10000.0,
                "credit": 0.0,
                "ref_type": "InternalTransfer",
                "ref_id": 0,
                "ref_vc_id": None,
                ...
            }
        },
        {
            "class": "FinancialJournal",
            "id": 21,
            "data": {
                "id": 21,
                "voucher_no": "TRF-XXXXXX",
                "account_id": 3,
                "debit": 0.0,
                "credit": 10000.0,
                ...
            }
        },
        {
            "class": "CashFlowLedger",
            "id": 22,
            "data": {...}
        },
        {
            "class": "CashFlowLedger",
            "id": 23,
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
            "path": "data/finance/finance-voucher/InternalTransfer_0.json",
            "content": {...}
        }
    ]
}
```

---

## rollback

```python
# 逆序删除
session.delete(SystemEvent)
session.delete(CashFlowLedger)
session.delete(CashFlowLedger)
session.delete(FinancialJournal)
session.delete(FinancialJournal)

# 删除 JSON
os.remove("data/finance/finance-voucher/InternalTransfer_0.json")

# void_report
void_report("InternalTransfer", 0, transaction_date)
```

---

## begin_transaction 调用时机

```
record_entries(...)                             → INSERT FinancialJournal × 2 + JSON + report
emit_event(...)                                 → INSERT SystemEvent
session.flush()

create_operation_record(..., snapshot_before={}, snapshot_after=serialize_all_records(session))
session.commit()
```

**注意：** `create_operation_record` 在 `record_entries` 和 `emit_event` 之后调用，此时 `session.new` 包含所有新记录。
