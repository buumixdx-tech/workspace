# create_inventory_allocation_action 快照分析

**类型：混合（新建 VC + 修改 EquipmentInventory）**

---

## 代码路径

```
session.query(Business)                          SELECT
session.query(Point)                            SELECT（_get_customer_points）
session.query(EquipmentInventory)               SELECT（校验 SN 是否在库）

session.add(new_vc)                            → session.new += {VC}
session.flush()                                  → VC.id 分配

for e in payload.elements:
    eq = session.query(EquipmentInventory)...    SELECT（逐个查）
    eq.operational_status = OPERATING            ← UPDATE
    eq.point_id = target_pt                      ← UPDATE
    eq.virtual_contract_id = new_vc.id           ← UPDATE

emit_event()
    └→ INSERT SystemEvent
```

**注意：** 本 action **不调用** `apply_offset_to_vc`（无预收预付核销）。

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `session.add(new_vc)` | VirtualContract | INSERT | 无条件 |
| 2 | `UPDATE EquipmentInventory` | EquipmentInventory | UPDATE | 每个 SN 一条（修改 status/point_id/vc_id） |
| 3 | `session.add(SystemEvent)` | SystemEvent | INSERT | 无条件 |

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
                "type": "INVENTORY_ALLOCATION",
                "status": "EXE",
                "subject_status": "FINISH",
                "cash_status": "FINISH",
                "elements": {...},
                "description": "库存拨付: X台设备"
            }
        },
        {
            "class": "EquipmentInventory",
            "id": 10,
            "data": {
                "operational_status": "STOCK",   # 旧值
                "point_id": 3,                  # 旧值
                "virtual_contract_id": None,     # 旧值
                ...
            }
        },
        # ... 每个 SN 一条
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
            "data": {...}
        },
        {
            "class": "EquipmentInventory",
            "id": 10,
            "data": {
                "operational_status": "OPERATING",  # 新值
                "point_id": 7,                        # 新值
                "virtual_contract_id": 5,             # 新值
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
# 1. DELETE 新建的 VC 和 SystemEvent
session.delete(SystemEvent)
session.delete(VirtualContract)

# 2. UPDATE 回 EquipmentInventory 旧值
for record in snapshot_before["records"]:
    if record["class"] == "EquipmentInventory":
        eq = session.query(EquipmentInventory).get(record["id"])
        for attr, old_val in record["data"].items():
            setattr(eq, attr, old_val)
```

---

## begin_transaction 调用时机

```
# 阶段1：查询将被修改的现有记录（旧值）
biz = session.query(Business).get(payload.business_id)
for e in payload.elements:
    for eq_id in e.sn_list:
        eq = session.query(EquipmentInventory).filter_by(sn=str(eq_id)).first()
        snapshot_before["records"].append(serialize(eq))

session.begin_nested()              → SAVEPOINT

session.add(new_vc); session.flush()
for e in payload.elements:
    eq.operational_status = OPERATING
    eq.point_id = target_pt
    eq.virtual_contract_id = new_vc.id
emit_event(...)

snapshot_after = serialize_all_records(session)
create_operation_record(..., snapshot_before, snapshot_after)
session.commit()
```
