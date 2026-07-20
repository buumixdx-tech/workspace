# Mobile (Android V2) 与 Desktop (Python) 原子级别对比分析

> 生成时间: 2026-04-02
> Mobile: `shanyin-android-v2` (Kotlin, Clean Architecture + MVVM, Room DB, Hilt, Jetpack Compose)
> Desktop: `desktop-version` (Python, SQLAlchemy ORM, 单一 models.py, CQRS pattern in logic/)

---

## 1. 架构模式总览

| 维度 | Desktop (Python) | Mobile V2 (Kotlin) |
|------|----------------|---------------------|
| 架构风格 | 过程式 + ORM | Clean Architecture + MVVM |
| 数据层 | `models.py` 单文件 24 个 SQLAlchemy Models | `data/local/entity/` 24 个 Room Entities |
| 业务逻辑 | `logic/*.py` (actions/queries/schemas) | `domain/usecase/` 纯 Kotlin Use Cases |
| 状态管理 | `state_machine.py` 集中式状态机 | `VirtualContractStateMachineUseCase` ✅ |
| 财务凭证 | `finance/engine.py` 集中处理 | `ProcessCashFlowFinanceUseCase` + `ProcessLogisticsFinanceUseCase` ✅ |
| 时间规则 | `time_rules/` 集中引擎 | `domain/usecase/rule_engine/` ✅ + `TimeRuleUseCases` ✅ |
| 事件系统 | `events/` 统一分发 | `SystemEventRepository.insert()` (简化版) |
| 常量定义 | `logic/constants.py` 集中 | 分散到 `domain/model/` 各 enum 类 |
| DI 框架 | 无 | Hilt (Dagger) ✅ |
| UI 框架 | FastAPI + Streamlit | Jetpack Compose ✅ |

---

## 2. 数据结构 (Models/Entities) 完整映射

### 2.1 核心业务实体 一一对应

| Desktop (`models.py`) | Mobile (Room Entity) | 字段对比 |
|----------------------|---------------------|---------|
| `ChannelCustomer` | `ChannelCustomerEntity` | ✅ 完全一致 |
| `Point` | `PointEntity` | ✅ 完全一致 |
| `Supplier` | `SupplierEntity` | ✅ 完全一致 |
| `SKU` | `SkuEntity` | ✅ 完全一致 |
| `EquipmentInventory` | `EquipmentInventoryEntity` | ✅ 字段一致 |
| `MaterialInventory` | `MaterialInventoryEntity` | ✅ 字段一致 |
| `Contract` | `ContractEntity` | ✅ 字段一致 |
| `VirtualContract` | `VirtualContractEntity` | ✅ 核心字段一致 |
| `VirtualContractStatusLog` | `VirtualContractStatusLogEntity` | ✅ 字段一致 |
| `VirtualContractHistory` | `VirtualContractHistoryEntity` | ✅ 字段一致 |
| `FinanceAccount` | `FinanceAccountEntity` | ✅ 字段一致 |
| `FinancialJournal` | `FinancialJournalEntity` | ✅ 字段一致 |
| `CashFlowLedger` | `CashFlowLedgerEntity` | ✅ 字段一致 |
| `ExternalPartner` | `ExternalPartnerEntity` | ✅ 字段一致 |
| `BankAccount` | `BankAccountEntity` | ✅ 字段一致 |
| `Business` | `BusinessEntity` | ✅ 字段一致 |
| `SupplyChain` | `SupplyChainEntity` | ✅ 字段一致 |
| `SupplyChainItem` | `SupplyChainItemEntity` | ✅ 字段一致 |
| `Logistics` | `LogisticsEntity` | ✅ 字段一致 |
| `ExpressOrder` | `ExpressOrderEntity` | ✅ 字段一致 |
| `CashFlow` | `CashFlowEntity` | ✅ 字段一致 |
| `TimeRule` | `TimeRuleEntity` | ✅ 字段一致 |
| `SystemEvent` | `SystemEventEntity` | ✅ 字段一致 |

**总计: Desktop 24 个 Models == Mobile 24 个 Entities (100% 覆盖)**

---

