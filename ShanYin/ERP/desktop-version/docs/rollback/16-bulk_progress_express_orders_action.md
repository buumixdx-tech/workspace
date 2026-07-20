# bulk_progress_express_orders_action 快照分析

**类型：混合（UPDATE 多个 ExpressOrder + 联动修改 Logistics + VirtualContract）**

---

## 代码路径

```
for oid in order_ids:
    o = session.query(ExpressOrder).get(oid)    SELECT
    o.status = target_status                    ← UPDATE ExpressOrder

    logistics_state_machine(logistics_id, o.id)   ← 每次都调用
          ├→ query Logistics                   SELECT
          ├→ UPDATE Logistics.status            ← 条件
          └→ virtual_contract_state_machine(vc.id, 'logistics', logistics_id)
                ├→ UPDATE VirtualContract.subject_status   ← 条件
                ├→ UPDATE VirtualContract.cash_status      ← 条件
                └→ if RETURN + subject=FINISH:
                      deposit_module(原vc_id)
                        └→ UPDATE VirtualContract.deposit_info

emit_event()
    └→ INSERT SystemEvent
```

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `UPDATE ExpressOrder` | ExpressOrder | UPDATE | 每个 oid 一条（N 个） |
| 2 | `UPDATE Logistics` | Logistics | UPDATE | `logistics_state_machine` 导致 Logistics 状态变化 |
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
            "class": "ExpressOrder",
            "id": 51,
            "data": {
                "status": "PENDING",           # 旧值
                ...
            }
        },
        # ... order_ids 中所有 ExpressOrder
        {
            "class": "Logistics",
            "id": 8,
            "data": {
                "status": "PENDING",           # 旧值
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

---

## snapshot_after

```python
{
    "records": [
        {
            "class": "ExpressOrder",
            "id": 50,
            "data": {
                "status": "SIGNED",           # 新值
                ...
            }
        },
        {
            "class": "ExpressOrder",
            "id": 51,
            "data": {
                "status": "SIGNED",           # 新值
                ...
            }
        },
        {
            "class": "Logistics",
            "id": 8,
            "data": {
                "status": "SIGNED",            # 新值
                ...
            }
        },
        {
            "class": "VirtualContract",
            "id": 5,
            "data": {
                "subject_status": "SIGNED",    # 新值
                "cash_status": "EXE",           # 新值
                "deposit_info": {...},          # 新值
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
# UPDATE 回旧值（ExpressOrder × N + Logistics + VirtualContract）
for record in snapshot_before["records"]:
    if record["class"] != "SystemEvent":
        obj = session.query(globals()[record["class"]]).get(record["id"])
        for attr, old_val in record["data"].items():
            setattr(obj, attr, old_val)

session.delete(SystemEvent)
```

---

## begin_transaction 调用时机

```
# 阶段1：查询所有将被修改的记录
express_orders = [session.query(ExpressOrder).get(oid) for oid in order_ids]
log = session.query(Logistics).get(logistics_id)
vc = session.query(VirtualContract).get(log.virtual_contract_id)
snapshot_before = serialize(express_orders + [log, vc])

session.begin_nested()

for oid in order_ids:
    o = session.query(ExpressOrder).get(oid)
    o.status = target_status
    logistics_state_machine(logistics_id, o.id)

emit_event(...)

snapshot_after = serialize_all_records(session)
create_operation_record(..., snapshot_before, snapshot_after)
session.commit()
```

**注意：** `logistics_state_machine` 在循环内被多次调用，但只有第一次会实际改变 Logistics/VirtualContract 状态（后续调用时 Logistics 已是目标状态，状态机判断不会再改变）。但为保险起见，snapshot_before 仍需捕获 Logistics 和 VirtualContract 旧值。
