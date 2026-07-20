# 闪饮 ERP 系统 API 手册 (v4.1)

> [!IMPORTANT]
> 本文档包含 ShanYin ERP 系统 `logic` 层的所有公开 API 函数。本文档旨在实现 100% 的功能覆盖，确保所有 UI 操作均可通过对应的 API 逻辑实现。

## 1. 基础数据 (Master Data) API

### 1.1 客户管理 (Customers)
- **`create_customer_action(session, payload)`**: 创建新客户。
- **`update_customers_action(session, payloads)`**: 批量更新客户信息。
- **`delete_customers_action(session, payloads)`**: 批量删除客户。
- **`get_customers_for_ui(limit=100)`**: 获取供 UI 展示的客户列表。
- **`get_customer_by_id(customer_id)`**: 根据 ID 获取客户详细信息。

### 1.2 供应商管理 (Suppliers)
- **`create_supplier_action(session, payload)`**: 创建新供应商。
- **`update_suppliers_action(session, payloads)`**: 批量更新供应商信息。
- **`delete_suppliers_action(session, payloads)`**: 批量删除供应商。
- **`get_suppliers_for_ui(limit=100)`**: 获取供 UI 展示的供应商列表。
- **`get_supplier_by_id(supplier_id)`**: 根据 ID 获取供应商详细信息。
- **`get_supplier_by_name(name)`**: 根据名称查找供应商。

### 1.3 点位与仓库 (Points)
- **`create_point_action(session, payload)`**: 创建新点位/仓库。
- **`update_points_action(session, payloads)`**: 批量更新点位信息。
- **`delete_points_action(session, payloads)`**: 批量删除点位。
- **`get_points_for_ui(search_keyword=None, limit=100)`**: 获取点位列表，支持关键词搜索。
- **`get_point_by_id(point_id)`**: 根据 ID 获取点位详情。
- **`get_warehouse_points()`**: 获取所有仓库类型的点位。
- **`get_points_by_customer(customer_id)`**: 获取特定客户关联的所有点位。

### 1.4 商品与 SKU (SKUs)
- **`create_sku_action(session, payload)`**: 创建新 SKU。
- **`update_skus_action(session, payloads)`**: 批量更新 SKU 信息。
- **`delete_skus_action(session, payloads)`**: 批量删除 SKU。
- **`get_skus_for_ui(limit=200)`**: 获取 SKU 列表。
- **`get_sku_map_by_names(names)`**: 根据名称列表获取 SKU ID 映射。
- **`get_skus_by_names(names)`**: 根据名称列表获取 SKU 对象列表。

### 1.5 外部合作方 (Partners)
- **`create_partner_action(session, payload)`**: 创建新外部合作方。
- **`update_partners_action(session, payloads)`**: 批量更新合作方信息。
- **`delete_partners_action(session, payloads)`**: 批量删除合作方。
- **`get_partners_for_ui(limit=100)`**: 获取合作方列表。
- **`get_partner_by_id(partner_id)`**: 根据 ID 获取合作方详情。

### 1.6 银行账户 (Bank Accounts)
- **`create_bank_account_action(session, payload)`**: 创建新的银行账户。
- **`update_bank_accounts_action(session, payloads)`**: 批量更新银行账户信息。
- **`get_bank_accounts_for_ui(owner_type=None, owner_id=None)`**: 获取指定主体的银行账户列表。
- **`get_bank_account_by_id(account_id)`**: 根据 ID 获取账户详情。

---

## 2. 业务管理 (Business Management) API

- **`create_business_action(session, payload)`**: 启动新的业务项（如：前期接洽）。
- **`update_business_status_action(session, payload)`**: 更新业务项状态（终止、暂缓等）。
- **`delete_business_action(session, business_id)`**: 删除业务项（仅限无关联数据时）。
- **`advance_business_stage_action(session, payload)`**: 推进业务阶段（如：从“评估”到“落地”），并支持自动生成时间规则和合同。
- **`get_business_list(status=None, customer_id=None, limit=100)`**: 按状态或客户筛选业务列表。
- **`get_business_detail(business_id)`**: 获取业务项的完整视图，包括关联合同。
- **`get_businesses_for_execution()`**: 获取所有处于“落地”或“开展”阶段的业务。

---

## 3. 虚拟合同 (Virtual Contracts) API

- **`create_procurement_vc_action(session, payload)`**: 创建设备采购类虚拟合同。
- **`create_material_supply_vc_action(session, payload)`**: 创建物料供应类虚拟合同。
- **`create_stock_procurement_vc_action(session, payload)`**: 创建库存采购类虚拟合同。
- **`create_return_vc_action(session, payload)`**: 创建退货类虚拟合同。
- **`bulk_allocate_inventory_action(session, vc_id, allocations)`**: 批量进行库存拨付/锁定。
- **`delete_vc_action(session, vc_id)`**: 删除虚拟合同。
- **`get_vc_list_for_ui(vc_type=None, status=None, limit=100)`**: 获取虚拟合同列表。
- **`get_vc_detail_for_ui(vc_id)`**: 获取虚拟合同的完整明细（含货品、资金、物流进度）。

