# Services（跨模块业务服务层）

## 模块职责

`services.md` 在 Android 中对应各 UseCase 中的**工具方法**和 **Repository 查询抽象**。Android 没有独立的 `services.py`，但相同类型的跨模块业务计算逻辑分散在各 UseCase 和 Repository 中。

## 主要跨模块计算逻辑

### 1. 对手方识别

对应 Desktop 的 `get_counterpart_info()`，Android 中在 `VirtualContractStateMachineUseCase` 或相关 UseCase 中实现：

```kotlin
// 穿透退货 VC 找原始对手方
fun getCounterpartInfo(vc: VirtualContract): Pair<String?, Long?> {
    val activeVc = if (vc.type == "退货" && vc.relatedVcId != null) {
        vcRepository.getById(vc.relatedVcId) ?: vc
    } else vc

    return when (activeVc.type) {
        "设备采购", "物料采购" -> "SUPPLIER" to activeVc.supplyChainId
        "物料供应" -> "CUSTOMER" to activeVc.businessId
        else -> null to null
    }
}
```

### 2. 资金流进度计算

对应 Desktop 的 `calculate_cashflow_progress()`，Android 中在 `VirtualContractUseCases.kt` 或独立 UseCase 中实现：

```kotlin
// 计算 VC 的资金流进度
fun calculateCashflowProgress(vcId: Long): CashflowProgress {
    // 1. 查询所有关联 CashFlow
    // 2. 按 type 分类求和（预付/履约/退款/冲抵）
    // 3. 计算总额、已付、余额、冲抵池
    // 4. 返回 progress 对象
}
```

### 3. 库存充足性校验

对应 Desktop 的 `validate_inventory_availability()`：

```kotlin
// ValidateInventoryAvailabilityUseCase（伪代码）
class ValidateInventoryAvailabilityUseCase @Inject constructor(
    private val materialInventoryRepository: MaterialInventoryRepository
) {
    suspend operator fun invoke(requestItems: List<SkuRequest>): ValidationResult {
        // 1. 汇总每个 SKU × 仓库的申请量
        // 2. 查询 MaterialInventory.stockDistribution
        // 3. 对比申请量和可用量
        // 4. 返回不足项列表
    }
}
```

### 4. 可退货明细计算

对应 Desktop 的 `get_returnable_items()`：

```kotlin
// GetReturnableItemsUseCase
class GetReturnableItemsUseCase @Inject constructor(
    private val vcRepository: VirtualContractRepository,
    private val equipmentInventoryRepository: EquipmentInventoryRepository,
    private val materialInventoryRepository: MaterialInventoryRepository,
) {
    suspend operator fun invoke(targetVcId: Long, returnDirection: String): List<ReturnableItem> {
        // 1. 获取原始 VC elements
        // 2. 搜集已发起退货单的锁定量
        // 3. 设备按 SN 锁定，物料按仓库分布扣减
        // 4. 返回剩余可退货明细
    }
}
```

### 5. 建议付款方/收款方

对应 Desktop 的 `get_suggested_cashflow_parties()`：

```kotlin
// GetSuggestedCashflowPartiesUseCase
class GetSuggestedCashflowPartiesUseCase @Inject constructor(
    private val vcRepository: VirtualContractRepository,
    private val businessRepository: BusinessRepository,
    private val supplyChainRepository: SupplyChainRepository,
) {
    suspend operator fun invoke(vcId: Long, cfType: String): CashflowParties {
        // 按 VC 类型 + 资金流类型判断付款方和收款方
        // 与 Desktop get_suggested_cashflow_parties() 逻辑一致
    }
}
```

### 6. 会计科目余额查询

对应 Desktop 的 `get_account_balance()`：

```kotlin
// GetAccountBalanceUseCase
class GetAccountBalanceUseCase @Inject constructor(
    private val financeAccountRepository: FinanceAccountRepository,
    private val financialJournalRepository: FinancialJournalRepository,
) {
    suspend operator fun invoke(level1Name: String, cpType: String?, cpId: Long?): Double {
        // 1. 查找或创建 Account
        // 2. 汇总 debit - credit
        // 3. 返回余额
    }
}
```

## Android 跨模块计算的架构特点

```
Desktop：
  services.py（纯计算函数）
    ↓ 调用（只读）
  models.py

Android：
  UseCase（业务逻辑）
    ↓ 调用
  Repository（数据访问抽象）
      ↓ 实现
  DAO（Room 数据访问）
```

## 与 Desktop services.py 的主要差异

| 差异 | Desktop | Android |
|------|---------|---------|
| 位置 | `logic/services.py`（独立文件） | 分散在各 UseCase 中 |
| 依赖注入 | 无 | Hilt 注入 |
| 时间戳 | `DATETIME`（ISO 字符串） | `Long`（Unix ms） |
| VC 对象访问 | 字典或 SQLAlchemy 对象 | Kotlin data class |

## 开发注意事项

- Android 的跨模块计算通过 Hilt 注入的 Repository 实现，无独立 services 层
- 时间戳全部为 `Long`（Unix ms），与 Desktop 的 ISO 字符串需相互转换时注意格式
- 穿透退货 VC 找原始对手方时，注意 `relatedVcId` 可能为 null
