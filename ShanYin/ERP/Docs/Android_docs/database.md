# Android Room 数据库详细说明

Room 数据库文件：Android 内部 SQLite（`AppDatabase.kt` 配置路径）

---

## 与 Desktop 数据库的对照说明

- **Desktop** 使用 SQLAlchemy ORM（`models.py`），表结构和 Python 对象模型共存
- **Android** 使用 Room（`entity/` 下 23 个 Entity 类），表定义与 DAO 接口分离
- 两者表名完全一致，字段名通过 `@ColumnInfo(name = "...")` 映射
- JSON 字段在 Android 中存储为 `String?`（JSON 字符串），需序列化/反序列化

---

## 数据类型对照

| SQLAlchemy (Desktop) | Room (Android) | 说明 |
|---------------------|----------------|------|
| `INTEGER` | `Long` / `Int` | 主键/外键 |
| `VARCHAR(n)` | `String` | 字符串 |
| `TEXT` | `String` | 长文本 |
| `JSON` | `String?` | JSON 字符串，需 Gson 解析 |
| `DATETIME` | `Long` | Unix timestamp（毫秒） |
| `BOOLEAN` | `Boolean` | 布尔值 |
| `FLOAT` | `Double` | 浮点数 |

> ⚠️ Android 的时间字段（`timestamp`、`transaction_date` 等）全部使用 `Long`（Unix ms），而 Desktop 使用 `DATETIME`。转换时注意时区处理。

---

## 1. 主数据表（Master Data）

### 1.1 channel_customers（渠道客户）

```kotlin
@Entity(tableName = "channel_customers")
data class ChannelCustomerEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val info: String?,        // Text，整体信息备注
    val createdAt: Long = System.currentTimeMillis()
)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `name` | String | 客户名称 |
| `info` | String? | 整体信息备注 |
| `createdAt` | Long | 创建时间（Unix ms） |

---

### 1.2 suppliers（供应商）

```kotlin
@Entity(tableName = "suppliers")
data class SupplierEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val category: String?,    // 设备/物料/兼备
    val address: String?,
    val qualifications: String?,
    val info: String?         // JSON
)
```

---

### 1.3 skus（SKU 存货）

```kotlin
@Entity(tableName = "skus",
    foreignKeys = [ForeignKey(..., parentColumns = ["id"], childColumns = ["supplier_id"])])
