# ShanYin ERP Android V2 移植规划

## 项目概述

**目标:** 将 desktop-version 100% 功能移植到 Android (shanyin-android-v2)
**源目录:** `d:/WorkSpace/ShanYin/ERP/desktop-version`
**目标目录:** `d:/WorkSpace/ShanYin/ERP/shanyin-android-v2`

---

## 一、技术栈决策

### 1.1 框架选型

| 层级 | 桌面版 | Android V2 | 说明 |
|------|--------|-------------|------|
| UI | Streamlit + AntD | Jetpack Compose + Material 3 | 等效组件库 |
| 状态管理 | Session State | ViewModel + StateFlow | 响应式状态 |
| 路由 | Streamlit Pages | Navigation Compose | 页面导航 |
| 本地数据库 | SQLite + SQLAlchemy | Room | Android 原生ORM |
| 网络层 | FastAPI + uvicorn | Retrofit + OkHttp | REST API 客户端 |
| 离线优先 | SQLite WAL | Room + DataStore | 本地优先架构 |
| 依赖注入 | - | Hilt | 编译时DI |
| 异步 | asyncio | Kotlin Coroutines + Flow | 响应式编程 |

### 1.2 项目结构

```
shanyin-android-v2/
├── app/
│   └── src/main/
│       ├── java/com/shanyin/erp/
│       │   ├── data/
│       │   │   ├── local/          # Room 数据库
│       │   │   │   ├── dao/        # Data Access Objects
│       │   │   │   ├── entity/     # 数据库实体
│       │   │   │   ├── converters/ # 类型转换器
│       │   │   │   └── AppDatabase.kt
│       │   │   ├── remote/         # Retrofit API
│       │   │   ├── repository/    # Repository 实现
│       │   │   └── mapper/        # DTO <-> Entity 映射
│       │   ├── domain/
│       │   │   ├── model/         # 领域模型
│       │   │   ├── repository/    # Repository 接口
│       │   │   ├── usecase/       # 用例
│       │   │   └── event/         # 领域事件
│       │   ├── di/               # Hilt 模块
│       │   └── ui/
│       │       ├── theme/        # Material 3 主题
│       │       ├── components/   # 通用组件
│       │       ├── navigation/  # 导航
│       │       └── screens/     # 页面
│       │           ├── dashboard/
│       │           ├── business/
│       │           ├── vc/
│       │           ├── supplychain/
│       │           ├── inventory/
│       │           ├── logistics/
│       │           ├── finance/
│       │           ├── masterdata/
│       │           └── timerules/
│       └── res/
├── build.gradle.kts
└── settings.gradle.kts
```

---

## 二、数据库设计 (Room Schema)

### 2.1 实体映射表 (22 表 -> 22 Entity)

| # | Desktop Table | Android Entity | 类型 |
|---|---------------|-----------------|------|
| 1 | `channel_customers` | `ChannelCustomerEntity` | ✅ |
| 2 | `points` | `PointEntity` | ✅ |
| 3 | `suppliers` | `SupplierEntity` | ✅ |
| 4 | `skus` | `SkuEntity` | ✅ |
| 5 | `equipment_inventory` | `EquipmentInventoryEntity` | ✅ |
| 6 | `material_inventory` | `MaterialInventoryEntity` | ✅ |
| 7 | `contracts` | `ContractEntity` | ✅ |
| 8 | `virtual_contracts` | `VirtualContractEntity` | ✅ |
| 9 | `vc_history` | `VcHistoryEntity` | ✅ |
| 10 | `external_partners` | `ExternalPartnerEntity` | ✅ |
| 11 | `bank_accounts` | `BankAccountEntity` | ✅ |
| 12 | `business` | `BusinessEntity` | ✅ |
| 13 | `supply_chains` | `SupplyChainEntity` | ✅ |
| 14 | `supply_chain_items` | `SupplyChainItemEntity` | ✅ |
| 15 | `logistics` | `LogisticsEntity` | ✅ |
| 16 | `express_orders` | `ExpressOrderEntity` | ✅ |
| 17 | `cash_flows` | `CashFlowEntity` | ✅ |
| 18 | `vc_status_logs` | `VcStatusLogEntity` | ✅ |
| 19 | `finance_accounts` | `FinanceAccountEntity` | ✅ |
| 20 | `financial_journal` | `FinancialJournalEntity` | ✅ |
| 21 | `cash_flow_ledger` | `CashFlowLedgerEntity` | ✅ |
| 22 | `system_events` | `SystemEventEntity` | ✅ |
| 23 | `time_rules` | `TimeRuleEntity` | ✅ |

