# update_express_order_status_action 快照分析

**类型：混合（UPDATE ExpressOrder + 联动修改 Logistics + VirtualContract）**

---

## 代码路径

```
session.query(ExpressOrder)                  SELECT

o.status = payload.target_status             ← UPDATE ExpressOrder

logistics_state_machine(payload.logistics_id, o.id)
    ├→ query Logistics                       SELECT
    ├→ UPDATE Logistics.status                ← 条件：ExpressOrder 状态变化导致 Logistics 状态改变
    └→ virtual_contract_state_machine(vc.id, 'logistics', logistics_id)
          ├→ UPDATE VirtualContract.subject_status   ← 条件
          ├→ UPDATE VirtualContract.cash_status      ← 条件
          └→ if RETURN + subject=FINISH:
                deposit_module(原vc_id)
                  └→ UPDATE VirtualContract.deposit_info（条件）

emit_event()
    └→ INSERT SystemEvent
```

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `UPDATE ExpressOrder` | ExpressOrder | UPDATE | 无条件 |
| 2 | `UPDATE Logistics` | Logistics | UPDATE | `logistics_state_machine` 导致状态变化时 |
| 3 | `UPDATE VirtualContract.subject_status` | VirtualContract | UPDATE | `virtual_contract_state_machine` |
| 4 | `UPDATE VirtualContract.cash_status` | VirtualContract | UPDATE | 同上 |
| 5 | `UPDATE VirtualContract.deposit_info` | VirtualContract | UPDATE | 退货 + subject=FINISH 时 |
| 6 | `INSERT SystemEvent` | SystemEvent | INSERT | 无条件 |

---

## snapshot_before

```python
{
    "records": [
        {
            "class": "ExpressOrder",
            "id": 50,
            "data": {
                "status": "PENDING",           # 旧值
                ...
            }
        },
        {
            "class": "Logistics",
            "id": 8,
            "data": {
                "status": "PENDING",           # 旧值（如果 logistics_state_machine 会改变它）
                ...
            }
        },
        {
            "class": "VirtualContract",
            "id": 5,
            "data": {
                "subject_status": "EXE",        # 旧值
                "cash_status": "EXE",            # 旧值
                "deposit_info": {...},           # 旧值
                ...
            }
        }
    ]
}
```

**必须包含 Logistics 和 VirtualContract 旧值**：因为 `logistics_state_machine` 会根据 ExpressOrder 新状态更新它们。

---

## snapshot_after

```python
{
    "records": [
        {
            "class": "ExpressOrder",
            "id": 50,
            "data": {
                "status": "TRANSIT",           # 新值
                ...
            }
        },
        {
            "class": "Logistics",
            "id": 8,
            "data": {
                "status": "TRANSIT",           # 新值
                ...
            }
        },
        {
            "class": "VirtualContract",
            "id": 5,
            "data": {
                "subject_status": "SHIPPED",    # 新值
                "cash_status": "EXE",           # 新值
                "deposit_info": {...},           # 新值
                ...
            }
        },
        {
            "class": "SystemEvent",
            "id": 40,
            "data": {...}
        }
    ],
    "files": []
}
```

---

## rollback

```python
# UPDATE 回旧值
o = session.query(ExpressOrder).get(50)
for attr, old_val in snapshot_before["records"][0]["data"].items():
    setattr(o, attr, old_val)

log = session.query(Logistics).get(8)
for attr, old_val in snapshot_before["records"][1]["data"].items():
    setattr(log, attr, old_val)

vc = session.query(VirtualContract).get(5)
for attr, old_val in snapshot_before["records"][2]["data"].items():
    setattr(vc, attr, old_val)

session.delete(SystemEvent)
```

---

## begin_transaction 调用时机

```
# 阶段1：查询所有将被修改的现有记录
o = session.query(ExpressOrder).get(payload.order_id)
log = session.query(Logistics).get(payload.logistics_id)
vc = session.query(VirtualContract).get(log.virtual_contract_id)
snapshot_before = serialize([o, log, vc])

session.begin_nested()

o.status = payload.target_status
logistics_state_machine(payload.logistics_id, o.id)
emit_event(...)

snapshot_after = serialize_all_records(session)
create_operation_record(..., snapshot_before, snapshot_after)
session.commit()
```
