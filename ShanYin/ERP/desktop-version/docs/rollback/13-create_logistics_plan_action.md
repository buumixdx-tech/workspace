# create_logistics_plan_action 快照分析

**类型：纯新建（无现有记录被修改）**

---

## 代码路径

```
session.query(VirtualContract)                    SELECT

session.query(Logistics).filter(...).first()     SELECT
if not log:
    session.add(log)                            ← INSERT Logistics（条件：不存在时）
    session.flush()                              → Logistics.id 分配
    RuleManager.sync_from_parent()               ← INSERT TimeRule（条件）

for order_data in payload.orders:
    session.add(ExpressOrder)                   ← INSERT ExpressOrder × N

emit_event()
    └→ INSERT SystemEvent
```

---

## DB 改动清单

| # | 操作 | 表 | 类型 | 条件 |
|---|------|-----|------|------|
| 1 | `session.add(Logistics)` | Logistics | INSERT | 条件：该 VC 尚无物流计划时 |
| 2 | `session.add(TimeRule)` | TimeRule | INSERT | 条件：Logistics 新建时 |
| 3 | `session.add(ExpressOrder)` | ExpressOrder | INSERT | 无条件（每个 order） |
| 4 | `session.add(SystemEvent)` | SystemEvent | INSERT | 无条件 |

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
            "class": "Logistics",
            "id": 8,
            "data": {
                "id": 8,
                "virtual_contract_id": 5,
                "status": "PENDING",
                ...
            }
        },
        {
            "class": "TimeRule",
            "id": 30,
            "data": {...}
        },
        {
            "class": "ExpressOrder",
            "id": 50,
            "data": {
                "id": 50,
                "logistics_id": 8,
                "tracking_number": "SF123456789",
                "status": "PENDING",
                ...
            }
        },
        {
            "class": "ExpressOrder",
            "id": 51,
            "data": {...}
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

**说明：** `create_logistics_plan_action` 不生成 FinancialJournal（无财务凭证），无 JSON 文件。

---

## 特殊情况：Logistics 已存在

如果该 VC 已有物流计划，则不新建 Logistics 和 TimeRule：

| # | 操作 | 表 | 类型 |
|---|------|-----|------|
| 1 | `session.add(ExpressOrder)` | ExpressOrder | INSERT（多个） |
| 2 | `session.add(SystemEvent)` | SystemEvent | INSERT |

**snapshot_after 应相应调整。**

---

## begin_transaction 调用时机

```
session.add(log)
session.flush()
RuleManager.sync_from_parent()
for order in payload.orders:
    session.add(ExpressOrder)
emit_event(...)

create_operation_record(..., snapshot_before={}, snapshot_after=serialize_all_records(session))
session.commit()
```

**注意：** `record_entries` 不会被调用，无财务凭证生成。
