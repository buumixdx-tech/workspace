"""
兼容性模块：重定向旧版 actions 导入到新架构

将 logic.actions.* 重定向到新的领域模块：
- logic.actions.business_actions -> logic.business.actions
- logic.actions.finance_actions -> logic.finance.actions
- logic.actions.logistics_actions -> logic.logistics.actions
- logic.actions.master_actions -> logic.master.actions
- logic.actions.vc_actions -> logic.vc.actions
- logic.actions.supply_chain_actions -> logic.supply_chain.actions
"""

# Business Actions
from logic.business.actions import (
    create_business_action,
    update_business_status_action,
    delete_business_action,
    advance_business_stage_action
)

# 兼容性别名
update_business_action = update_business_status_action
update_business_pricing_action = advance_business_stage_action

# Finance Actions
from logic.finance.actions import (
    create_cash_flow_action,
    internal_transfer_action,
    external_fund_action,
    create_bank_account_action,
    update_bank_accounts_action
)

# Logistics Actions
from logic.logistics.actions import (
    create_logistics_plan_action,
    confirm_inbound_action,
    update_express_order_action,
    update_express_order_status_action
)

# 兼容性别名
create_logistics_action = create_logistics_plan_action
update_logistics_action = confirm_inbound_action # 这里的 mapping 取决于旧版含义，通常是推进状态或入库

# Master Actions
from logic.master.actions import (
    create_customer_action,
    create_supplier_action,
    create_sku_action,
)
update_customer_action = None  # 兼容旧引用，实际使用 update_customers_action
update_supplier_action = None
update_sku_action = None
from logic.master.actions import (
    update_customers_action,
    update_suppliers_action,
    update_skus_action,
)

# VC Actions
from logic.vc.actions import (
    create_procurement_vc_action,
    update_vc_action,
    delete_vc_action,
    create_return_vc_action,
    create_material_supply_vc_action,
    create_mat_procurement_vc_action,
    create_stock_procurement_vc_action
)

# 兼容性别名
create_vc_action = create_procurement_vc_action

# Supply Chain Actions
from logic.supply_chain.actions import (
    create_supply_chain_action
)

# Rule Actions
from logic.time_rules.actions import (
    save_rule_action,
    delete_rule_action,
)

__all__ = [
    # Business
    'create_business_action',
    'update_business_action',
    'delete_business_action',
    'update_business_pricing_action',
    # Finance
    'create_cash_flow_action',
    'internal_transfer_action',
    'external_fund_action',
    'create_bank_account_action',
    'update_bank_accounts_action',
    # Logistics
    'create_logistics_action',
    'update_logistics_action',
    'create_express_order_action',
    'update_express_order_action',
    # Master
    'create_customer_action',
    'update_customer_action',
    'create_supplier_action',
    'update_supplier_action',
    'create_sku_action',
    'update_sku_action',
    # VC
    'create_vc_action',
    'update_vc_action',
    'delete_vc_action',
    'create_return_vc_action',
    # Supply Chain
    'create_supply_chain_action',
    'update_supply_chain_action',
    'delete_supply_chain_action',
    # Rule
    'save_rule_action',
    'delete_rule_action',
]