---

## 三、功能模块分解

### Phase 1: 基础设施 (第1-2周)

| 模块 | 功能点 | 状态 |
|------|--------|------|
| 项目初始化 | Gradle 配置, Hilt, Navigation | ⬜ |
| Room 数据库 | Entity, DAO, Database, Migration | ⬜ |
| Repository 架构 | 本地优先数据层 | ⬜ |
| 主题系统 | Material 3 深色/浅色主题 | ⬜ |
| 通用组件 | Card, Dialog, Form, Table | ⬜ |

### Phase 2: 主数据管理 (第3周)

| 功能 | Desktop 等效 | Android 实现 |
|------|--------------|--------------|
| 客户管理 | `ui/entry.py` | `ChannelCustomerScreen` |
| 地点管理 | `ui/entry.py` | `PointScreen` |
| 供应商管理 | `ui/entry.py` | `SupplierScreen` |
| SKU管理 | `ui/entry.py` | `SkuScreen` |
| 合作伙伴 | `ui/entry.py` | `PartnerScreen` |
| 银行账户 | `ui/entry.py` | `BankAccountScreen` |
| Excel导入导出 | `logic/master/` | `MasterDataUseCase` |

### Phase 3: 业务管理 (第4周)

| 功能 | Desktop 等效 | Android 实现 |
|------|--------------|--------------|
| 业务列表 | `ui/operations.py` | `BusinessListScreen` |
| 业务创建 | `ui/operations.py` | `BusinessFormDialog` |
| 阶段流转 | `ui/operations.py` | `BusinessStageTransition` |
| 业务详情 | `ui/operations.py` | `BusinessDetailScreen` |

**业务阶段:** `前期接洽 -> 业务评估 -> 客户反馈 -> 合作落地 -> 业务开展 -> 业务暂缓/完成/终止`

### Phase 4: 虚拟合同 (第5周)

| VC类型 | Desktop 等效 | Android 实现 |
|--------|--------------|--------------|
| 设备采购(客户) | `logic/vc/procurement.py` | `EquipmentProcurementScreen` |
| 设备采购(库存) | `logic/vc/procurement.py` | `EquipmentStockScreen` |
| 物料采购 | `logic/vc/supply.py` | `MaterialProcurementScreen` |
| 物料供应 | `logic/vc/supply.py` | `MaterialSupplyScreen` |
| 库存拨付 | `logic/vc/allocation.py` | `AllocationScreen` |
| 退货 | `logic/vc/return.py` | `ReturnScreen` |
| 状态跟踪 | `logic/state_machine.py` | `VcStatusTracker` |

**VC状态:**
- 主状态: `执行 / 完成 / 终止`
- 标的物状态: `执行 / 发货 / 签收 / 完成`
- 资金状态: `执行 / 预付 / 完成`

### Phase 5: 供应链 (第6周)

| 功能 | Desktop 等效 | Android 实现 |
|------|--------------|--------------|
| 供应链列表 | `ui/operations.py` | `SupplyChainListScreen` |
| 协议创建 | `logic/supply_chain/` | `SupplyChainFormDialog` |
| 价格配置 | `logic/supply_chain/` | `PricingConfigScreen` |
| 供应商定价 | `logic/supply_chain/` | `SupplierPricingScreen` |

### Phase 6: 仓储管理 (第7周)

| 功能 | Desktop 等效 | Android 实现 |
|------|--------------|--------------|
| 设备库存 | `logic/inventory.py` | `EquipmentInventoryScreen` |
| 设备SN管理 | `logic/inventory.py` | `EquipmentSnManager` |
| 物料库存 | `logic/inventory.py` | `MaterialInventoryScreen` |
| 库存分布 | `logic/inventory.py` | `InventoryDistributionScreen` |
| 状态管理 | `logic/inventory.py` | `DeviceStatusManager` |

**设备状态:** `库存 / 运营 / 处置`
**库存验证:** 供应时检查库存是否充足

### Phase 7: 物流管理 (第8周)

