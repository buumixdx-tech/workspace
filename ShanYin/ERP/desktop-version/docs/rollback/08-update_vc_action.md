# update_vc_action 快照分析

**类型：修改（UPDATE 现有记录）**

---

## 代码路径

```
session.query(VirtualContract)                SELECT

vc.description = ...                        ← UPDATE
vc.elements = ...                           ← UPDATE
vc.deposit_info = ...                        ← UPDATE

emit_event()
    └→ INSERT SystemEvent
```

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `UPDATE VirtualContract` | VirtualContract | UPDATE | `payload.description` 非 None |
| 2 | `UPDATE VirtualContract` | VirtualContract | UPDATE | `payload.elements` 非 None |
| 3 | `UPDATE VirtualContract` | VirtualContract | UPDATE | `payload.deposit_info` 非 None |
| 4 | `INSERT SystemEvent` | SystemEvent | INSERT | `emit_event` 无条件执行 |

---

## snapshot_before

```python
{
    "records": [
        {
            "class": "VirtualContract",
            "id": 5,
            "data": {
                "description": "旧描述",          # 旧值
                "elements": {...},                  # 旧值
                "deposit_info": {...},               # 旧值
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
            "class": "VirtualContract",
            "id": 5,
            "data": {
                "description": "新描述",          # 新值
                "elements": {...},                  # 新值
                "deposit_info": {...},               # 新值
            }
        },
        {
            "class": "SystemEvent",
            "id": 40,
            "data": {...}
        }
    ]
}
```

---

## rollback

```python
# UPDATE 回 snapshot_before 中的旧值
vc = session.query(VirtualContract).get(5)
for attr, old_val in snapshot_before["records"][0]["data"].items():
    setattr(vc, attr, old_val)
session.delete(SystemEvent)
```

---

## begin_transaction 调用时机

```
# 阶段1：查询将被修改的现有记录（旧值）
vc = session.query(VirtualContract).get(payload.id)
snapshot_before = serialize([vc])

session.begin_nested()              → SAVEPOINT

vc.description = ...
vc.elements = ...
vc.deposit_info = ...
emit_event(...)

snapshot_after = serialize_all_records(session)
create_operation_record(..., snapshot_before, snapshot_after)
session.commit()
```
