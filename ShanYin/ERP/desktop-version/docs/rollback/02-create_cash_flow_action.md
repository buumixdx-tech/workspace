# create_cash_flow_action 快照分析

**类型：混合（新建 CashFlow + 修改现有记录）**

---

## 代码路径

```
session.add(new_cf)                     → session.new += {CashFlow}
session.flush()                          → CashFlow.id 分配

check_and_split_excess()                → 空操作（pass）

virtual_contract_state_machine(vc_id, 'cash_flow', cf.id)
    ├→ query VirtualContract              SELECT
    ├→ query Logistics                   SELECT
    ├→ query CashFlow（all）             SELECT
    ├→ UPDATE VirtualContract.subject_status   ← 条件：state 变化
    ├→ UPDATE VirtualContract.cash_status     ← 条件：state 变化
    └→ if cf.type in [DEPOSIT, RETURN_DEPOSIT]:
         deposit_module(cf_id=cf.id)
           └→ process_cf_deposit()
                  ├→ UPDATE VirtualContract.deposit_info
                  └→ process_vc_deposit()
                         ├→ UPDATE VirtualContract.deposit_info
                         ├→ UPDATE VirtualContract.status（条件：自动完结）
                         └→ UPDATE EquipmentInventory.deposit_amount

finance_module(cash_flow_id=cf.id)
    └→ process_cash_flow_finance(...)
          └→ record_entries(...)
                ├→ query FinanceAccount        SELECT
                ├→ session.add(FinancialJournal)
                ├→ session.flush()             → FinancialJournal.id 分配
                ├→ if level1 == CASH:
                │   journal.cash_flow_record = CashFlowLedger  → INSERT CashFlowLedger
                ├→ save_voucher()             → JSON 文件
                └→ update_report()             → report.json

emit_event(...)
    ├→ session.add(SystemEvent)           → INSERT SystemEvent
    ├→ session.flush()                   → SystemEvent.id 分配
    └→ dispatch() → listeners             → 纯内存，无DB改动
```

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `session.add(CashFlow)` | CashFlow | INSERT | 无条件 |
| 2 | `UPDATE VirtualContract` | VirtualContract | UPDATE | `virtual_contract_state_machine` 导致状态变化 |
| 3 | `UPDATE VirtualContract.deposit_info` | VirtualContract | UPDATE | `cf.type in [DEPOSIT, RETURN_DEPOSIT]` |
| 4 | `UPDATE VirtualContract.status` | VirtualContract | UPDATE | `process_vc_deposit` 自动完结时 |
| 5 | `UPDATE EquipmentInventory` | EquipmentInventory | UPDATE | 同上（押金分摊到设备） |
| 6 | `session.add(FinancialJournal)` | FinancialJournal | INSERT | `record_entries` 被调用 |
| 7 | `CashFlowLedger` 关系 | CashFlowLedger | INSERT | `level1=CASH` 时 |
| 8 | `session.add(SystemEvent)` | SystemEvent | INSERT | `emit_event` 无条件执行 |

**文件系统改动：**
- `data/finance/finance-voucher/CashFlow_{id}.json`
- `data/finance/finance-report/report.json`

---

## snapshot_before

```python
{
    "records": [
        {
            "class": "VirtualContract",
            "id": 5,
            "data": {
                "subject_status": "EXE",       # 旧值
                "cash_status": "EXE",          # 旧值
                "deposit_info": {"should_receive": 5000.0, "total_deposit": 0.0},  # 旧值
                "status": "EXE"                # 旧值
            }
        },
        {
            "class": "EquipmentInventory",    # 条件：cf.type in [DEPOSIT, RETURN_DEPOSIT]
            "id": 10,
            "data": {
                "deposit_amount": 0.0,        # 旧值
                ...
            }
        }
    ]
}
```

**说明：** 本 action 是混合类型（新建+修改），必须保存被修改记录的旧值。修改前需主动查询。

---

## snapshot_after

```python
{
    "records": [
        {
            "class": "CashFlow",
            "id": 10,
            "data": {...}
        },
        {
            "class": "VirtualContract",
            "id": 5,
            "data": {
                "subject_status": "FINISH",   # 新值
                "cash_status": "EXE",          # 新值（可能变化）
                "deposit_info": {...},          # 新值
                "status": "EXE"                # 新值（可能变化）
            }
        },
        {
            "class": "EquipmentInventory",
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
            "class": "SystemEvent",
            "id": 30,
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
# 1. DELETE 新增记录
session.delete(SystemEvent)
session.delete(CashFlowLedger)
session.delete(FinancialJournal)
session.delete(CashFlow)

# 2. UPDATE 回 snapshot_before 中的旧值
vc = session.query(VirtualContract).get(5)
for attr, old_val in snapshot_before["records"][0]["data"].items():
    setattr(vc, attr, old_val)

if "EquipmentInventory" in snapshot_before["records"]:
    eq = session.query(EquipmentInventory).get(10)
    for attr, old_val in snapshot_before["records"][1]["data"].items():
        setattr(eq, attr, old_val)

# 3. 删除 JSON 文件
os.remove("data/finance/finance-voucher/CashFlow_10.json")

# 4. void_report() 清理 report.json
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
session.add(new_cf); session.flush()
virtual_contract_state_machine(...)        → UPDATE VirtualContract 等
finance_module(...)                        → INSERT FinancialJournal + JSON
emit_event(...)                            → INSERT SystemEvent
session.flush()                            → 所有改动落 DB

serialize_dirty_committed_state(session)   → snapshot_before（被修改记录的旧值）
serialize_all_records(session)              → snapshot_after

create_operation_record(..., snapshot_before, snapshot_after)
session.commit()
```