data class SkuEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val supplierId: Long?,
    val name: String,
    val typeLevel1: String?, // 设备/物料
    val typeLevel2: String?, // 子类别
    val model: String?,
    val description: String?,
    val certification: String?,
    val params: String?       // JSON
)
```

---

### 1.4 points（点位）

```kotlin
@Entity(
    tableName = "points",
    foreignKeys = [
        ForeignKey(..., parentColumns = ["id"], childColumns = ["customer_id"]),
        ForeignKey(..., parentColumns = ["id"], childColumns = ["supplier_id"])
    ],
    indices = [Index("customer_id"), Index("supplier_id")]
)
data class PointEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val customerId: Long?,
    val supplierId: Long?,
    val name: String,
    val address: String?,
    val type: String?,        // 运营点位/客户仓/自有仓/供应商仓/转运仓
    val receivingAddress: String?
)
```

---

### 1.5 external_partners（外部合作伙伴）

```kotlin
@Entity(tableName = "external_partners")
data class ExternalPartnerEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val type: String?,        // 外包服务商/客户关联方/供应商关联方/其他
    val name: String,
    val address: String?,
    val content: String?
)
```

---

### 1.6 bank_accounts（银行账户）

```kotlin
@Entity(
    tableName = "bank_accounts",
    foreignKeys = [ForeignKey(..., parentColumns = ["id"], childColumns = ["owner_id"])]
)
data class BankAccountEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val ownerType: String?,   // ourselves/customer/supplier/other
    val ownerId: Long?,
    val accountInfo: String?, // JSON: 开户名称/银行名称/银行账号/账户类型
    val isDefault: Boolean = false
)
```

**`account_info` JSON 结构：**

```json
{
  "开户名称": "天津集利嘉和智能科技有限公司北京分公司",
  "银行名称": "招商银行北京万通中心支行",
  "银行账号": "110945287710802",
  "账户类型": "对公"
}
```

---

## 2. 业务表（Business）

### 2.1 contracts（合同）

```kotlin
@Entity(tableName = "contracts")
data class ContractEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val contractNumber: String?,  // 唯一
    val type: String?,
    val status: String?,          // 签约完成/生效/过期/终止
    val parties: String?,         // JSON
    val content: String?,         // JSON
    val signedDate: Long?,
    val effectiveDate: Long?,
    val expiryDate: Long?,
    val timestamp: Long = System.currentTimeMillis()
)
```

---

### 2.2 business（业务项目）

```kotlin
@Entity(
    tableName = "business",
    foreignKeys = [
        ForeignKey(..., parentColumns = ["id"], childColumns = ["customer_id"]),
        ForeignKey(..., parentColumns = ["id"], childColumns = ["contract_id"])
    ],
    indices = [Index("customer_id"), Index("contract_id")]
)
data class BusinessEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val customerId: Long?,
    val contractId: Long?,
    val status: String?,         // 前期接洽/业务评估/客户反馈/合作落地/业务开展/业务暂缓/业务终止
    val timestamp: Long = System.currentTimeMillis(),
    val details: String?          // JSON: history/pricing/payment_terms
)
```

**`details` JSON 结构（与 Desktop 完全一致）：**

```json
{
  "history": [
    {"from": null, "to": "前期接洽", "time": 1741658556608, "comment": "初始化创建"}
  ],
  "pricing": {
    "冰激凌机-湖北广腊-单头双冷": {"price": 31.0, "deposit": 0}
  },
  "payment_terms": {
    "prepayment_ratio": 0.0,
    "balance_period": 45,
    "day_rule": "自然日",
    "start_trigger": "入库日"
  },
  "contract_id": 10
}
```

> ⚠️ `details.history[].time` 在 Desktop 是 ISO 字符串，在 Android 是 `Long`（Unix ms）

---

## 3. 供应链表（Supply Chain）

### 3.1 supply_chains（供应链协议）

```kotlin
@Entity(
    tableName = "supply_chains",
    foreignKeys = [
        ForeignKey(..., parentColumns = ["id"], childColumns = ["supplier_id"]),
        ForeignKey(..., parentColumns = ["id"], childColumns = ["contract_id"])
    ],
    indices = [Index("supplier_id"), Index("contract_id")]
)
data class SupplyChainEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val supplierId: Long,
    val supplierName: String,
    val type: String?,           // 物料 or 设备
    val contractId: Long?,
    val pricingConfig: String?,  // JSON: SKU名称→单价
    val paymentTerms: String?    // JSON: prepayment_ratio/balance_period/day_rule/start_trigger
)
```

---

### 3.2 supply_chain_items（供应链明细项）

```kotlin
@Entity(
    tableName = "supply_chain_items",
    foreignKeys = [
        ForeignKey(..., parentColumns = ["id"], childColumns = ["supply_chain_id"]),
        ForeignKey(..., parentColumns = ["id"], childColumns = ["sku_id"])
    ]
)
data class SupplyChainItemEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val supplyChainId: Long,
    val skuId: Long,
    val price: Double,
    val isFloating: Boolean
)
```

---

## 4. 虚拟合同表（Virtual Contract）

### 4.1 virtual_contracts（虚拟合同）

```kotlin
@Entity(
    tableName = "virtual_contracts",
    foreignKeys = [
        ForeignKey(..., parentColumns = ["id"], childColumns = ["business_id"]),
        ForeignKey(..., parentColumns = ["id"], childColumns = ["supply_chain_id"])
    ],
    indices = [
        Index("business_id"),
        Index("status"),
        Index("type"),
        Index("supply_chain_id"),
        Index("business_id", "status")
    ]
)
data class VirtualContractEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val description: String?,
    val businessId: Long?,
    val supplyChainId: Long?,
    val relatedVcId: Long?,     // 退货 VC 关联原 VC
    val type: String?,          // 设备采购/物料供应/物料采购/退货
    val summary: String?,
    val elements: String?,       // JSON: 合同标的明细
    val depositInfo: String?,    // JSON: 应收/实收押金
    val status: String?,         // 执行/完成/终止
    val subjectStatus: String?,  // 执行/发货/签收/完成
    val cashStatus: String?,     // 执行/预付/完成
    val statusTimestamp: Long?,
    val subjectStatusTimestamp: Long?,
    val cashStatusTimestamp: Long?,
    val returnDirection: String? // 退货方向
)
```

### 4.2 VC.elements JSON 结构

与 Desktop 完全一致，参见 [Desktop database.md](https://github.com/.../database.md)（VC.elements 章节）。

### 4.3 VC.deposit_info JSON 结构

```json
{
  "shouldReceive": 0.0,
  "totalDeposit": 0.0
}
```

---

### 4.4 vc_status_logs（VC 状态变更日志）

```kotlin
@Entity(
    tableName = "vc_status_logs",
    foreignKeys = [ForeignKey(..., parentColumns = ["id"], childColumns = ["vc_id"])]
)
data class VirtualContractStatusLogEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val vcId: Long,
    val category: String?,   // status/subjectStatus/cashStatus
    val statusName: String?,
    val timestamp: Long
)
```

---

### 4.5 vc_history（VC 变更历史）

```kotlin
@Entity(
    tableName = "vc_history",
    foreignKeys = [ForeignKey(..., parentColumns = ["id"], childColumns = ["vc_id"])]
)
data class VirtualContractHistoryEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val vcId: Long,
    val originalData: String?, // JSON: 变更前完整快照
    val changeDate: Long,
    val changeReason: String?
)
```

---

## 5. 库存表（Inventory）

### 5.1 equipment_inventory（设备库存）

```kotlin
@Entity(
    tableName = "equipment_inventory",
    foreignKeys = [
        ForeignKey(..., parentColumns = ["id"], childColumns = ["sku_id"]),
        ForeignKey(..., parentColumns = ["id"], childColumns = ["virtual_contract_id"]),
        ForeignKey(..., parentColumns = ["id"], childColumns = ["point_id"])
    ],
    indices = [
        Index("virtual_contract_id"),
        Index("point_id"),
        Index("operational_status"),
        Index("sku_id")
    ]
)
data class EquipmentInventoryEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val skuId: Long?,
    val sn: String?,              // 设备序列号（唯一）
    val operationalStatus: String?, // 库存/运营/处置
    val deviceStatus: String?,     // 正常/维修/损坏/故障/维护/锁机
    val virtualContractId: Long?,
    val pointId: Long?,
    val depositAmount: Double = 0.0,
    val depositTimestamp: Long?
)
```

---

### 5.2 material_inventory（物料库存）

```kotlin
@Entity(
    tableName = "material_inventory",
    foreignKeys = [ForeignKey(..., parentColumns = ["id"], childColumns = ["sku_id"])],
    indices = [Index("sku_id", unique = true)]
)
data class MaterialInventoryEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val skuId: Long,
    val stockDistribution: String?, // JSON: {"仓库名称": 数量}
    val averagePrice: Double = 0.0,
    val totalBalance: Double = 0.0
)
```

> ⚠️ `stock_distribution` key 是**仓库名称**（字符串），非 ID。与 Desktop 一致。

---

## 6. 物流表（Logistics）

### 6.1 logistics（物流主单）

```kotlin
@Entity(
    tableName = "logistics",
    foreignKeys = [ForeignKey(..., parentColumns = ["id"], childColumns = ["virtual_contract_id"])],
    indices = [Index("virtual_contract_id")]
)
data class LogisticsEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val virtualContractId: Long,
    val financeTriggered: Boolean = false,
    val status: String?,  // 待发货/在途/签收/完成/终止
    val timestamp: Long = System.currentTimeMillis()
)
```

---

### 6.2 express_orders（快递单）

```kotlin
@Entity(
    tableName = "express_orders",
    foreignKeys = [ForeignKey(..., parentColumns = ["id"], childColumns = ["logistics_id"])],
    indices = [Index("logistics_id")]
)
data class ExpressOrderEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val logisticsId: Long,
    val trackingNumber: String?,
    val items: String?,       // JSON: 货品明细
    val addressInfo: String?, // JSON: 地址信息
    val status: String?,
    val timestamp: Long = System.currentTimeMillis()
)
```

**`items` JSON 结构：**

```json
[
  {
    "skuId": 2,
    "skuName": "原味豆花-朝日",
    "pointId": null,
    "pointName": "朝日饲料仓 (供应商仓)",
    "qty": 500.0,
    "price": 6.5,
    "deposit": 0.0,
    "sn": "-"
  }
]
```

---

## 7. 财务表（Finance）

### 7.1 finance_accounts（会计科目）

```kotlin
@Entity(tableName = "finance_accounts")
data class FinanceAccountEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val category: String?,     // 资产/负债/损益/所有者权益
    val level1Name: String?,   // 一级科目名称
    val level2Name: String?,   // 二级科目（对手方明细）
    val counterpartType: String?,
    val counterpartId: Long?,
    val direction: String?     // Debit/Credit
)
```

---

### 7.2 financial_journal（复式记账凭证）

```kotlin
@Entity(
    tableName = "financial_journal",
    foreignKeys = [
        ForeignKey(..., parentColumns = ["id"], childColumns = ["account_id"]),
        ForeignKey(..., parentColumns = ["id"], childColumns = ["ref_vc_id"])
    ],
    indices = [Index("account_id"), Index("ref_vc_id")]
)
data class FinancialJournalEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val voucherNo: String?,  // TRF-xxx / EXT-IN-xxx / EXT-OUT-xxx
    val accountId: Long?,
    val debit: Double,
    val credit: Double,
    val summary: String?,
    val refType: String?,   // VC/Logistics/CashFlow
    val refId: Long?,
    val refVcId: Long?,
    val transactionDate: Long?
)
```

---

### 7.3 cash_flows（资金流水）

```kotlin
@Entity(
    tableName = "cash_flows",
    foreignKeys = [
        ForeignKey(..., parentColumns = ["id"], childColumns = ["virtual_contract_id"]),
        ForeignKey(..., parentColumns = ["id"], childColumns = ["payer_account_id"]),
        ForeignKey(..., parentColumns = ["id"], childColumns = ["payee_account_id"])
    ],
    indices = [
        Index("virtual_contract_id"),
        Index("type"),
        Index("transaction_date"),
        Index("virtual_contract_id", "type"),
        Index("payer_account_id"),
        Index("payee_account_id")
    ]
)
data class CashFlowEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val virtualContractId: Long?,
    val type: String?,          // 预付/履约/押金/退还押金/退款/冲抵入金/冲抵支付/罚金
    val amount: Double = 0.0,
    val payerAccountId: Long?,
    val payerAccountName: String?,
    val payeeAccountId: Long?,
    val payeeAccountName: String?,
    val financeTriggered: Boolean = false,
    val paymentInfo: String?,    // JSON
    val voucherPath: String?,
    val description: String?,
    val transactionDate: Long?,
    val timestamp: Long = System.currentTimeMillis()
)
```

---

### 7.4 cash_flow_ledger（现金流台账）

```kotlin
@Entity(
    tableName = "cash_flow_ledger",
    foreignKeys = [ForeignKey(..., parentColumns = ["id"], childColumns = ["journal_id"])]
)
data class CashFlowLedgerEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val journalId: Long?,
    val mainCategory: String?,
    val direction: String?,  // Debit/Credit
    val amount: Double
)
```

---

## 8. 时间规则表（Time Rules）

### 8.1 time_rules（时间规则）

```kotlin
@Entity(tableName = "time_rules")
data class TimeRuleEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val relatedId: Long,
    val relatedType: String?, // 业务/供应链/虚拟合同/物流
    val inherit: Int = 0,      // 0=自身定制, 1=近继承, 2=远继承
    val party: String?,       // 规则责任方

    // 触发事件
    val triggerEvent: String?,
    val tgeParam1: String?,
    val tgeParam2: String?,
    val triggerTime: Long?,

    // 目标事件
    val targetEvent: String,
    val taeParam1: String?,
    val taeParam2: String?,
    val targetTime: Long?,

    // 时间约束
    val offset: Int?,
    val unit: String?,        // 自然日/工作日/小时
    val flagTime: Long?,     // 标杆时间
    val direction: String?,   // before/after

    // 监控与结果
    val warning: String?,    // 绿色/黄色/橙色/红色
    val result: String?,     // 合规/违规
    val status: String = "生效", // 失效/生效/有结果/结束

    // 时间戳
    val timestamp: Long = System.currentTimeMillis(),
    val resultstamp: Long?,
    val endstamp: Long?
)
```

> 与 Desktop 的 `time_rules` 表结构完全一致

---

## 9. 事件表（System Events）

### 9.1 system_events（领域事件持久化）

```kotlin
@Entity(tableName = "system_events")
data class SystemEventEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val eventType: String?,
    val aggregateType: String?,
    val aggregateId: Long?,
    val payload: String?,      // JSON
    val createdAt: Long = System.currentTimeMillis(),
    val pushedToAi: Boolean = false
)
```

> ⚠️ Android 中 `system_events` 表存在，但 **无事件分发机制**（`domain/event/` 目录为空），Android 不使用 Desktop 的 `emit_event()` → `dispatch()` → `listener` 事件总线模式。

---

## 10. DAO 接口一览

| DAO | 对应 Entity | 主要方法 |
|-----|------------|---------|
| `ChannelCustomerDao` | ChannelCustomerEntity | getAll, getById, insert, update, delete |
| `BusinessDao` | BusinessEntity | getAll, getByCustomerId, getByStatus, insert, update |
| `VirtualContractDao` | VirtualContractEntity | getAll, getByBusinessId, getByStatus, getByType, insert, update |
| `SupplyChainDao` | SupplyChainEntity | getAll, getBySupplierId, getByContractId, insert, update |
| `LogisticsDao` | LogisticsEntity | getByVcId, update, insert |
| `ExpressOrderDao` | ExpressOrderEntity | getByLogisticsId, update, insert |
| `CashFlowDao` | CashFlowEntity | getByVcId, getByType, insert, update |
| `FinanceAccountDao` | FinanceAccountEntity | getAll, getByType, insert |
| `FinancialJournalDao` | FinancialJournalEntity | getByAccountId, getByVcId, insert |
| `EquipmentInventoryDao` | EquipmentInventoryEntity | getByVcId, getBySn, getByPoint, insert, update |
| `MaterialInventoryDao` | MaterialInventoryEntity | getBySkuId, insert, update |
| `TimeRuleDao` | TimeRuleEntity | getByRelated, getByStatus, update, insert |
| `SystemEventDao` | SystemEventEntity | insert, getByType, getByAggregate |

---

## 11. 表关系总图

```
channel_customers (1)───(N) business
                          │
                          └───(N) virtual_contracts (1)───(N) logistics (1)───(N) express_orders
                                  │                           │
                                  │                           ├── finance_triggered
                                  │                           └── status
                                  │
                                  ├──(N) equipment_inventory
                                  ├──(N) material_inventory
                                  ├──(N) cash_flows
                                  ├──(N) time_rules
                                  └──(N) vc_status_logs