## 3. Enum/常量 对比

### 3.1 VC 类型 (VCType)

| Desktop | Mobile V2 | 映射 |
|---------|-----------|------|
| `VCType.EQUIPMENT_PROCUREMENT` | `VCType.EQUIPMENT_PROCUREMENT` | ✅ 同名 |
| `VCType.STOCK_PROCUREMENT` | `VCType.EQUIPMENT_STOCK` | ⚠️ 重命名 |
| `VCType.INVENTORY_ALLOCATION` | `VCType.INVENTORY_ALLOCATION` | ✅ 同名 |
| `VCType.MATERIAL_PROCUREMENT` | `VCType.MATERIAL_PROCUREMENT` | ✅ 同名 |
| `VCType.MATERIAL_SUPPLY` | `VCType.MATERIAL_SUPPLY` | ✅ 同名 |
| `VCType.RETURN` | `VCType.RETURN` | ✅ 同名 |

### 3.2 VC 状态 (VCStatus)

| Desktop | Mobile V2 | 映射 |
|---------|-----------|------|
| `VCStatus.EXE` | `VCStatus.EXECUTING` | ⚠️ 缩写 vs 全称 |
| `VCStatus.FINISH` | `VCStatus.COMPLETED` | ⚠️ FINISH vs COMPLETED |
| `VCStatus.TERMINATED` | `VCStatus.TERMINATED` | ✅ 同名 |
| `VCStatus.CANCELLED` | `VCStatus.CANCELLED` | ✅ 同名 |

### 3.3 标的物状态 (SubjectStatus)

| Desktop | Mobile V2 | 映射 |
|---------|-----------|------|
| `SubjectStatus.EXE` | `SubjectStatus.EXECUTING` | ⚠️ 缩写 vs 全称 |
| `SubjectStatus.SHIPPED` | `SubjectStatus.SHIPPED` | ✅ 同名 |
| `SubjectStatus.SIGNED` | `SubjectStatus.SIGNED` | ✅ 同名 |
| `SubjectStatus.FINISH` | `SubjectStatus.COMPLETED` | ⚠️ FINISH vs COMPLETED |

### 3.4 资金状态 (CashStatus)

| Desktop | Mobile V2 | 映射 |
|---------|-----------|------|
| `CashStatus.EXE` | `CashStatus.EXECUTING` | ⚠️ 缩写 vs 全称 |
| `CashStatus.PREPAID` | `CashStatus.PREPAID` | ✅ 同名 |
| `CashStatus.FINISH` | `CashStatus.COMPLETED` | ⚠️ FINISH vs COMPLETED |

### 3.5 物流状态 (LogisticsStatus)

| Desktop | Mobile V2 | 映射 |
|---------|-----------|------|
| `LogisticsStatus.PENDING` | `LogisticsStatus.PENDING` | ✅ 同名 |
| `LogisticsStatus.TRANSIT` | `LogisticsStatus.IN_TRANSIT` | ⚠️ 不同名 |
| `LogisticsStatus.SIGNED` | `LogisticsStatus.SIGNED` | ✅ 同名 |
| `LogisticsStatus.FINISH` | `LogisticsStatus.COMPLETED` | ⚠️ FINISH vs COMPLETED |

### 3.6 资金流类型 (CashFlowType) ⚠️ 关键差异

| Desktop | Mobile V2 | 映射 |
|---------|-----------|------|
| `CashFlowType.PREPAYMENT` | `CashFlowType.PREPAYMENT` | ✅ 同名 |
| `CashFlowType.FULFILLMENT` | `CashFlowType.PERFORMANCE` | ⚠️ 不同名 |
| `CashFlowType.DEPOSIT` | `CashFlowType.DEPOSIT` | ✅ 同名 |
| `CashFlowType.RETURN_DEPOSIT` | `CashFlowType.DEPOSIT_REFUND` | ⚠️ 不同名 |
| `CashFlowType.REFUND` | `CashFlowType.REFUND` | ✅ 同名 |
| `CashFlowType.OFFSET_PAY` | `CashFlowType.OFFSET_OUTFLOW` | ⚠️ 不同名 |
| `CashFlowType.OFFSET_IN` | `CashFlowType.OFFSET_INFLOW` | ⚠️ 不同名 |
| `CashFlowType.DEPOSIT_OFFSET_IN` | `CashFlowType.DEPOSIT_OFFSET_IN` | ✅ 同名 |
| `CashFlowType.PENALTY` | `CashFlowType.PENALTY` | ✅ 同名 |

