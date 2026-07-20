# create_return_vc_action 快照分析

**类型：混合（新建 + 修改）**

---

## 代码路径

```
session.query(VirtualContract)                    SELECT（target_vc）
get_returnable_items()                            SELECT（无DB改动）

session.add(new_vc)                               → session.new += {VC}
session.flush()                                    → VC.id 分配

RuleManager.sync_from_parent()                    → 可能 INSERT TimeRule

if draft_rules:                                   → 可能 INSERT TimeRule

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
| 3 | `session.add(TimeRule)` | TimeRule | INSERT | `draft_rules` 不为空时 |
| 4 | `session.add(CashFlow)` | CashFlow | INSERT | `apply_offset_to_vc` 中 `balance > 0.01` |
| 5 | `session.add(FinancialJournal)` | FinancialJournal | INSERT | `record_entries` |
| 6 | `CashFlowLedger` 关系 | CashFlowLedger | INSERT | `level1=CASH` |
| 7 | `session.add(SystemEvent)` | SystemEvent | INSERT | 无条件 |

**说明：** 退货 VC 创建时，`apply_offset_to_vc` 同样会被调用（如果 balance > 0.01）。退货单自己的 `deposit_info` 也在创建时写入，状态为 `cash_status=FINISH`（如果 `total_refund <= 0`）。

**文件系统改动：**
- `data/finance/finance-voucher/CashFlow_{id}.json`
- `data/finance/finance-report/report.json`

---

## snapshot_before

```python
{}
```

**原因：** 虽然涉及 target_vc（现有记录），但本 action 不修改 target_vc。退货逻辑是在新 VC 的 `elements` 中记录退款金额，由 `confirm_inbound` 触发库存和押金的实际变动。target_vc 的押金重算由 `confirm_inbound` 后的 `deposit_module` 完成，不由本 action 直接修改。

---

## snapshot_after

```python
{
    "records": [
        {
            "class": "VirtualContract",
            "id": 6,
            "data": {
                "id": 6,
                "related_vc_id": 5,
                "business_id": 1,
                "supply_chain_id": 2,
                "type": "RETURN",
                "status": "EXE",
                "subject_status": "EXE",
                "cash_status": "FINISH",         # total_refund=0 时为 FINISH
                "return_direction": "US_TO_SUPPLIER",
                "elements": {
                    "elements": [...],
                    "total_refund": 5000.0,
                    "goods_amount": 5000.0,
                    "deposit_amount": 2000.0
                },
                "description": "..."
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

| 区别点 | create_procurement_vc_action | create_return_vc_action |
|--------|----------------------------|-------------------------|
| VC.type | EQUIPMENT_PROCUREMENT | RETURN |
| related_vc_id | `None` | `= payload.target_vc_id` |
| return_direction | 无 | 有 |
| cash_status | `EXE` | `EXE` 或 `FINISH`（看 total_refund） |
| elements 结构 | `total_amount` | `total_refund`, `goods_amount`, `deposit_amount` |
| draft_rules | 有 | 有 |
