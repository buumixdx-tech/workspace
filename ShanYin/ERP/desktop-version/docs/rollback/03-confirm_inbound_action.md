# confirm_inbound_action 快照分析

**类型：混合（修改多个现有记录 + 新建 FinancialJournal + 文件系统）**

---

## 代码路径

```
Line 74:  query Logistics                              SELECT
Line 78:  query VirtualContract                         SELECT
Lines 83-94: query EquipmentInventory.sn              SELECT

Line 100: log.status = LogisticsStatus.FINISH         ← UPDATE Logistics

Line 102: inventory_module(log.id, equipment_sn_json)
          ├→ EQUIPMENT_PROCUREMENT / STOCK_PROCUREMENT 分支：
          │   ├→ INSERT EquipmentInventory（每个 SN，status=OPERATING）
          │   └→ deposit_module(vc_id)
          │         └→ process_vc_deposit()
          │               ├→ UPDATE VirtualContract.deposit_info
          │               ├→ UPDATE VirtualContract.status（条件）
          │               └→ UPDATE EquipmentInventory.deposit_amount（每个设备）
          ├→ MATERIAL_PROCUREMENT 分支：
          │   ├→ INSERT/UPDATE MaterialInventory（stock_distribution）
          │   └→ UPDATE SKU.average_price
          ├→ MATERIAL_SUPPLY 分支：
          │   └→ UPDATE MaterialInventory（减库存）
          └→ RETURN 分支：
               ├→ UPDATE EquipmentInventory（point_id/status/deposit_amount）
               ├→ INSERT/UPDATE MaterialInventory
               └→ deposit_module(vc.related_vc_id)

Line 103: logistics_state_machine(log.id)
          ├→ UPDATE Logistics.status（可能覆盖 Line 100 的设置）
          ├→ virtual_contract_state_machine(vc.id, 'logistics', log.id)
          │     ├→ UPDATE VirtualContract.subject_status
          │     ├→ UPDATE VirtualContract.cash_status
          │     └→ if RETURN + subject=FINISH:
          │           deposit_module(原vc_id)
          │                 └→ process_vc_deposit()
          │                       ├→ UPDATE VirtualContract.deposit_info
          │                       ├→ UPDATE VirtualContract.status
          │                       └→ UPDATE EquipmentInventory.deposit_amount
          └→ emit_event(...)

Line 104: finance_module(logistics_id=log.id)
          └→ record_entries(...)
                ├→ INSERT FinancialJournal
                ├→ INSERT CashFlowLedger（条件：level1=CASH）
                ├→ save_voucher()    → JSON 文件
                └→ update_report()   → report.json

Lines 106-112: emit_event(...)
          ├→ INSERT SystemEvent
          └→ dispatch() → listeners
```

---

## DB 改动清单（按 VC 类型）

### EQUIPMENT_PROCUREMENT

| # | 操作 | 表 | 类型 |
|---|------|-----|------|
| 1 | UPDATE Logistics.status | Logistics | UPDATE |
| 2 | INSERT EquipmentInventory | EquipmentInventory | INSERT（每个SN） |
| 3 | UPDATE VirtualContract.subject_status | VirtualContract | UPDATE |
| 4 | UPDATE VirtualContract.deposit_info | VirtualContract | UPDATE |
| 5 | UPDATE VirtualContract.cash_status | VirtualContract | UPDATE（条件） |
| 6 | UPDATE VirtualContract.status | VirtualContract | UPDATE（条件：自动完结） |
| 7 | UPDATE EquipmentInventory.deposit_amount | EquipmentInventory | UPDATE（每个设备） |
| 8 | INSERT FinancialJournal | FinancialJournal | INSERT |
| 9 | INSERT CashFlowLedger | CashFlowLedger | INSERT（条件） |
| 10 | INSERT SystemEvent | SystemEvent | INSERT |

### MATERIAL_SUPPLY

| # | 操作 | 表 | 类型 |
|---|------|-----|------|
| 1 | UPDATE Logistics.status | Logistics | UPDATE |
| 2 | UPDATE MaterialInventory | MaterialInventory | UPDATE（减库存） |
| 3 | UPDATE VirtualContract.subject_status | VirtualContract | UPDATE |
| 4 | UPDATE VirtualContract.cash_status | VirtualContract | UPDATE（条件） |
| 5 | INSERT FinancialJournal | FinancialJournal | INSERT |
| 6 | INSERT CashFlowLedger | CashFlowLedger | INSERT（条件） |
| 7 | INSERT SystemEvent | SystemEvent | INSERT |

### RETURN