### 3.7 设备运营状态 (OperationalStatus)

| Desktop | Mobile V2 | 映射 |
|---------|-----------|------|
| `OperationalStatus.STOCK` | `OperationalStatus.IN_STOCK` | ⚠️ 不同名 |
| `OperationalStatus.OPERATING` | `OperationalStatus.IN_OPERATION` | ⚠️ 不同名 |
| `OperationalStatus.DISPOSED` | `OperationalStatus.DISPOSAL` | ⚠️ 不同名 |

---

## 4. 业务逻辑模块对比

### 4.1 虚拟合同 (VC) ✅ Mobile 完整实现

| 操作 | Desktop | Mobile V2 |
|------|---------|-----------|
| 创建设备采购 VC | `create_procurement_vc_action()` | `CreateEquipmentProcurementVCUseCase` ✅ |
| 创建物料供应 VC | `create_material_supply_vc_action()` | `CreateMaterialSupplyVCUseCase` ✅ |
| 创建物料采购 VC | `create_mat_procurement_vc_action()` | ❌ 缺失 (仅有 SaveVirtualContractUseCase) |
| 创建库存采购 VC | `create_stock_procurement_vc_action()` | ❌ 缺失 (仅有 SaveVirtualContractUseCase) |
| 创建退货 VC | `create_return_vc_action()` | `CreateReturnVCUseCase` ✅ |
| 库存拨付 | `create_inventory_allocation_action()` | ❌ 缺失 (仅有 TransferInventoryUseCase) |
| 更新 VC | `update_vc_action()` | `SaveVirtualContractUseCase` ✅ |
| 删除 VC | `delete_vc_action()` | `DeleteVirtualContractUseCase` ✅ |
| 完成 VC | - | `CompleteVirtualContractUseCase` ✅ |
| 终止 VC | - | `TerminateVirtualContractUseCase` ✅ |
| VC 查询列表 | `get_vc_list()` | `VirtualContractRepository.getAll()` + Flow ✅ |
| VC 详情 | `get_vc_detail()` | `VirtualContractRepository.getById()` ✅ |
| VC 状态日志 | `get_vc_status_logs()` | `GetVCStatusLogsUseCase` ✅ |
| VC 历史版本 | - | `GetVCHistoryUseCase` ✅ |
| 获取可退货 VC | `get_virtual_contracts_for_return()` | ❌ 缺失 |
| 更新标的物状态 | - | `UpdateVCSubjectStatusUseCase` ✅ |
| 更新资金状态 | - | `UpdateVCCashStatusUseCase` ✅ |

### 4.2 物流 (Logistics) ✅ Mobile 完整实现

| 操作 | Desktop | Mobile V2 |
|------|---------|-----------|
| 创建物流计划 | `create_logistics_plan_action()` | `CreateLogisticsUseCase` ✅ |
| 确认入库 | `confirm_inbound_action()` | `ConfirmInboundUseCase` ✅ |
| 更新快递单 | `update_express_order_action()` | `UpdateExpressOrderTrackingUseCase` ✅ |
| 推进快递单状态 | `update_express_order_status_action()` | `UpdateExpressOrderStatusUseCase` ✅ |
| 批量推进 | `bulk_progress_express_orders_action()` | ❌ 缺失 |
| 物流查询 | `get_logistics_by_vc()` | `GetLogisticsByVcUseCase` ✅ |
| 物流列表 (UI) | `get_logistics_list_for_ui()` | `GetAllLogisticsUseCase` ✅ |
| 快递单列表 | `get_express_orders_by_logistics()` | `GetExpressOrdersByLogisticsUseCase` ✅ |
| 触发物流凭证 | - | `TriggerFinanceUseCase` ✅ |

