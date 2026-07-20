# Events（领域事件系统）

## 模块职责

领域事件系统是系统的消息中枢，通过发布-订阅模式实现模块间的松耦合。所有业务状态变更通过 `emit_event()` 发布到 `SystemEvent` 表，再分发给已注册的监听器，实现跨模块联动。

## 核心组件

| 文件 | 职责 |
|------|------|
| `dispatcher.py` | `emit_event()` — 发布领域事件并持久化到 SystemEvent 表，同时触发监听器 |
| `listeners.py` | `register_listener()` / `unregister_listener()` / `dispatch()` — 观察者注册与分发 |
| `responders.py` | 内置响应器实现 |

## emit_event 签名

```python
emit_event(
    session: Session,
    event_type: str,          # 事件类型（如 VC_CREATED）
    aggregate_type: str,       # 聚合根类型（如 VirtualContract）
    aggregate_id: int,        # 聚合根 ID
    payload: dict = None       # 额外数据
) -> SystemEvent
```

## 事件流程

```
Action 函数执行状态变更
  → emit_event() 写入 SystemEvent 表
  → dispatch() 查找所有匹配监听器
  → 各监听器/响应器执行副作用
  （事务由调用方控制，commit/rollback 在 Action 层）
```

## SystemEvent 表结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `event_type` | String | 事件类型 |
| `aggregate_type` | String | 聚合根类型 |
| `aggregate_id` | Integer | 聚合根 ID |
| `payload` | JSON | 事件附加数据 |
| `pushed_to_ai` | Boolean | 是否已推送给 AI |
| `created_at` | DateTime | 创建时间 |

## SystemEventType 一览

### 业务项目事件
- `BUSINESS_CREATED`
- `BUSINESS_STATUS_CHANGED`
- `BUSINESS_STAGE_ADVANCED`
- `BUSINESS_DELETED`

### VC 事件
- `VC_CREATED`
- `VC_UPDATED`
- `VC_DELETED`
- `VC_STATUS_TRANSITION` — 业务总体状态跳变
- `VC_SUBJECT_TRANSITION` — 标的状态跳变
- `VC_CASH_TRANSITION` — 资金状态跳变
- `VC_GOODS_CLEARED` — 货款结清
- `VC_DEPOSIT_CLEARED` — 押金结清

### 供应链事件
- `SUPPLY_CHAIN_CREATED`

### 物流事件
- `LOGISTICS_PLAN_CREATED`
- `LOGISTICS_STATUS_CHANGED` — 物流主单状态变化
- `EXPRESS_ORDER_UPDATED`
- `EXPRESS_ORDER_STATUS_CHANGED`
- `EXPRESS_ORDER_BULK_PROGRESS`

### 财务事件
- `CASH_FLOW_RECORDED`
- `INTERNAL_TRANSFER`
- `EXTERNAL_FUND_FLOW`

### 规则事件
- `RULE_UPDATED`
- `RULE_DELETED`
- `RULES_TRIGGERED_BY_LOGISTICS`

### 预警事件
- `INVENTORY_LOW_STOCK_WARNING`

### 附加业务事件
- `ADDON_CREATED` — 附加业务创建
- `ADDON_UPDATED` — 附加业务更新
- `ADDON_DEACTIVATED` — 附加业务失效

### 主数据事件
- `MASTER_CREATED`

## 内置响应器（responders.py）

### time_rule_completion_listener

| 属性 | 说明 |
|------|------|
| 监听事件 | `LOGISTICS_STATUS_CHANGED`（目标状态=FINISH） |
| 作用 | 在物流完成时，自动记录触发事件时间到关联的时间规则，推动 TimeRule 状态演进 |

### inventory_low_stock_listener

| 属性 | 说明 |
|------|------|
| 监听事件 | `VC_CREATED`（仅 MATERIAL_SUPPLY 类型） |
| 作用 | 检查 VC 中所需 SKU 的库存水位，若低于阈值发布 `INVENTORY_LOW_STOCK_WARNING` |

## 监听器注册方式

```python
from logic.events.listeners import register_listener

def my_listener(session, event):
    # event.event_type, event.aggregate_type, event.aggregate_id, event.payload
    pass

register_listener("VC_CREATED", my_listener)
```

监听器签名为 `(session, event) -> None`。

## 跨模块联动示例

### VC 创建 → 库存预警
```
create_*_vc_action()
  → emit_event(VC_CREATED)
    → inventory_low_stock_listener
      → 检查库存水位
        → 不足则 emit_event(INVENTORY_LOW_STOCK_WARNING)
```

### 物流完成 → 规则触发记录
```
confirm_inbound_action()
  → emit_event(LOGISTICS_STATUS_CHANGED, to=FINISH)
    → time_rule_completion_listener
      → 查询关联 TimeRule
      → 记录触发时间
      → 更新 TimeRule 状态
```

## SystemAggregateType（聚合根类型）

| 类型 | 说明 |
|------|------|
| `Business` | 业务项目 |
| `VirtualContract` | 虚拟合同 |
| `SupplyChain` | 供应链 |
| `TimeRule` | 时间规则 |
| `Logistics` | 物流 |
| `ExpressOrder` | 快递单 |
| `CashFlow` | 资金流水 |
| `FinancialJournal` | 财务凭证 |
| `MaterialInventory` | 物料库存 |
| `EquipmentInventory` | 设备库存 |
| `ChannelCustomer` | 渠道客户 |
| `Point` | 点位 |
| `Supplier` | 供应商 |
| `SKU` | SKU |
| `ExternalPartner` | 合作伙伴 |
| `BankAccount` | 银行账户 |
| `AddonBusiness` | 附加业务政策 |

## 开发注意事项

- `emit_event()` 不控制事务，commit/rollback 由调用方负责
- 监听器执行顺序不确定，避免在监听器中执行有顺序依赖的操作
- `SystemEvent.pushed_to_ai` 用于 AI 推送标识，业务逻辑中不涉及
