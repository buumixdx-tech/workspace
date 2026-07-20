# Logistics（物流模块）

## 模块职责

管理物流发货计划、快递单生命周期、入库确认。是连接 VC 与库存变动的关键节点——入库确认触发库存更新、状态机推进和财务记账的三方联动。

## 核心数据模型

### Logistics（物流主单）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `virtual_contract_id` | Integer | 关联 VC |
| `status` | String | 物流主单状态 |
| `finance_triggered` | Boolean | 是否已触发财务记账（防重） |

### ExpressOrder（快递单）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `logistics_id` | Integer | 关联物流主单 |
| `tracking_number` | String | 快递单号 |
| `items` | JSON | 快递包含的货品明细 |
| `status` | String | 快递单状态 |

## 物流主单状态流转

```
PENDING（待发货）→ TRANSIT（在途）→ SIGNED（签收）→ FINISH（完成）
```

## 物流 → 状态机推进逻辑

`logistics_state_machine()` 根据快递单状态更新主单：

| 快递单状态 | 主单状态更新 |
|------------|--------------|
| 全部 SIGNED | → SIGNED |
| 全部 FINISH | → FINISH |
| 任意 TRANSIT | → TRANSIT |
| 其他 | → PENDING |

## 关键 Action 函数

| 函数 | 作用 |
|------|------|
| `create_logistics_plan_action` | 创建物流发货计划 + 创建 ExpressOrder |
| `confirm_inbound_action` | **核心**：确认收货/入库，触发库存变动 + 状态机 + 财务 |
| `update_express_order_action` | 更新快递单信息 |
| `update_express_order_status_action` | 推进快递单状态 |
| `bulk_progress_express_orders_action` | 批量推进快递单状态 |

## 入库确认核心流程（confirm_inbound_action）

```
confirm_inbound_action()
  → 设备采购：校验 SN 不冲突
  → inventory_module()            # 处理库存变动
  → logistics_state_machine()     # 更新物流状态 → 触发 VC 状态机
  → finance_module(logistics_id)  # 触发财务记账
  → emit_event(LOGISTICS_STATUS_CHANGED)
     → time_rule_completion_listener  # 记录规则触发时间
```

## SN 校验逻辑（设备采购入库）

设备采购入库时，系统校验：
- 所有 SN 必须属于该 VC
- SN 不能与已有运营中设备冲突（`operational_status != STOCK`）
- SN 不能重复入同一个库

## 与其他模块的关系

- **→ VC**：通过 `virtual_contract_id` 关联，入库影响 VC 三状态机
- **→ ExpressOrder**：一个 Logistics 可包含多个 ExpressOrder
- **→ Inventory**：入库确认调用 `inventory_module()` 更新库存
- **→ Finance**：入库确认调用 `finance_module()` 生成记账凭证
- **→ TimeRule**：物流创建时同步父级（VC/Business/SupplyChain）规则
- **→ StateMachine**：`logistics_state_machine()` 在 `logic/state_machine.py`

## 事件发布

| 事件 | 触发时机 |
|------|----------|
| `LOGISTICS_PLAN_CREATED` | 创建物流计划 |
| `LOGISTICS_STATUS_CHANGED` | 物流主单状态变化 |
| `EXPRESS_ORDER_UPDATED` | 快递单信息更新 |
| `EXPRESS_ORDER_STATUS_CHANGED` | 快递单状态变更 |
| `EXPRESS_ORDER_BULK_PROGRESS` | 批量推进快递单 |

## 开发注意事项

- `confirm_inbound_action` 是最关键函数，涉及多个模块的联动
- `finance_triggered` 防重标志：财务只应被触发一次
- 退货物流的处理方向与正向采购相反（扣减库存 + 反向记账）
