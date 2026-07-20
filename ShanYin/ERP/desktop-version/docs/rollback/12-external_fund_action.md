# external_fund_action 快照分析

**类型：纯新建（无现有记录被修改）**

---

## 代码路径

```
# 构造 entries（根据 is_inbound 分支）
# inbound:  debit=CASH, credit=lv1
# outbound: debit=lv1, credit=CASH

record_entries(session, v_no, None, "ExternalTransfer", 0, entries, date)
    ├→ query FinanceAccount                        SELECT
    ├→ session.add(FinancialJournal) × 2           ← INSERT × 2
    ├→ session.flush()                            → FinancialJournal 获得 ID
    ├→ if level1 == CASH:
    │   journal.cash_flow_record = CashFlowLedger ← INSERT CashFlowLedger
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
| 3 | `CashFlowLedger` 关系 | CashFlowLedger | INSERT | `level1=CASH` 时 |
| 4 | `session.add(SystemEvent)` | SystemEvent | INSERT | 无条件 |

**文件系统改动：**
- `data/finance/finance-voucher/ExternalTransfer_{id}.json`
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
            "class": "FinancialJournal",
            "id": 20,
            "data": {...}
        },
        {
            "class": "FinancialJournal",
            "id": 21,
            "data": {...}
        },
        {
            "class": "CashFlowLedger",
            "id": 22,
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
            "path": "data/finance/finance-voucher/ExternalTransfer_0.json",
            "content": {...}
        }
    ]
}
```

---

## 与 internal_transfer_action 的区别

| 区别点 | internal_transfer_action | external_fund_action |
|--------|--------------------------|---------------------|
| ref_type | InternalTransfer | ExternalTransfer |
| voucher_no 前缀 | TRF- | EXT-IN- / EXT-OUT- |
| ref_vc_id | None | None |
| entries | 两个都是 CASH 账户 | 一个 CASH + 一个 lv1（收入/支出类） |
