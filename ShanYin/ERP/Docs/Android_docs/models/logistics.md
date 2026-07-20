# Logistics（物流模块）

## 模块职责

管理物流发货计划、快递单生命周期、入库确认。是连接 VC 与库存变动的关键节点——入库确认触发库存更新、状态机推进和财务记账的三方联动。

## 核心数据模型

### LogisticsEntity（物流主单）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `virtualContractId` | Long | 关联 VC |
| `financeTriggered` | Boolean | 是否已触发财务记账（防重） |
| `status` | String? | 物流状态 |
| `timestamp` | Long | 创建时间（Unix ms） |

### ExpressOrderEntity（快递单）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `logisticsId` | Long | 关联物流主单 |
| `trackingNumber` | String? | 快递单号 |
| `items` | String? | JSON：货品明细 |
| `addressInfo` | String? | JSON：地址信息 |
| `status` | String? | 快递单状态 |
| `timestamp` | Long | 创建时间 |

## 物流主单状态流转

```
PENDING（待发货）→ IN_TRANSIT（在途）→ SIGNED（签收）→ COMPLETED（完成）
```

## 关键 UseCase

| UseCase | 文件 | 作用 |
|---------|------|------|
| `GetLogisticsByVcUseCase` | LogisticsUseCases.kt | 按 VC 查询物流 |
| `CreateLogisticsUseCase` | LogisticsUseCases.kt | 创建物流计划 |
| `ConfirmInboundUseCase` | LogisticsUseCases.kt | **核心**：入库确认，触发三联动 |
| `UpdateLogisticsStatusUseCase` | LogisticsUseCases.kt | 更新物流主单状态 |
| `UpdateExpressOrderUseCase` | LogisticsUseCases.kt | 更新快递单信息 |
| `UpdateExpressOrderStatusUseCase` | LogisticsUseCases.kt | 推进快递单状态 |

## 入库确认核心流程（ConfirmInboundUseCase）

```kotlin
ConfirmInboundUseCase {
    // 1. 设备采购：SN 冲突校验
    inventoryUseCase.createEquipmentInventory(...)

    // 2. 按 VC 类型处理库存变动
    //  - 物料采购：更新 MaterialInventory（累加）
    //  - 物料供应：扣减 MaterialInventory
    //  - 退货：退货入库 + 触发原 VC 押金重算

    // 3. 推进物流状态
    logisticsUseCase.updateStatus(...)

    // 4. 推进 VC subjectStatus
    virtualContractStateMachineUseCase.onLogisticsStatusChanged(...)

    // 5. 触发财务记账
    processLogisticsFinanceUseCase.process(...)

    // 6. 手动更新 TimeRule（Android 无 listener）
    runTimeRuleEngineUseCase.updateRuleResult(...)
}
```

> ⚠️ Android 中无 `time_rule_completion_listener`，需在 `ConfirmInboundUseCase` 中手动调用 `runTimeRuleEngineUseCase` 更新规则触发时间

## 与其他模块的关系

- **→ VC**：通过 `virtualContractId` 关联，入库影响 VC 三状态机
- **→ ExpressOrder**：一个 Logistics 可包含多个 ExpressOrder
- **→ Inventory**：入库确认调用 `InventoryUseCase` 更新库存
- **→ Finance**：入库确认调用 `ProcessLogisticsFinanceUseCase` 生成记账凭证
- **→ TimeRule**：物流创建时同步父级（VC/Business/SupplyChain）规则

## Android 与 Desktop 的差异

| 差异 | Desktop | Android |
|------|---------|---------|
| 入库确认 | `confirm_inbound_action()` | `ConfirmInboundUseCase` |
| 状态联动 | `emit_event()` → `logistics_state_machine()` | UseCase 直接调用 |
| 规则触发监听 | `time_rule_completion_listener` | 需手动调用 |
| 快递单 items 格式 | JSON | JSON（结构一致） |

## 开发注意事项

- `ConfirmInboundUseCase` 是最关键 UseCase，涉及多个模块的联动
- `financeTriggered` 防重标志：财务只应被触发一次
- 退货物流的处理方向与正向采购相反（扣减库存 + 反向记账）
- Android 中时间字段全部为 `Long`（Unix ms）