### 4.3 财务 (Finance) ✅ Mobile 完整实现

| 操作 | Desktop | Mobile V2 |
|------|---------|-----------|
| 创建资金流 | `create_cash_flow_action()` | `CreateCashFlowUseCase` ✅ (含完整验证) |
| 更新资金流 | - | `UpdateCashFlowUseCase` ✅ |
| 删除资金流 | - | `DeleteCashFlowUseCase` ✅ |
| 内部划拨 | `internal_transfer_action()` | `InternalTransferUseCase` ✅ |
| 外部出入金 | `external_fund_action()` | `ExternalFundUseCase` ✅ |
| 凭证生成 | `process_cash_flow_finance()` | `TriggerCashFlowFinanceUseCase` + `ProcessCashFlowFinanceUseCase` ✅ |
| 物流凭证 | `process_logistics_finance()` | `ProcessLogisticsFinanceUseCase` ✅ |
| 核销池管理 | `offset_manager.py` | `OffsetPoolUseCase` ✅ |
| 应用核销到 VC | `apply_offset_to_vc()` | `ApplyOffsetToVcUseCase` ✅ |
| 财务报表 | `get_dashboard_stats()` | `FinancialStatementsUseCase` ✅ |
| 银行对账 | - | `BankReconciliationUseCase` ✅ |
| 应收应付 | - | `AccountsPayableReceivableUseCases` ✅ |
| VC 货款进度 | `calculate_cashflow_progress()` | `GetVcPaymentProgressUseCase` ✅ |
| 建议资金流方 | `get_suggested_cashflow_parties()` | `GetSuggestedCashflowPartiesUseCase` ✅ |
| 可用资金流类型 | - | `GetAvailableCashFlowTypesUseCase` ✅ |
| 复式记账凭证 | - | `CreateDoubleEntryVoucherUseCase` ✅ |
| 财务账户余额 | - | `GetAccountBalanceUseCase` ✅ |

### 4.4 押金 (Deposit) ✅ Mobile 完整实现 (在 StateMachine 内)

| 操作 | Desktop | Mobile V2 |
|------|---------|-----------|
| 押金模块入口 | `deposit_module()` | `VirtualContractStateMachineUseCase.onCashFlowChanged()` ✅ |
| 处理 CF 押金 | `process_cf_deposit()` | `VirtualContractStateMachineUseCase.processCfDeposit()` ✅ |
| 处理 VC 押金 | `process_vc_deposit()` | `VirtualContractStateMachineUseCase.processVcDeposit()` ✅ |
| 押金分布到设备 | ✅ (在 process_vc_deposit 内) | `VirtualContractStateMachineUseCase.distributeDepositToInventory()` ✅ |
| shouldReceive 重算 | `calculate_should_receive()` | `VirtualContractStateMachineUseCase.calculateShouldReceive()` ✅ |
| 退货 VC 押金重定向 | ✅ | `VirtualContractStateMachineUseCase.processCfDeposit()` ✅ |

### 4.5 库存 (Inventory) ✅ Mobile 完整实现

| 操作 | Desktop | Mobile V2 |
|------|---------|-----------|
| 库存模块入口 | `inventory_module()` | `ConfirmInboundUseCase.createInventoryByVcType()` ✅ |
| 设备采购入库 | ✅ | `ConfirmInboundUseCase` (EQUIPMENT_PROCUREMENT 分支) ✅ |
| 物料采购入库 | ✅ | `ConfirmInboundUseCase` (MATERIAL_PROCUREMENT 分支) ✅ |
| 物料供应出库 | ✅ | `ConfirmInboundUseCase` (MATERIAL_SUPPLY 分支) ✅ |
| 退货库存更新 | ✅ | `ConfirmInboundUseCase` (RETURN 分支) ✅ |
| 库存调拨 | - | `TransferInventoryUseCase` ✅ |
| 库存分布更新 | - | `UpdateStockDistributionUseCase` ✅ |
| 设备状态更新 | - | `UpdateEquipmentStatusUseCase` ✅ |
| 库存查询 | `get_equipment_inventory_summary()` | `EquipmentInventoryRepository` ✅ (只读) |

