# 闪饮 ERP 系统 API 手册

> [!IMPORTANT]
> 本文档包含 ShanYin ERP 系统 `logic` 层的所有公开 API 函数。本文档旨在实现 100% 的功能覆盖，确保所有 UI 操作均可通过对应的 API 逻辑实现。
>
> **版本说明：** 包含 v5.0 VC elements 重构、addon_business 附加业务模块、operation_transactions 回滚事务模块。

## 导入路径速查

```python
from logic.vc import create_procurement_vc_action, get_vc_list, get_vc_detail, VCElementSchema
from logic.business import create_business_action, advance_business_stage_action
from logic.master import get_customers, get_system_constants
from logic.finance import create_cash_flow_action, get_cash_flow_list, get_dashboard_stats
from logic.logistics import create_logistics_plan_action, confirm_inbound_action
from logic.supply_chain import create_supply_chain_action
from logic.services import calculate_cashflow_progress, get_returnable_items
from logic.addon_business import create_addon_business_action, get_active_addons
from logic.transactions import rollback_operation, redo_operation
```

---

## 1. 基础数据 (Master Data) API

**模块路径：** `logic/master/`

### 客户管理 (Customers)
- **`create_customer_action(session, payload)`**: 创建新客户。payload 为 `CustomerSchema`。
- **`update_customers_action(session, payloads)`**: 批量更新客户信息。
- **`delete_customers_action(session, payloads)`**: 批量删除客户。
- **`get_customers()`**: 获取客户列表（别名：`get_customers_for_ui`）。
- **`get_partner_by_id(partner_id)`**: 根据 ID 获取合作方（客户/供应商）详情。

### 供应商管理 (Suppliers)
- **`create_supplier_action(session, payload)`**: 创建新供应商。
- **`update_suppliers_action(session, payloads)`**: 批量更新供应商信息。
- **`delete_suppliers_action(session, payloads)`**: 批量删除供应商。
- **`get_suppliers()`**: 获取供应商列表（别名：`get_suppliers_for_ui`）。

### 点位与仓库 (Points)
- **`create_point_action(session, payload)`**: 创建新点位/仓库。
- **`update_points_action(session, payloads)`**: 批量更新点位信息。
- **`delete_points_action(session, payloads)`**: 批量删除点位。
- **`get_points()`**: 获取点位列表，支持关键词搜索（别名：`get_points_for_ui`）。

### 商品与 SKU (SKUs)
- **`create_sku_action(session, payload)`**: 创建新 SKU。
- **`update_skus_action(session, payloads)`**: 批量更新 SKU 信息。
- **`delete_skus_action(session, payloads)`**: 批量删除 SKU。
- **`get_skus()`**: 获取 SKU 列表（别名：`get_skus_for_ui`）。

### 外部合作方 (Partners)
- **`create_partner_action(session, payload)`**: 创建新外部合作方。
- **`update_partners_action(session, payloads)`**: 批量更新合作方信息。
- **`delete_partners_action(session, payloads)`**: 批量删除合作方。
- **`get_partners()`**: 获取合作方列表（别名：`get_partners_for_ui`）。

### 银行账户 (Bank Accounts)
- **`create_bank_account_action(session, payload)`**: 创建新的银行账户。
- **`update_bank_accounts_action(session, payloads)`**: 批量更新银行账户信息。
- **`delete_bank_accounts_action(session, payloads)`**: 批量删除银行账户。
- **`get_bank_accounts()`**: 获取银行账户列表（别名：`get_bank_accounts_for_ui`）。
- **`get_bank_account_by_id(account_id)`**: 根据 ID 获取账户详情。

### 系统级
- **`get_system_constants()`**: 获取系统全局常量映射表（供前端构建下拉选择器）。

---

## 2. 业务管理 (Business Management) API

**模块路径：** `logic/business/`

- **`create_business_action(session, payload)`**: 启动新的业务项（如：前期接洽）。使用 `CreateBusinessSchema`。
- **`update_business_status_action(session, payload)`**: 更新业务项状态（终止、暂缓等）。使用 `UpdateBusinessStatusSchema`。
- **`delete_business_action(session, business_id)`**: 删除业务项（仅限无关联数据时）。
- **`advance_business_stage_action(session, payload)`**: 推进业务阶段（如：从"评估"到"落地"），并支持自动生成时间规则和合同。使用 `AdvanceBusinessStageSchema`。
- **`get_business_list(status=None, customer_id=None, limit=100)`**: 按状态或客户筛选业务列表。
- **`get_business_detail(business_id)`**: 获取业务项的完整视图，包括关联合同。
- **`get_businesses_for_execution()`**: 获取所有处于"落地"或"开展"阶段的业务。