---

## 4. 供应链 (Supply Chain) API

- **`create_supply_chain_action(session, payload)`**: 创建供应链框架协议。
- **`delete_supply_chain_action(session, sc_id)`**: 删除供应链。
- **`get_supply_chains_by_type(sc_type)`**: 按类型（直供/经销等）获取供应链列表。
- **`get_supply_chain_by_id(sc_id)`**: 获取供应链详细信息。

---

## 5. 财务与资金流 (Finance) API

- **`create_cash_flow_action(session, payload)`**: 录入资金收付、押金及退款流水。
- **`internal_transfer_action(session, payload)`**: 执行内部账户间的资金划拨。
- **`external_fund_action(session, payload)`**: 记录非业务类的外部出入金操作。
- **`get_account_list_for_ui(has_balance_only=True)`**: 获取会计科目余额表。
- **`get_journal_entries_for_ui(account_id=None, limit=50)`**: 获取详细的记账凭证历史。
- **`get_fund_operation_history_for_ui(limit=50)`**: 获取资金划拨的历史操作记录。
- **`get_cash_flow_list_for_ui(vc_id=None, limit=100)`**: 获取指定合同或全局的资金流记录。
- **`get_dashboard_stats()`**: 获取财务看板的核心统计汇总数据。

---

## 6. 物流管理 (Logistics) API

- **`create_logistics_plan_action(session, payload)`**: 创建发货计划（物流单及快递子单）。
- **`confirm_inbound_action(session, payload)`**: 确认收货入库，并自动触发库存变更与财务凭证。
- **`update_express_order_action(session, payload)`**: 修改快递单的单号或地址。
- **`update_express_order_status_action(session, payload)`**: 推进快递单状态（待发货 -> 运输中 -> 已签收）。
- **`bulk_progress_express_orders_action(session, order_ids, target_status, logistics_id)`**: 批量推进快递单状态。
- **`get_logistics_list_for_ui(status_list=None, vc_id=None)`**: 获取物流任务列表。
- **`get_logistics_dashboard_summary()`**: 获取物流看板的汇总统计。

---

## 7. 时间规则 (Time Rules) API

- **`save_rule_action(session, payload)`**: 保存或编辑时间偏置规则（用于自动产生下游任务）。
- **`delete_rule_action(session, rule_id)`**: 删除特定的时间规则。
- **`persist_draft_rules_action(session, draft_rules, related_type, related_id)`**: 将从合同模板或界面生成的草稿规则持久化到数据库。
- **`get_time_rule_list(related_id, related_type)`**: 获取特定关联对象的所有动态规则。

---

## 8. 文件管理与批量操作 (File & Bulk) API

- **`generate_master_data_excel(session)`**: 导出全量的基础数据 Excel 模板（带数据验证与联动下拉）。
- **`process_master_data_excel(session, file_bytes)`**: 解析并入库上传的基础数据。
- **`save_contract_files(contract_id, uploaded_files)`**: 保存合同相关的附件文件。
- **`get_contract_files(contract_id)`**: 获取指定合同的所有附件列表。

---

## 9. 核心辅助与系统服务 API

- **`get_system_constants()`**: 获取系统全局常量映射表（供前端构建下拉选择器）。
- **`calculate_cashflow_progress(session, vc)`**: 深度计算虚拟合同的收款进度、实时应付及冲抵池状态。
- **`get_account_balance(session, level1_name, cp_type=None, cp_id=None)`**: 查询特定科目的实时余额（含对手方维度）。
- **`format_vc_items_for_display(vc)`**: 将复杂的合同 JSON 结构转换为 UI 表格友好的渲染格式。
- **`get_returnable_items(session, target_vc_id, return_direction)`**: 智能计算合同中当前“可退货”的货品范围与数量。
- **`validate_inventory_availability(session, request_items)`**: 校验申请的物料在特定仓库中是否有足够的可用库存。

---

## 10. 库存统计 (Inventory Stats) API

- **`get_equipment_inventory_summary()`**: 获取设备库存在不同地点的汇总统计。
- **`get_material_inventory_summary()`**: 获取物料库存的全域汇总统计。
- **`get_equipment_inventory_list(limit=1000)`**: 获取全量设备 SN 档案列表。
- **`get_stock_equipment_for_allocation(points_list)`**: 获取特定仓库中可供拨付的空闲设备。
- **`get_material_stock_for_supply(points_list)`**: 获取特定仓库中可供供应的物料存量。

---

## 调用示例 (Python)

```python
from logic.master.queries import get_customers_for_ui
from logic.business.actions import create_business_action
from logic.master.schemas import CreateBusinessSchema

# 1. 查询
customers = get_customers_for_ui(limit=10)

# 2. 写入 (需传入 SQLAlchemy session)
res = create_business_action(session, CreateBusinessSchema(customer_id=1, ...))
if res.success:
    print(f"成功创建业务 ID: {res.data['business_id']}")
```