| 功能 | Desktop 等效 | Android 实现 |
|------|--------------|--------------|
| 发货计划 | `logic/logistics/` | `ShipmentPlanScreen` |
| 快递单管理 | `logic/logistics/` | `ExpressOrderScreen` |
| 入库确认 | `logic/logistics/` | `InboundConfirmScreen` |
| SN验证 | `logic/logistics/` | `SnVerification` |
| 状态流转 | `logic/state_machine.py` | `LogisticsStatusTracker` |

**物流状态:** `待发货 / 已发货 / 运输中 / 已签收 / 完成`

### Phase 8: 财务管理 (第9-10周)

| 功能 | Desktop 等效 | Android 实现 |
|------|--------------|--------------|
| 账户管理 | `ui/finance_admin.py` | `FinanceAccountScreen` |
| 资金流水 | `logic/finance/` | `CashFlowScreen` |
| 预付/履约/押金 | `logic/finance/` | `CashFlowTypeHandler` |
| 内部转账 | `logic/finance/` | `InternalTransferDialog` |
| 自动凭证 | `logic/finance/voucher.py` | `VoucherGenerator` |
| 日记账 | `logic/finance/journal.py` | `FinancialJournalScreen` |
| 月报生成 | `logic/finance/report.py` | `MonthlyReportScreen` |
| 银行存款 | `ui/dashboard.py` | `BankBalanceCard` |

**复式记账:** 16个一级科目
**凭证类型:** 收款/付款/转账/应收/应付

### Phase 9: 规则引擎 (第11周)

| 功能 | Desktop 等效 | Android 实现 |
|------|--------------|--------------|
| 规则创建 | `ui/rule_components.py` | `TimeRuleFormDialog` |
| 规则继承 | `logic/time_rules/` | `RuleInheritanceSystem` |
| 事件触发 | `logic/events/` | `EventTriggerSystem` |
| 偏移计算 | `logic/offset_manager.py` | `OffsetCalculator` |
| 预警显示 | `logic/time_rules/` | `WarningLevelIndicator` |

**预警等级:** `绿色 / 黄色 / 橙色 / 红色`
**偏移类型:** 自然日 / 工作日 / 小时

### Phase 10: 仪表盘 (第12周)

| 功能 | Desktop 等效 | Android 实现 |
|------|--------------|--------------|
| KPI卡片 | `ui/dashboard.py` | `KpiCards` |
| 银行余额 | `ui/dashboard.py` | `BankBalanceRow` |
| 应收应付 | `ui/dashboard.py` | `ArApSummary` |
| 月度报表 | `ui/dashboard.py` | `MonthlyReportCard` |
| 快捷操作 | `ui/dashboard.py` | `QuickActionsGrid` |

---

## 四、UI/UX 对照表

### 4.1 导航结构

| Desktop Streamlit | Android Compose |
|-------------------|-----------------|
| Sidebar 导航 | BottomNavigation + Drawer |
| Streamlit Pages | Navigation Compose |
| `st.page_link` | `NavHost` + `composable` |
| antd menu | `NavigationDrawer` |

### 4.2 核心组件映射

| Desktop 组件 | Android Compose |
|--------------|-----------------|
| `st.title` / `st.header` | `Text.h1/h2` |
| `st.card` | `Card` composable |
| `st.form` / `st.form_submit_button` | `OutlinedTextField` + `Button` |
| `st.table` | `DataTable` / `LazyColumn` |
| `st.selectbox` | `DropdownMenu` / `ExposedDropdownMenu` |
| `st.date_input` | `DatePicker` |
| `st.number_input` | `OutlinedTextField` (numeric keyboard) |
| `st.dialog` | `Dialog` / `AlertDialog` |
| `st.tabs` | `TabRow` |
| `st.columns` | `Row` / `Column` |
| `st.metric` | Custom `KpiCard` |
| `st.success/error/warning` | `Snackbar` |
| `st.progress` | `LinearProgressIndicator` |
| antd `Table` | `DataTable` with `remember` state |
| antd `Form` | `TextField` + `Validation` |
| antd `Modal` | `Dialog` |
| antd `DatePicker` | `DatePicker` |
| antd `Select` | `ExposedDropdownMenu` |

### 4.3 交互模式