---

## 3. 附加业务 (Addon Business) API

**模块路径：** `logic/addon_business/`

> 附加业务政策（原子化）：在 Business ACTIVE 阶段，可对特定 SKU 添加有效期促销/新增价格协议。

### Actions
- **`create_addon_business_action(session, payload)`**: 创建附加业务政策（PRICE_ADJUST / NEW_SKU）。使用 `CreateAddonSchema`。
- **`update_addon_business_action(session, payload)`**: 更新附加业务（仅可修改日期、覆盖值、status、remark）。使用 `UpdateAddonSchema`。
- **`deactivate_addon_business_action(session, addon_id)`**: 软删除/失效附加业务。

### 查询
- **`get_active_addons(session, business_id, dt=None)`**: 获取业务下当前生效的所有 addon。
- **`get_active_addons_by_type(session, business_id, addon_type, dt=None)`**: 获取业务下指定类型的生效 addon。
- **`get_addon_detail(session, addon_id)`**: 获取单个 addon 详情。
- **`get_business_addons(session, business_id, include_expired=False)`**: 获取业务下所有 addon（可含过期）。
- **`can_add_addon(session, business_id)`**: 检查业务是否允许添加 addon（前提：ACTIVE 阶段）。
- **`sku_exists_in_business(session, business_id, sku_id)`**: 判断 SKU 是否已在业务定价配置中存在。
- **`get_original_price_and_deposit(session, business_id, sku_id)`**: 获取 SKU 在业务中的原价和原押金。
- **`check_addon_overlap(session, business_id, sku_id, start_date, end_date, exclude_id=None)`**: 检查日期重叠。

---

## 4. 虚拟合同 (Virtual Contracts) API

**模块路径：** `logic/vc/`

> **v5.0 重大变化：** VC 结构从 `items`（`VCItemSchema`）迁移到 `elements`（`VCElementSchema`）。`VCElementSchema` 包含 `shipping_point_id`、`receiving_point_id`、`sku_id`、`qty`、`price`、`deposit`、`subtotal`、`sn_list` 字段。所有 VC 创建接口均使用 `elements` 参数。

### VC 创建 Actions
- **`create_procurement_vc_action(session, payload)`**: 创建设备采购类虚拟合同。使用 `CreateProcurementVCSchema`（包含 `elements: List[VCElementSchema]`）。
- **`create_material_supply_vc_action(session, payload)`**: 创建物料供应类虚拟合同。使用 `CreateMaterialSupplyVCSchema`。
- **`create_stock_procurement_vc_action(session, payload)`**: 创建库存采购类虚拟合同。使用 `CreateStockProcurementVCSchema`。
- **`create_mat_procurement_vc_action(session, payload)`**: 创建物料采购类虚拟合同。使用 `CreateMatProcurementVCSchema`。
- **`create_return_vc_action(session, payload)`**: 创建退货类虚拟合同。使用 `CreateReturnVCSchema`。
- **`update_vc_action(session, payload)`**: 更新虚拟合同信息。使用 `UpdateVCSchema`。
- **`delete_vc_action(session, vc_id)`**: 删除虚拟合同。使用 `DeleteVCSchema`。

### VC 库存操作
- **`create_inventory_allocation_action(session, payload)`**: 拨付库存到虚拟合同（替代旧版 `bulk_allocate_inventory_action`）。使用 `AllocateInventorySchema`。

### VC 查询
- **`get_vc_list(vc_type=None, status=None, limit=100)`**: 获取虚拟合同列表（别名：`get_vc_list_for_ui`）。
- **`get_vc_detail(vc_id)`**: 获取虚拟合同的完整明细（含货品、资金、物流进度）（别名：`get_vc_detail_for_ui`）。
- **`get_time_rules_for_vc(vc_id)`**: 获取某 VC 关联的所有时间规则。
- **`get_returnable_vcs(related_vc_id, return_direction)`**: 获取某原合同关联的可退货 VC 列表。
- **`get_vc_count_by_business(business_id)`**: 按业务 ID 统计 VC 数量。
- **`get_vc_status_logs(vc_id)`**: 获取 VC 的状态变更日志。
- **`get_vc_cash_flows(vc_id)`**: 获取某 VC 的所有资金流记录。

### VC 辅助函数（services.py）
- **`format_vc_items_for_display(vc)`**: 将复杂的 VC `elements` JSON 结构转换为 UI 表格友好的渲染格式。
- **`get_returnable_items(session, target_vc_id, return_direction)`**: 智能计算合同中当前"可退货"的货品范围与数量。
- **`calculate_cashflow_progress(session, vc, existing_cfs)`**: 深度计算虚拟合同的收款进度、实时应付及冲抵池状态。