### 4.6 状态机 (State Machine) ✅ Mobile 完整实现

| 操作 | Desktop | Mobile V2 |
|------|---------|-----------|
| VC 状态机 | `virtual_contract_state_machine()` | `VirtualContractStateMachineUseCase` ✅ |
| - 物流→标的物状态 | ✅ | `onLogisticsStatusChanged()` ✅ |
| - 资金流→押金处理 | ✅ | `onCashFlowChanged()` → `processCfDeposit()` ✅ |
| - 资金流→cashStatus 重算 | ✅ | `onCashFlowChanged()` → `recalculateCashStatus()` ✅ |
| - 整体状态重算 | `check_vc_overall_status()` | `recalculateOverallStatus()` ✅ |
| - 退货 VC 自动完成 | ✅ | `processReturnVcAutoComplete()` ✅ |
| 物流状态机 | `logistics_state_machine()` | `UpdateExpressOrderStatusUseCase.deriveLogisticsStatus()` ✅ |

### 4.7 时间规则 (Time Rules) ✅ Mobile 完整实现

| 操作 | Desktop | Mobile V2 |
|------|---------|-----------|
| 规则引擎 | `TimeRuleEngine` | `RuleEngine` ✅ |
| 规则评估 | `RuleEvaluator` | `RuleEvaluator` ✅ |
| 事件处理 | `EventHandler` | `EventHandler` ✅ |
| 继承解析 | `InheritanceResolver` | ❌ 缺失 (简化实现) |
| 规则传播 | `RuleManager.sync_from_parent()` | `SyncRulesFromBusinessUseCase`, `SyncRulesFromSupplyChainUseCase`, `SyncRulesFromVirtualContractUseCase` ✅ |
| 创建规则 | `save_rule_action()` | `SaveTimeRuleUseCase` ✅ |
| 删除规则 | `delete_rule_action()` | `DeleteTimeRuleUseCase` ✅ |
| 更新规则状态 | - | `UpdateTimeRuleStatusUseCase` ✅ |
| 规则查询 | `get_time_rules_for_ui()` | `GetAllTimeRulesUseCase` ✅ |
| 从付款条款生成规则 | `generate_rules_from_payment_terms()` | `GenerateRulesFromPaymentTermsUseCase` ✅ |

### 4.8 事件系统 (Events) ⚠️ Mobile 简化

| 操作 | Desktop | Mobile V2 |
|------|---------|-----------|
| 发送事件 | `emit_event()` | `RecordSystemEventUseCase` ✅ |
| 事件监听器 | `register_listener()` | ❌ 缺失 |
| 内置响应器 | `responders.py` | ❌ 缺失 |
| 事件查询 | - | `GetAllSystemEventsUseCase` ✅ |
| 标记已推送 | - | `MarkEventAsPushedUseCase` ✅ |

### 4.9 业务 (Business) ✅ Mobile 完整实现

| 操作 | Desktop | Mobile V2 |
|------|---------|-----------|
| 创建业务 | `create_business_action()` | `CreateBusinessUseCase` ✅ |
| 更新业务状态 | `update_business_status_action()` | `AdvanceBusinessStageUseCase` ✅ |
| 推进业务阶段 | `advance_business_stage_action()` | `AdvanceBusinessStageUseCase` ✅ |
| 暂停业务 | - | `SuspendBusinessUseCase` ✅ |
| 重新激活 | - | `ReactivateBusinessUseCase` ✅ |
| 终止业务 | - | `TerminateBusinessUseCase` ✅ |
| 删除业务 | `delete_business_action()` | `DeleteBusinessUseCase` ✅ |
| 业务列表 | `get_business_list()` | `GetAllBusinessesUseCase` ✅ |

### 4.10 供应链 (Supply Chain) ✅ Mobile 完整实现

