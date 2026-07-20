# Deposit（押金模块）

## 模块职责

管理设备采购业务中的押金应收/实收动态核算，按 SKU 约定押金比例将实收押金分摊到每台设备。

> ⚠️ Android 中押金逻辑**内嵌于 `VirtualContractStateMachineUseCase`**，不单独拆分为模块（Desktop 中 `logic/deposit.py` 是独立文件）。

## 核心概念

| 指标 | 说明 |
|------|------|
| **应收押金** | 运营中设备数量 × 约定单台押金（或合同计划量） |
| **实收押金** | CashFlow 中 `押金` 类型之和 − `退还押金` |

## 押金重算触发入口

```kotlin
// VirtualContractStateMachineUseCase.kt
suspend fun onCashFlowChanged(vcId: Long) {
    // 1. 计算当前 VC 的应付/实收押金
    // 2. 分摊比例 = 实收 / 应收
    // 3. 更新每台设备的 depositAmount
}
```

## 约定单台押金的来源

约定单台押金从以下优先级获取：
1. `Business.details.pricing[skuName].deposit`（客户协议）
2. `SupplyChain.pricingConfig` 中的默认值

## 分摊比例计算

```
分摊比例 = 实收押金总额 / 应收押金总额
每台设备应退押金 = 设备约定押金 × 分摊比例
```

> 分摊比例可能 > 1（客户多付）或 < 1（少付）

## 退货 VC 的押金处理

```kotlin
// 退货 VC.subjectStatus = COMPLETED 时触发
onReturnVcCompleted(returnVcId) {
    // 1. 找到原合同（relatedVcId）
    // 2. 重新核算原合同的应收/实收押金
    // 3. 更新原合同关联的所有 EquipmentInventory.depositAmount
    // 4. 判断原 VC 是否应自动完结（押金未付足且无退款）
}
```

## 关键 UseCase

| UseCase | 文件 | 作用 |
|---------|------|------|
| `VirtualContractStateMachineUseCase` | VirtualContractStateMachineUseCase.kt | 押金重算逻辑内嵌于 `onCashFlowChanged()` |

## Android 与 Desktop 的关键差异

| 差异 | Desktop | Android |
|------|---------|---------|
| 押金模块 | 独立 `logic/deposit.py` | **内嵌**于 `VirtualContractStateMachineUseCase` |
| 押金重算入口 | `deposit_module(vc_id/cf_id)` | `onCashFlowChanged(vcId)` |
| 退货押金处理 | `process_cf_deposit(session, cf_id)` | 在 `onCashFlowChanged` 中统一处理 |
| 自动完结判断 | 独立逻辑 | 内嵌于状态机判断 |

## deposit_info JSON 结构

与 Desktop 一致：

```json
{
  "shouldReceive": 0.0,
  "totalDeposit": 0.0
}
```

## 开发注意事项

- Android 中所有押金相关逻辑集中在 `VirtualContractStateMachineUseCase`，修改时需注意副作用
- 应收押金是动态的（基于运营中设备数量），每次设备状态变更或资金流录入都应重算
- 退货 VC 的押金退还流水会触发原合同的押金重算