suppliers (1)───(N) supply_chains (1)───(N) supply_chain_items
        │              │
        │              └───(N) virtual_contracts
        │
        └───(N) points (1)───(N) equipment_inventory

skus (1)───(N) supply_chain_items
    │
    ├──(N) equipment_inventory
    └──(N) material_inventory

contracts (1)───(N) business
           └───(N) supply_chains

bank_accounts (1)───(N) cash_flows (payer/payee)

external_partners ──(独立)───(N) bank_accounts (owner)

finance_accounts (1)───(N) financial_journal
```

---

## 12. Android 与 Desktop 字段命名对照

| Desktop (snake_case) | Android (camelCase) | 备注 |
|---------------------|---------------------|------|
| `customer_id` | `customerId` | |
| `virtual_contract_id` | `virtualContractId` | |
| `supply_chain_id` | `supplyChainId` | |
| `related_vc_id` | `relatedVcId` | |
| `operational_status` | `operationalStatus` | |
| `device_status` | `deviceStatus` | |
| `deposit_amount` | `depositAmount` | |
| `deposit_timestamp` | `depositTimestamp` | |
| `stock_distribution` | `stockDistribution` | |
| `average_price` | `averagePrice` | |
| `total_balance` | `totalBalance` | |
| `finance_triggered` | `financeTriggered` | |
| `payer_account_id` | `payerAccountId` | |
| `payee_account_id` | `payeeAccountId` | |
| `payer_account_name` | `payerAccountName` | 冗余字段，Desktop 无 |
| `payee_account_name` | `payeeAccountName` | 冗余字段，Desktop 无 |