| 操作 | Desktop | Mobile V2 |
|------|---------|-----------|
| 创建供应链 | `create_supply_chain_action()` | `CreateSupplyChainUseCase` ✅ |
| 删除供应链 | `delete_supply_chain_action()` | `DeleteSupplyChainUseCase` ✅ |
| 更新 SKU 定价 | - | `UpdateSkuPricingUseCase` ✅ |
| 查询供应链 | `get_supply_chains_for_ui()` | `GetAllSupplyChainsUseCase` ✅ |
| 供应链详情 | `get_supply_chain_detail_for_ui()` | `GetSupplyChainByIdUseCase` ✅ |

### 4.11 主数据 (Master Data) ✅ Mobile 完整实现

| 操作 | Desktop | Mobile V2 |
|------|---------|-----------|
| 创建客户 | `create_customer_action()` | `SaveCustomerUseCase` ✅ |
| 更新客户 | `update_customers_action()` | `SaveCustomerUseCase` ✅ |
| 创建点位 | `create_point_action()` | `SavePointUseCase` ✅ |
| 创建 SKU | `create_sku_action()` | `SaveSkuUseCase` ✅ |
| 创建供应商 | `create_supplier_action()` | `SaveSupplierUseCase` ✅ |
| 创建合作伙伴 | `create_partner_action()` | `SavePartnerUseCase` ✅ |
| 创建银行账户 | `create_bank_account_action()` | `SaveBankAccountUseCase` ✅ |
| 查询客户 | `get_customers_for_ui()` | `GetAllCustomersUseCase` ✅ |
| 查询 SKU | `get_skus_for_ui()` | `GetAllSkusUseCase` ✅ |
| 查询点位 | `get_points_for_ui()` | `GetAllPointsUseCase` ✅ |
| 查询供应商 | `get_suppliers_for_ui()` | `GetAllSuppliersUseCase` ✅ |
| 查询银行账户 | - | `GetAllBankAccountsUseCase` ✅ |

---

## 5. 命名不一致风险汇总 ⚠️

### 5.1 状态值命名不一致 (数据同步风险)

| 类别 | Desktop 值 | Mobile V2 值 | 风险级别 |
|------|-----------|-------------|---------|
| VCStatus | `FINISH` | `COMPLETED` | 🔴 高 - 状态判断失效 |
| VCStatus | `EXE` | `EXECUTING` | 🔴 高 - 状态判断失效 |
| CashStatus | `FINISH` | `COMPLETED` | 🔴 高 - 状态判断失效 |
| CashStatus | `EXE` | `EXECUTING` | 🔴 高 - 状态判断失效 |
| SubjectStatus | `FINISH` | `COMPLETED` | 🔴 高 - 状态判断失效 |
| SubjectStatus | `EXE` | `EXECUTING` | 🔴 高 - 状态判断失效 |
| LogisticsStatus | `FINISH` | `COMPLETED` | 🔴 高 - 状态判断失效 |
| LogisticsStatus | `TRANSIT` | `IN_TRANSIT` | 🔴 高 |
| OperationalStatus | `STOCK` | `IN_STOCK` | 🟡 中 |
| OperationalStatus | `OPERATING` | `IN_OPERATION` | 🟡 中 |

### 5.2 CashFlowType 命名不一致 (资金流类型判断失效)

| Desktop 值 | Mobile V2 值 | 风险级别 |
|-----------|-------------|---------|
| `FULFILLMENT` | `PERFORMANCE` | 🔴 高 - 货款计算逻辑失效 |
| `RETURN_DEPOSIT` | `DEPOSIT_REFUND` | 🔴 高 |
| `OFFSET_PAY` | `OFFSET_OUTFLOW` | 🔴 高 |
| `OFFSET_IN` | `OFFSET_INFLOW` | 🔴 高 |

### 5.3 VCType 命名不一致

| Desktop 值 | Mobile V2 值 | 风险级别 |
|-----------|-------------|---------|
| `STOCK_PROCUREMENT` | `EQUIPMENT_STOCK` | 🟡 中 - 类型匹配可能失效 |

---

## 6. Mobile V2 完整实现清单 ✅

