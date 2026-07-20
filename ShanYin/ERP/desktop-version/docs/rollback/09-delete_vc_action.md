# delete_vc_action 快照分析

**类型：删除（DELETE 现有记录）**

---

## 代码路径

```
session.query(VirtualContract)                SELECT
session.query(Logistics)                     SELECT（确认存在）

session.query(Logistics).filter(...).delete()  ← DELETE Logistics
session.delete(vc)                            ← DELETE VirtualContract

emit_event()
    └→ INSERT SystemEvent
```

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `DELETE Logistics` | Logistics | DELETE | 无条件（级联清理） |
| 2 | `DELETE VirtualContract` | VirtualContract | DELETE | 无条件 |
| 3 | `INSERT SystemEvent` | SystemEvent | INSERT | `emit_event` 无条件执行 |

**注意：** 本 action **不清理** CashFlow、TimeRule，留下孤立引用（按现有行为不变）。

---

## snapshot_before

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
                "deposit_info": {...},
                "description": "..."
            }
        },
        {
            "class": "Logistics",
            "id": 8,
            "data": {
                "id": 8,
                "virtual_contract_id": 5,
                "status": "PENDING",
                ...
            }
        }
    ]
}
```

---

## snapshot_after

```python
{}
```

**原因：** 所有记录都被删除，无新记录产生。

---

## rollback

```python
# 从 snapshot_before 重建所有被删除的记录
# 逆序：先 VirtualContract（无外键依赖），再 Logistics
for record in reversed(snapshot_before["records"]):
    ModelClass = globals()[record["class"]]
    obj = ModelClass(**record["data"])
    session.add(obj)
```

---

## begin_transaction 调用时机

```
# 阶段1：查询将被删除的现有记录（旧值）
vc = session.query(VirtualContract).get(vc_id)
logistics_list = session.query(Logistics).filter(Logistics.virtual_contract_id == vc_id).all()
snapshot_before = serialize([vc] + logistics_list)

session.begin_nested()              → SAVEPOINT

session.query(Logistics).delete()
session.delete(vc)
emit_event(...)

snapshot_after = {}
create_operation_record(..., snapshot_before, snapshot_after)
session.commit()
```
