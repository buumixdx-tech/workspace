# Time Rules（时间规则引擎）

## 模块职责

时间规则引擎是系统的智能预警中枢，通过定义"触发事件 + 偏移量 → 标杆时间 → 目标事件"的关系，实现对业务履约时限的监控和告警。Android 实现与 Desktop 逻辑基本一致。

## 核心概念

| 概念 | 说明 |
|------|------|
| **触发事件（triggerEvent）** | 时间点标杆，如 `SUBJECT_SHIPPED`（发货完成） |
| **目标事件（targetEvent）** | 需要监控的事件，如 `SUBJECT_CASH_FINISH` |
| **偏移量（offset）** | 相对于触发事件的时间偏移 |
| **单位（unit）** | 偏移单位：自然日、工作日、小时 |
| **标杆时间（flagTime）** | `triggerEventTime + offset + unit` |
| **方向（direction）** | `before`（目标需在标杆时间之前）或 `after` |

**合规判断：**
- `direction=before`：`targetTime <= flagTime` 合规
- `direction=after`：`targetTime >= flagTime` 合规

## 三层继承体系

```
第一层：Business / SupplyChain（制定模板规则）
         │
         ▼ (inherit=1, NEAR)
第二层：VirtualContract（继承模板规则）
         │
         ▼ (inherit=1/2, NEAR/FAR)
第三层：Logistics（继承 VC / Business / SupplyChain 规则）
```

## 状态（TimeRuleEntity.status）

| 状态 | 说明 | 引擎处理 |
|------|------|---------|
| `失效` | 手动失效 | 跳过 |
| `生效` | 生效监控中 | 正常评估 |
| `有结果` | 目标事件已发生，触发事件未发生 | 继续监控 |
| `结束` | 目标和触发都发生 | 跳过 |

> Android 中无 `模板` 状态（Desktop 的 `TEMPLATE`），规则模板直接标记为 `生效` 并通过 `inherit` 字段区分

## 告警等级（warning）

| 等级 | 条件 |
|------|------|
| 绿色 | 距标杆时间 > 7 天 |
| 黄色 | 3-7 天 |
| 橙色 | 1-3 天 |
| 红色 | ≤ 0 天（超时） |

## 关键 UseCase

| UseCase | 文件 | 作用 |
|---------|------|------|
| `SaveTimeRuleUseCase` | TimeRuleUseCases.kt | 创建/更新时间规则 |
| `GetTimeRulesByRelatedUseCase` | TimeRuleUseCases.kt | 按关联对象查询规则 |
| `RunTimeRuleEngineUseCase` | rule_engine/ | **核心**：批量运行规则引擎 |
| `RuleEngine` | rule_engine/ | 规则引擎主体（与 Desktop engine.py 对应） |
| `RuleEvaluator` | rule_engine/ | 规则评估器（与 Desktop evaluator.py 对应） |

## RuleEngine（规则引擎主体）

```kotlin
// domain/usecase/rule_engine/RuleEngine.kt
class RuleEngine {
    fun runAll(rules: List<TimeRuleEntity>): List<TimeRuleAlert>
    fun evaluate(rule: TimeRuleEntity, triggerTime: Long?, targetTime: Long?): TimeRuleAlert
}
```

## RuleEvaluator（规则评估器）

```kotlin
// domain/usecase/rule_engine/RuleEvaluator.kt
class RuleEvaluator {
    fun calculateFlagTime(triggerTime: Long, offset: Int, unit: String): Long
    fun evaluateCompliance(direction: String, targetTime: Long, flagTime: Long): Boolean
    fun determineWarningLevel(remainingDays: Long): String
}
```

## flagTime 计算（与 Desktop 一致）

```
flagTime = triggerEventTime + offset + unit
```

## Android 与 Desktop 的关键差异

| 差异 | Desktop | Android |
|------|---------|---------|
| 规则触发完成监听 | `time_rule_completion_listener`（事件驱动） | 需在 `ConfirmInboundUseCase` 中**手动调用** |
| 规则引擎运行 | 定时扫描（系统启动/每日） | `RunTimeRuleEngineUseCase`（按需调用） |
| 模板规则状态 | `TEMPLATE`（引擎跳过） | 无独立状态，通过 `inherit` 区分 |
| 规则生成 | `RuleManager.generate_rules_from_payment_terms()` | 对应 UseCase（GenerateTimeRulesFromPaymentTermsUseCase） |

## Android 规则触发更新的调用链

Desktop 中 `time_rule_completion_listener` 自动响应 `LOGISTICS_STATUS_CHANGED` 事件。Android 中需要手动触发：

```kotlin
// ConfirmInboundUseCase 中（伪代码）
suspend fun confirmInbound(...) {
    // ... 库存处理 ...
    // ... 状态机推进 ...

    // 手动更新 TimeRule 触发时间
    runTimeRuleEngineUseCase.updateRuleResult(
        relatedId = logisticsId,
        relatedType = "物流",
        triggerEvent = "物流完成",
        triggerTime = System.currentTimeMillis()
    )
}
```

## 开发注意事项

- Android 无事件总线，`ConfirmInboundUseCase` 完成后需手动调用 `RunTimeRuleEngineUseCase` 更新规则
- `flagTime` 和时间戳全部为 `Long`（Unix ms）
- `inherit` 字段：0=自身定制，1=近继承，2=远继承