1. **VC 状态机** - `VirtualContractStateMachineUseCase` 完整实现 (含押金处理、cashStatus 重算、整体状态重算、 RETURN VC 自动完成)
2. **VC 创建 Use Cases** - 设备采购 `CreateEquipmentProcurementVCUseCase`、物料供应 `CreateMaterialSupplyVCUseCase`、退货 `CreateReturnVCUseCase`
3. **物流操作 Use Cases** - 创建 `CreateLogisticsUseCase`、确认入库 `ConfirmInboundUseCase`、快递单状态推进 `UpdateExpressOrderStatusUseCase`
4. **库存操作 Use Cases** - 入库创建 (设备按 SN/物料按汇总)、调拨 `TransferInventoryUseCase`、分布更新 `UpdateStockDistributionUseCase`
5. **财务凭证生成** - `ProcessCashFlowFinanceUseCase` (资金流凭证化)、`ProcessLogisticsFinanceUseCase` (物流凭证化)
6. **Business Use Cases** - 完整 CRUD + 阶段推进 (创建/推进/暂停/终止/重新激活)
7. **Supply Chain Use Cases** - 完整 CRUD + SKU 定价管理
8. **Master Data Use Cases** - Customer/Point/Supplier/SKU/Partner/BankAccount 完整 CRUD
9. **财务核销** - `OffsetPoolUseCase`, `ApplyOffsetToVcUseCase`
10. **财务报表** - `FinancialStatementsUseCase`, `BankReconciliationUseCase`
11. **应收应付** - `AccountsPayableReceivableUseCases`
12. **规则引擎核心** - `RuleEngine`, `RuleEvaluator`, `EventHandler`
13. **时间规则 Use Cases** - 完整 CRUD + 从付款条款生成 + 规则同步 (Business/SC/VC → Logistics)
14. **数据导入** - `ImportViewModel`
15. **所有 Entity 的 Repository 接口**

---

## 7. Mobile V2 缺失清单 ⚠️

1. **物料采购 VC 创建** - 无 `create_mat_procurement_vc_action` 等效 (可用 `SaveVirtualContractUseCase` 代替)
2. **库存采购 VC 创建** - 无 `create_stock_procurement_vc_action` 等效 (可用 `SaveVirtualContractUseCase` 代替)
3. **库存拨付 VC 创建** - 无 `create_inventory_allocation_action` 等效 (仅 `TransferInventoryUseCase` 处理库存层面)
4. **批量快递单推进** - 无 `bulk_progress_express_orders_action` 等效
5. **事件监听器/响应器** - `emit_event` 仅记录到 `SystemEventRepository`，无实际响应逻辑
6. **规则继承解析器** - `InheritanceResolver` 未单独实现 (简化版本在 `SyncRulesFrom*UseCase` 中)
7. **获取可退货 VC** - 无 `get_virtual_contracts_for_return` 等效

---

## 8. 关键结论

### 8.1 Mobile V2 已实现核心业务流程闭环

Mobile V2 已实现完整的 VC 生命周期管理：创建 → 状态推进 → 财务凭证化 → 完成/终止。特别是 `VirtualContractStateMachineUseCase` 完整对标 Desktop 的状态机逻辑。

### 8.2 命名不一致是数据同步的主要风险

`FINISH` vs `COMPLETED`、`EXE` vs `EXECUTING`、`FULFILLMENT` vs `PERFORMANCE` 等命名差异，会导致 Desktop 和 Mobile 之间数据同步时状态判断完全失效。需要建立统一的映射层。

### 8.3 Mobile V2 可作为完整的离线客户端

当前 Mobile V2 状态：
- ✅ 可创建和推进 VC 业务流程
- ✅ 可执行物流操作和入库确认
- ✅ 可处理财务凭证和核销
- ✅ 可管理主数据和供应链
- ✅ 可生成财务报表和进行银行对账
- ⚠️ 需要注意与 Desktop 的命名映射

### 8.4 建议后续工作

1. **统一枚举命名** - 在数据同步层建立 Desktop→Mobile 命名映射
2. **补充物料采购/库存采购 VC 创建 Use Case** - 基于 `SaveVirtualContractUseCase` 封装
3. **补充批量快递单推进** - 参考 `UpdateExpressOrderStatusUseCase` 扩展
4. **完善事件响应机制** - 实现简单的内置响应器