| Desktop 行为 | Android 实现 |
|--------------|--------------|
| Streamlit 实时刷新 | `StateFlow` 响应式更新 |
| `st.rerun` | `snapshotFlow` / `collectAsState` |
| Session State | `ViewModel` + `SavedStateHandle` |
| Form 提交 | `LaunchedEffect` + `ViewModel` |
| 侧边栏筛选 | `BottomSheet` / `FilterSheet` |
| 数据导出Excel | `DocumentFile` + `Toast` 分享 |
| 确认对话框 | `AlertDialog` / `ConfirmDialog` |

---

## 五、事件系统

### 5.1 领域事件 (Desktop -> Android)

| Desktop Event | Android Event | 触发时机 |
|---------------|----------------|----------|
| `VC_CREATED` | `VcCreatedEvent` | VC创建 |
| `VC_STATUS_CHANGED` | `VcStatusChangedEvent` | VC状态变更 |
| `LOGISTICS_CREATED` | `LogisticsCreatedEvent` | 物流创建 |
| `LOGISTICS_COMPLETED` | `LogisticsCompletedEvent` | 物流完成 |
| `CASH_FLOW_RECORDED` | `CashFlowRecordedEvent` | 资金流水记录 |
| `INVENTORY_UPDATED` | `InventoryUpdatedEvent` | 库存更新 |
| `VOUCHER_GENERATED` | `VoucherGeneratedEvent` | 凭证生成 |
| `BUSINESS_STAGE_CHANGED` | `BusinessStageChangedEvent` | 业务阶段变更 |

### 5.2 事件监听器

```kotlin
// EventBus / SharedFlow 实现
interface DomainEvent
sealed class VcEvent : DomainEvent
sealed class LogisticsEvent : DomainEvent
sealed class FinanceEvent : DomainEvent

// 监听器注册
eventBus.subscribe<VcStatusChangedEvent> { event ->
    // 更新UI, 触发规则引擎
}
```

---

## 六、实现优先级

```
P0 (MVP - 必须):
1. Room 数据库 + 基础 Entity
2. Master Data CRUD (客户/地点/供应商/SKU)
3. Business 生命周期管理
4. Virtual Contract 全流程
5. 基础 Dashboard

P1 (核心功能):
6. 供应链管理
7. 仓储管理 (设备SN + 物料库存)
8. 物流管理
9. 财务管理 (资金流水 + 复式记账)

P2 (高级功能):
10. 时间规则引擎
11. 月度报表
12. Excel 导入导出
13. 深色主题
14. 离线同步
```

---

## 七、关键文件清单

### 7.1 需要转换的 Desktop 文件

| Category | Desktop Files | Count |
|----------|---------------|-------|
| Database | `models.py` | 1 |
| Business Logic | `logic/**/*.py` | ~30 |
| UI Screens | `ui/*.py` | 6 |
| API | `api/*.py` | 11 |
| Constants | `logic/constants.py` | 1 |

### 7.2 Android 需新建文件 (估算)

| Category | Files | Count |
|----------|-------|-------|
| Entities | `entity/*.kt` | 23 |
| DAOs | `dao/*.kt` | 23 |
| Repositories | `repository/*.kt` | 15 |
| UseCases | `usecase/*.kt` | 40+ |
| ViewModels | `screens/*/ViewModel.kt` | 15 |
| Screens | `screens/*/*.kt` | 30+ |
| Components | `components/*.kt` | 20+ |

---

## 八、里程碑

| 里程碑 | 目标日期 | 交付物 |
|--------|----------|--------|
| M1: 基础框架 | Week 2 | 项目结构, Room, 主题, 导航 |
| M2: Master Data | Week 3 | 客户/地点/供应商/SKU CRUD |
| M3: Business + VC | Week 5 | 业务生命周期, 虚拟合同 |
| M4: 供应链+仓储 | Week 7 | 供应链协议, 设备SN, 物料库存 |
| M5: 物流+资金 | Week 10 | 物流管理, 复式记账, 凭证 |
| M6: 规则引擎+报表 | Week 12 | 时间规则, 月度报告 |
| M7: 完成度验证 | Week 13 | 功能对比测试 |

---

## 九、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 桌面逻辑复杂 | 移植工作量大 | 分阶段交付, 优先MVP |
| 桌面状态管理简单 | Android需要额外代码 | ViewModel + StateFlow |
| 复式记账逻辑 | 移植复杂 | 保留逻辑层, 简化UI调用 |
| Excel导入导出 | 需要库支持 | Apache POI / OpenXML |
| 离线同步 | 实现困难 | 初期仅本地, 后期加Sync |
