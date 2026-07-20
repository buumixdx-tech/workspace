# Events（领域事件系统）

## ⚠️ Android 无事件系统

Android 中 **`domain/event/` 目录为空**，**不存在** Desktop 那样的 `emit_event()` → `dispatch()` → `listener` 事件驱动机制。

这是 Android 与 Desktop 之间最核心的架构差异。

---

## Desktop 事件系统在 Android 中的替代方案

Desktop 中通过事件总线实现的模块间解耦联动，在 Android 中通过 **UseCase 直接调用** 实现。

### Desktop 事件驱动模式

```
Action 函数
  → emit_event() 写入 SystemEvent 表
  → dispatch() 查找所有匹配监听器
  → listener 执行副作用（更新 TimeRule、触发财务等）
```

### Android 替代模式

```
UseCase
  → 直接调用其他 UseCase（通过 Hilt 注入）
  → 手动触发相关状态更新
```

---

## Android 中的手动联动示例

### 1. 入库确认 → 三联动

```kotlin
// ConfirmInboundUseCase（伪代码）
class ConfirmInboundUseCase @Inject constructor(
    private val inventoryUseCase: CreateEquipmentInventoryUseCase,
    private val virtualContractStateMachine: VirtualContractStateMachineUseCase,
    private val processLogisticsFinanceUseCase: ProcessLogisticsFinanceUseCase,
    private val runTimeRuleEngineUseCase: RunTimeRuleEngineUseCase,
) {
    suspend operator fun invoke(logisticsId: Long) {
        // 1. 库存变动
        inventoryUseCase.createEquipmentInventory(...)

        // 2. VC 状态机推进
        virtualContractStateMachine.onLogisticsStatusChanged(vcId, status)

        // 3. 财务记账
        processLogisticsFinanceUseCase.process(...)

        // 4. 手动更新 TimeRule（Desktop 的 listener 在 Android 中需要手动调用）
        runTimeRuleEngineUseCase.updateRuleResult(...)
    }
}
```

### 2. 资金流录入 → 状态机 + 财务 + 押金

```kotlin
// CreateCashFlowUseCase（伪代码）
class CreateCashFlowUseCase @Inject constructor(
    private val virtualContractStateMachine: VirtualContractStateMachineUseCase,
    private val processCashFlowFinanceUseCase: ProcessCashFlowFinanceUseCase,
    private val applyOffsetUseCase: ApplyOffsetToVcUseCase,
) {
    suspend operator fun invoke(cashFlow: CashFlow) {
        // 1. 保存 CashFlow
        cashFlowRepository.insert(cashFlow)

        // 2. 超额拆分
        applyOffsetUseCase.apply(...)

        // 3. VC 状态机（含押金重算）
        virtualContractStateMachine.onCashFlowChanged(vcId)

        // 4. 财务记账
        processCashFlowFinanceUseCase.process(...)
    }
}
```

---

## SystemEventEntity 存在但无分发机制

Android 的 `SystemEventEntity` 表仍然存在（用于审计或回溯），但没有 Desktop 那样的分发监听机制：

```kotlin
@Entity(tableName = "system_events")
data class SystemEventEntity(
    val id: Long = 0,
    val eventType: String?,
    val aggregateType: String?,
    val aggregateId: Long?,
    val payload: String?,      // JSON
    val createdAt: Long,
    val pushedToAi: Boolean = false
)
```

在 Android 中，`SystemEventEntity` 仅作为事件日志记录，不触发任何监听器。

---

## Android 架构的优势与代价

### 优势

- **性能更好**：无事件分发开销，直接调用更高效
- **调试更容易**：调用链清晰，可直接追踪
- **编译时安全**：Hilt 注入的依赖在编译时校验

### 代价

- **模块耦合**：UseCase 之间通过接口耦合，不如事件总线解耦彻底
- **手动维护联动**：新增联动逻辑需要修改调用方代码
- **规则触发需手动处理**：Desktop 的 `time_rule_completion_listener` 在 Android 中需要每个触发点手动调用

---

## 开发注意事项

- Android 中新增跨模块联动逻辑时，需在发起操作的 UseCase 中直接调用相关 UseCase
- `domain/event/` 目录保留为空，不需要实现事件分发机制
- 如需事件日志，仅写入 `SystemEventEntity` 即可（无监听器）