---

## 5. 供应链 (Supply Chain) API

**模块路径：** `logic/supply_chain/`

- **`create_supply_chain_action(session, payload)`**: 创建供应链框架协议。使用 `CreateSupplyChainSchema`。
- **`delete_supply_chain_action(sc_id)`**: 删除供应链。
- **`get_supply_chains(sc_type=None)`**: 获取供应链列表（别名：`get_supply_chains_by_type`）。
- **`get_supply_chain_detail(sc_id)`**: 获取供应链详细信息（别名：`get_supply_chain_detail_for_ui`）。

---

## 6. 物流管理 (Logistics) API

**模块路径：** `logic/logistics/`

### 物流 Actions
- **`create_logistics_plan_action(session, payload)`**: 创建发货计划（物流单及快递子单）。使用 `CreateLogisticsPlanSchema`。
- **`confirm_inbound_action(session, payload)`**: 确认收货入库，并自动触发库存变更与财务凭证。使用 `ConfirmInboundSchema`。
- **`update_express_order_action(session, payload)`**: 修改快递单的单号或地址。使用 `UpdateExpressOrderSchema`。
- **`update_express_order_status_action(session, payload)`**: 推进快递单状态（待发货 -> 运输中 -> 已签收）。使用 `ExpressOrderStatusSchema`。
- **`bulk_progress_express_orders_action(session, order_ids, target_status, logistics_id)`**: 批量推进快递单状态。

### 物流查询
- **`get_logistics_list(status_list=None, vc_id=None)`**: 获取物流任务列表（别名：`get_logistics_list_for_ui`）。
- **`get_logistics_detail(log_id)`**: 获取物流单详情（别名：`get_logistics_by_id`）。
- **`get_express_detail(logistics_id)`**: 获取某物流单下的所有快递子单（别名：`get_express_orders_by_logistics`）。
- **`get_logistics_dashboard_summary()`**: 获取物流看板的汇总统计（**v5.0 新增**）。

---

## 7. 财务与资金流 (Finance) API

**模块路径：** `logic/finance/`

### 财务 Actions
- **`create_cash_flow_action(session, payload)`**: 录入资金收付、押金及退款流水。使用 `CreateCashFlowSchema`。
- **`internal_transfer_action(session, payload)`**: 执行内部账户间的资金划拨。使用 `InternalTransferSchema`。
- **`external_fund_action(session, payload)`**: 记录非业务类的外部出入金操作。使用 `ExternalFundSchema`。
- **`create_bank_account_action(session, payload)`**: 创建银行账户。使用 `CreateBankAccountSchema`。
- **`update_bank_accounts_action(session, payloads)`**: 批量更新银行账户信息。使用 `UpdateBankAccountSchema`。

### 财务引擎
- **`finance_module(session, ref_type, ref_id)`**: 核心财务处理入口，根据 `ref_type`（`cash_flow` / `logistics`）分发到对应处理函数。
- **`record_entries(session, ...)`**: 记录复式记账分录到 `FinancialJournal`。
- **`rebuild_report(session, year, month)`**: 重建指定月份的财务报表。
- **`get_or_create_account(session, level1, level2, cp_type, cp_id)`**: 按名称和对手方获取或创建会计科目。

### 财务查询
- **`get_cash_flow_list(vc_id=None, cf_type=None, limit=100)`**: 获取资金流列表（别名：`get_cash_flow_list_for_ui`）。
- **`get_bank_accounts()`**: 获取银行账户列表（别名：`get_bank_account_list_for_ui`）。
- **`get_dashboard_stats()`**: 获取财务看板的核心统计汇总数据。
- **`get_account_list_for_ui(...)`**: 获取会计科目余额表。定义在 `queries.py` 中。
- **`get_journal_entries_for_ui(...)`**: 获取详细的记账凭证历史。定义在 `queries.py` 中。
- **`get_fund_operation_history_for_ui(limit=50)`**: 获取资金划拨的历史操作记录（TRF-*/EXT-IN-*/EXT-OUT-* 凭证）。定义在 `queries.py` 中。

### 财务辅助函数（services.py）
- **`get_counterpart_info(session, vc)`**: 获取 VC 的对手方信息（客户/供应商）。
- **`get_suggested_cashflow_parties(session, vc, cf_type)`**: 根据 VC 类型和资金流类型建议资金流的对手方账户。
- **`get_account_balance(session, level1_name, cp_type=None, cp_id=None)`**: 查询特定科目的实时余额（含对手方维度）。
- **`get_logistics_finance_context(session, logistics_id)`**: 构建物流财务上下文（计算 `items_cost`、确定 AR/AP 科目）。
- **`get_cashflow_finance_context(session, cash_flow_id)`**: 构建资金流财务上下文（判断 `is_income`、计算 `ar_ap_amt`/`pre_amt`）。

