# update_express_order_action 快照分析

**类型：修改（UPDATE 现有记录）**

---

## 代码路径

```
session.query(ExpressOrder)                  SELECT

o.tracking_number = ...                     ← UPDATE
o.address_info = ...                        ← UPDATE

emit_event()
    └→ INSERT SystemEvent
```

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `UPDATE ExpressOrder` | ExpressOrder | UPDATE | 无条件 |
| 2 | `INSERT SystemEvent` | SystemEvent | INSERT | 无条件 |

---

## snapshot_before

```python
{
    "records": [
        {
            "class": "ExpressOrder",
            "id": 50,
            "data": {
                "tracking_number": "旧单号",     # 旧值
                "address_info": {...},           # 旧值
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
                "tracking_number": "新单号",     # 新值
                "address_info": {...},            # 新值
                ...
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
# UPDATE 回旧值
o = session.query(ExpressOrder).get(50)
for attr, old_val in snapshot_before["records"][0]["data"].items():
    setattr(o, attr, old_val)
session.delete(SystemEvent)
```

---

## 特殊情况

**不调用 `logistics_state_machine`**，无 Logistics / VirtualContract 联动修改。

---

## begin_transaction 调用时机

```
o = session.query(ExpressOrder).get(payload.order_id)
snapshot_before = serialize([o])

session.begin_nested()
o.tracking_number = payload.tracking_number
o.address_info = payload.address_info
emit_event(...)

snapshot_after = serialize_all_records(session)
create_operation_record(..., snapshot_before, snapshot_after)
session.commit()
```