| # | 操作 | 表 | 类型 |
|---|------|-----|------|
| 1 | UPDATE Logistics.status | Logistics | UPDATE |
| 2 | UPDATE EquipmentInventory | EquipmentInventory | UPDATE（退货设备） |
| 3 | INSERT/UPDATE MaterialInventory | MaterialInventory | INSERT/UPDATE |
| 4 | UPDATE VirtualContract（退货单） | VirtualContract | UPDATE subject_status |
| 5 | UPDATE VirtualContract（原采购单） | VirtualContract | UPDATE deposit_info |
| 6 | UPDATE VirtualContract（原采购单） | VirtualContract | UPDATE status（条件） |
| 7 | UPDATE EquipmentInventory（退供应商） | EquipmentInventory | UPDATE status=DISPOSED |
| 8 | INSERT FinancialJournal | FinancialJournal | INSERT |
| 9 | INSERT CashFlowLedger | CashFlowLedger | INSERT（条件） |
| 10 | INSERT SystemEvent | SystemEvent | INSERT |

**文件系统改动：**
- `data/finance/finance-voucher/Logistics_{id}.json`
- `data/finance/finance-report/report.json`

---

## snapshot_before

必须先主动查询所有将被修改的现有记录：

```python
{
    "records": [
        {
            "class": "Logistics",
            "id": 8,
            "data": {
                "status": "PENDING",       # 旧值
                ...
            }
        },
        {
            "class": "VirtualContract",
            "id": 5,
            "data": {
                "subject_status": "EXE",   # 旧值
                "cash_status": "EXE",       # 旧值
                "deposit_info": {...},      # 旧值
                "status": "EXE"            # 旧值
            }
        },
        # 条件（按 VC 类型不同）：
        {
            "class": "EquipmentInventory",  # RETURN 类
            "id": 12,
            "data": {
                "point_id": 3,             # 旧值
                "operational_status": "OPERATING",  # 旧值
                "deposit_amount": 500.0,  # 旧值
                ...
            }
        },
        {
            "class": "MaterialInventory",  # MATERIAL 类
            "id": 7,
            "data": {
                "total_balance": 100,       # 旧值
                "stock_distribution": {...}, # 旧值
                ...
            }
        },
        {
            "class": "SKU",                # MATERIAL_PROCUREMENT
            "id": 1,
            "data": {
                "average_price": 10.0,      # 旧值
                ...
            }
        }
    ]
}
```

---

## snapshot_after

```python
{
    "records": [
        # 所有被修改记录的当前值
        {
            "class": "Logistics",
            "id": 8,
            "data": {
                "status": "FINISH",        # 新值
                ...
            }
        },
        {
            "class": "VirtualContract",
            "id": 5,
            "data": {
                "subject_status": "FINISH", # 新值
                "cash_status": "FINISH",    # 新值
                "deposit_info": {...},       # 新值
                "status": "FINISH"          # 新值（条件）
            }
        },
        {
            "class": "EquipmentInventory",  # 新增或修改
            "id": 15,
            "data": {...}
        },
        {
            "class": "FinancialJournal",    # 新增
            "id": 20,
            "data": {...}
        },
        {
            "class": "CashFlowLedger",     # 新增（条件）
            "id": 21,
            "data": {...}
        },
        {
            "class": "SystemEvent",         # 新增
            "id": 30,
            "data": {...}
        }
    ],
    "files": [
        {
            "path": "data/finance/finance-voucher/Logistics_8.json",
            "content": {...}
        }
    ]
}
```

---

## rollback

```python
# 1. DELETE 新增记录（snapshot_after 中非被修改的表）
session.delete(SystemEvent)
session.delete(CashFlowLedger)
session.delete(FinancialJournal)
session.delete(EquipmentInventory)  # 新建的设备记录

# 2. UPDATE 回 snapshot_before 中的旧值
log = session.query(Logistics).get(8)
for attr, old_val in snapshot_before["records"][0]["data"].items():
    setattr(log, attr, old_val)

vc = session.query(VirtualContract).get(5)
for attr, old_val in snapshot_before["records"][1]["data"].items():
    setattr(vc, attr, old_val)

# 3. 删除 JSON 文件
os.remove("data/finance/finance-voucher/Logistics_8.json")

# 4. void_report() 清理 report.json
void_report("Logistics", 8, logistics_timestamp)
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
save_voucher(content, "Logistics_8.json")

# update_report() 幂等追加
update_report(content)
```

---

## begin_transaction 调用时机

```
# 阶段1：查询将被修改的现有记录（旧值）
log = query(Logistics).get(log_id)
vc = query(VirtualContract).get(vc_id)
# 按 VC 类型查询可能被修改的 EquipmentInventory/MaterialInventory/SKU

snapshot_before = serialize([log, vc, ...])

session.begin_nested()              → SAVEPOINT

# 阶段2：执行所有 DB 改动
log.status = LogisticsStatus.FINISH
inventory_module(...)
logistics_state_machine(...)
finance_module(...)
emit_event(...)
session.flush()

# 阶段3：序列化并创建记录
snapshot_after = serialize_all_records(session)
create_operation_record(..., snapshot_before, snapshot_after)
session.commit()
```