---

## 8. 时间规则 (Time Rules) API

**模块路径：** `logic/time_rules/`

- **`save_rule_action(session, payload)`**: 保存或编辑时间偏置规则（用于自动产生下游任务）。
- **`delete_rule_action(session, rule_id)`**: 删除特定的时间规则。
- **`persist_draft_rules_action(session, draft_rules, related_type, related_id)`**: 将从合同模板或界面生成的草稿规则持久化到数据库。
- **`get_time_rule_list(related_id, related_type)`**: 获取特定关联对象的所有动态规则。

---

## 9. 库存管理 (Inventory) API

**模块路径：** `logic/inventory/`

- **`get_equipment_inventory(...)`**: 获取设备库存列表。
- **`get_material_inventory(...)`**: 获取物料库存列表。
- **`get_inventory_stats(...)`**: 获取库存统计汇总。

### 库存辅助函数（services.py）
- **`validate_inventory_availability(session, request_items)`**: 校验申请的物料在特定仓库中是否有足够的可用库存。
- **`get_sku_agreement_price(session, sc_id, business_id, sku_name)`**: 查询供应链协议中的 SKU 定价。

---

## 10. 文件管理与批量操作 API

**模块路径：** `logic/file_mgmt.py`

- **`generate_master_data_excel(session)`**: 导出全量的基础数据 Excel 模板（带数据验证与联动下拉）。
- **`process_master_data_excel(session, file_bytes)`**: 解析并入库上传的基础数据。
- **`save_contract_files(contract_id, uploaded_files)`**: 保存合同相关的附件文件。
- **`get_contract_files(contract_id)`**: 获取指定合同的所有附件列表。

---

## 11. 押金与池核销 API

**模块路径：** `logic/deposit.py`、`logic/offset_manager.py`

- **`deposit_module(vc_id=None, cf_id=None, session=None)`**: 押金处理入口函数。根据参数触发 `process_cf_deposit` 或 `process_vc_deposit`。
- **`process_cf_deposit(session, cf_id)`**: 处理单笔押金资金流（处理退货 VC 押金重定向到原合同）。
- **`process_vc_deposit(session, vc_id)`**: 重算 VC 应收押金（`should_receive`），按 SKU 级别运营设备数量重新分配押金，触发自动完结。
- **`apply_offset_to_vc(session, vc_id)`**: 将预收/预付池余额自动核销到指定 VC。

---

## 12. 操作事务与回滚 (Transactions) API

**模块路径：** `logic/transactions.py`

> 所有 Action 在执行成功后会创建 `OperationTransaction` 记录，存储 `snapshot_before`/`snapshot_after` 快照，支持回滚和撤销回滚。

### 事务操作
- **`create_operation_record(session, action_name, ref_type, ref_id, ref_vc_id, snapshot_before, snapshot_after, involved_ids)`**: 创建事务记录。
- **`rollback_operation(session, tx_id, reason)`**: 执行回滚，用 snapshot_before 恢复所有表。
- **`redo_operation(session, tx_id)`**: 撤销回滚，用 snapshot_after 重新应用。

### 凭证文件操作
- **`update_report(voucher, report_dir=None)`**: 幂等追加凭证到 report.json（按 voucher_no 去重）。
- **`void_report(ref_type, ref_id, transaction_date, report_dir=None)`**: 从 report.json 中移除指定凭证条目（幂等）。

---

## 调用示例 (Python)

```python
from logic.vc import create_procurement_vc_action, get_vc_list, VCElementSchema
from logic.business import advance_business_stage_action, AdvanceBusinessStageSchema
from logic.master import get_system_constants
from logic.services import calculate_cashflow_progress

# 1. 查询系统常量
constants = get_system_constants()

# 2. 创建设备采购 VC（v5.0 使用 elements）
elements = [
    VCElementSchema(
        shipping_point_id=1,
        receiving_point_id=2,
        sku_id=101,
        qty=5,
        price=2000.0,
        deposit=500.0,
        subtotal=10000.0
    )
]
payload = CreateProcurementVCSchema(
    business_id=1,
    elements=elements,
    total_amt=10000.0,
    total_deposit=2500.0,
    payment={"terms": "月结30"}
)
res = create_procurement_vc_action(session, payload)

# 3. 推进业务阶段
advance_payload = AdvanceBusinessStageSchema(business_id=1, target_stage="ACTIVE")
advance_business_stage_action(session, advance_payload)
```
