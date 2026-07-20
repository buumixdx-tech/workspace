import html
import streamlit as st
from models import get_session, SKU
import pandas as pd
import streamlit_antd_components as sac
import plotly.graph_objects as go
from datetime import datetime
from logic.constants import (
    VCType, VCStatus, SubjectStatus, CashStatus, ReturnDirection, CashFlowType,
    BusinessStatus, ContractStatus, SettlementRule, DeviceStatus, OperationalStatus, LogisticsBearer,
    SKUType, SystemConstants
)
from logic.offset_manager import apply_offset_to_vc
from logic.services import get_returnable_items, get_sku_agreement_price, validate_inventory_availability, normalize_item_data, format_vc_items_for_display
from logic.time_rules import RuleManager
from logic.supply_chain import create_supply_chain_action, CreateSupplyChainSchema, UpdateSupplyChainSchema, DeleteSupplyChainSchema
from logic.master import (
    create_customer_action, update_customers_action, delete_customers_action,
    create_point_action, update_points_action, delete_points_action,
    create_sku_action, update_skus_action, delete_skus_action,
    create_supplier_action, update_suppliers_action, delete_suppliers_action,
    create_partner_action, update_partners_action, delete_partners_action
)
from logic.vc.queries import (
    get_virtual_contracts_for_return, get_vc_detail_with_logs, get_vc_list_for_overview,
    get_vc_count_by_business, get_vc_status_logs, get_vc_cash_flows, get_returnable_vcs,
    get_vc_list, get_vc_detail,
    get_valid_receiving_points_for_procurement,
    get_valid_receiving_points_for_mat_procurement, get_valid_shipping_points_for_mat_procurement,
    get_valid_receiving_points_for_material_supply, get_valid_shipping_points_for_material_supply,
    get_valid_receiving_points_for_allocation, get_valid_shipping_points_for_allocation,
    get_valid_shipping_points_for_return_equipment, get_valid_shipping_points_for_return_mat,
    get_valid_receiving_points_for_return,
)
from logic.logistics.queries import (
    get_logistics_list_by_vc, get_logistics_dashboard_summary
)
from logic.finance.queries import get_cash_flow_list_for_ui
from logic.supply_chain.queries import (
    get_supply_chain_with_pricing, get_supply_chain_detail_for_ui,
    get_supply_chains_for_ui as get_supply_chains,
    get_supply_chain_detail_for_ui as get_supply_chain_detail
)
from logic.time_rules.queries import (
    get_inherited_time_rules, get_time_rules_for_ui, get_inherited_rules_for_ui
)
from logic.master.queries import (
    get_equipment_inventory_summary, get_material_inventory_summary,
    get_equipment_inventory_list, get_material_inventory_list,
    get_warehouse_points, get_sku_map_by_names,
    get_stock_equipment_for_allocation, get_material_stock_for_supply,
    get_customers_for_ui as get_customers,
    get_suppliers_for_ui as get_suppliers,
    get_skus_for_ui as get_skus,
    get_points_for_ui,
    get_partners_for_ui as get_partners,
    get_bank_accounts_for_ui as get_bank_accounts,
    get_points_by_customer, get_skus_by_names, get_material_inventory_all,
    get_supply_chains_by_type, get_supply_chain_by_id,
    get_contract_detail, get_material_movement_timeline,
)
from logic.business import (
    create_business_action, update_business_status_action, 
    delete_business_action, advance_business_stage_action,
    get_business_list, get_business_detail, get_businesses_for_execution,
    CreateBusinessSchema, UpdateBusinessStatusSchema, AdvanceBusinessStageSchema
)
from logic.vc import (
    create_procurement_vc_action, create_material_supply_vc_action,
    create_return_vc_action, create_mat_procurement_vc_action,
    update_vc_action, delete_vc_action,
    create_stock_procurement_vc_action, create_inventory_allocation_action,
    CreateProcurementVCSchema, VCItemSchema, CreateMaterialSupplyVCSchema,
    CreateReturnVCSchema, CreateMatProcurementVCSchema,
    CreateStockProcurementVCSchema, AllocateInventorySchema, VCElementSchema
)
from logic.addon_business import (
    create_addon_business_action,
    update_addon_business_action,
    deactivate_addon_business_action,
    get_business_addons,
    get_active_addons,
    get_addon_detail,
)
from logic.addon_business.queries import sku_exists_in_business, get_original_price_and_deposit
from logic.addon_business.schemas import CreateAddonSchema, UpdateAddonSchema
from logic.constants import AddonType, AddonStatus

def _save_procurement_vc(_session, business_id, data):
    """
    抽取的设备采购保存逻辑 (辅助 confirm_procurement_dialog)
    现在通过 standardized Action 执行，UI 只负责数据准备与状态清理
    """
    # 1. 准备 Action Payload
    # 新结构使用 VCElementSchema: (shipping_point_id, receiving_point_id, sku_id, qty, price, deposit, subtotal, sn_list)
    elems_payload = []
    for i in data['items']:
        norm = normalize_item_data(i)
        qty = float(norm.get('qty') or 0)
        price = float(norm.get('price') or 0)
        deposit = float(norm.get('deposit') or 0)
        elem = VCElementSchema(
            shipping_point_id=int(norm.get('shipping_point_id') or 0),
            receiving_point_id=int(norm.get('receiving_point_id') or norm.get('point_id') or 0),
            sku_id=int(norm.get('sku_id') or 0),
            qty=qty,
            price=price,
            deposit=deposit,
            subtotal=qty * price,
            sn_list=[norm.get('sn')] if norm.get('sn') and norm.get('sn') != '-' else []
        )
        elems_payload.append(elem)

    payload = CreateProcurementVCSchema(
        business_id=business_id,
        sc_id=data['sc_id'],
        elements=elems_payload,
        total_amt=data['total_amt'],
        total_deposit=data['total_deposit'],
        payment=data['payment'],
        description=data.get('description', '')
    )
    
    # 2. 获取草稿规则 (从 Session State 获取并传入 Action)
    draft_key = f"proc_{business_id}"
    draft_rules = st.session_state.get(f"draft_rules_{draft_key}", [])
    
    # 3. 调用逻辑内核
    result = create_procurement_vc_action(_session, payload, draft_rules=draft_rules)
    
    if result.success:
        # 4. 清理 UI 相关的状态
        if f"temp_proc_data_{business_id}" in st.session_state: del st.session_state[f"temp_proc_data_{business_id}"]
        if f"proc_df_{business_id}" in st.session_state: del st.session_state[f"proc_df_{business_id}"]
        # 清理草稿规则相关的 UI 状态 (封装在 persist_draft_rules 逻辑中)
        if f"draft_rules_{draft_key}" in st.session_state: del st.session_state[f"draft_rules_{draft_key}"]
        for k in list(st.session_state.keys()):
            if k.startswith(f"draft_") and draft_key in k:
                del st.session_state[k]
        
        return result.data["vc_id"]
    else:
        st.session_state[f"supply_error_{business_id}"] = result.error
        return None

@st.dialog("核心业务：确认设备采购执行单", width="large")
def confirm_procurement_dialog(session, business_id):
    biz = get_business_detail(business_id)
    data = st.session_state.get(f"temp_proc_data_{business_id}")
    if not data:
        st.error("数据丢失，请重新录入")
        if st.button("返回"): 
            st.session_state[f"show_proc_confirm_{business_id}"] = False
            st.rerun()
        return

    st.write("请核对以下设备采购清单及规则配置。点击“确认执行”后将正式生成核算单。")
    
    # 概览
    c1, c2, c3 = st.columns(3)
    c1.metric("关联客户", biz.get('customer_name', SystemConstants.UNKNOWN))
    c2.metric("采购总额", f"¥{data['total_amt']:,.2f}")
    c3.metric("应收总押金", f"¥{data['total_deposit']:,.2f}")

    # 1. 明细
    st.markdown("#### <i class='bi bi-box-seam'></i> 部署计划明细", unsafe_allow_html=True)
    df_preview = pd.DataFrame(data['items'])
    df_preview.columns = ["SKU ID", "品类名称", "点位 ID", "部署点位", "数量", "执行单价", "单台押金"]
    st.table(df_preview[["部署点位", "品类名称", "数量", "执行单价", "单台押金"]])

    # 2. 规则
    # 移除追加规则预览
    st.divider()
    
    c_sub1, c_sub2 = st.columns([2, 1])
    with c_sub1:
        if st.button("最终确认：下达执行单", type="primary", use_container_width=True):
            new_vc = _save_procurement_vc(session, business_id, data)
            st.success("✅ 采购核算单已成功下达！")
            st.session_state[f"show_proc_confirm_{business_id}"] = False
            st.rerun()

    with c_sub2:
        if st.button("返回修改", use_container_width=True):
            st.session_state[f"show_proc_confirm_{business_id}"] = False
            st.rerun()

def _save_material_supply_vc(_session, business_id, data):
    """辅助物料供应保存，通过 Action 执行"""
    order = data['order']
    # 将 flat items 结构直接映射为 elements（与其他 VC 类型一致）
    elems_payload = []
    for i in order.get('items', []):
        norm = normalize_item_data(i)
        qty = float(norm.get('qty') or 0)
        price = float(norm.get('price') or 0)
        elem = VCElementSchema(
            shipping_point_id=int(norm.get('shipping_point_id') or 0),
            receiving_point_id=int(norm.get('receiving_point_id') or 0),
            sku_id=int(norm.get('sku_id') or 0),
            batch_no=norm.get('batch_no') or None,
            qty=qty,
            price=price,
            deposit=0.0,
            subtotal=qty * price,
            sn_list=[]
        )
        elems_payload.append(elem)

    payload = CreateMaterialSupplyVCSchema(
        business_id=business_id,
        elements=elems_payload,
        total_amt=order.get('total_amount', 0),
        description=data.get('description', '')
    )
    
    draft_key = f"supply_{business_id}"
    draft_rules = st.session_state.get(f"draft_rules_{draft_key}", [])
    
    result = create_material_supply_vc_action(_session, payload, draft_rules=draft_rules)
    
    if result.success:
        # 清理 UI 状态
        if f"temp_supply_data_{business_id}" in st.session_state: del st.session_state[f"temp_supply_data_{business_id}"]
        if f"supply_df_{business_id}" in st.session_state: del st.session_state[f"supply_df_{business_id}"]
        if f"draft_rules_{draft_key}" in st.session_state: del st.session_state[f"draft_rules_{draft_key}"]
        for k in list(st.session_state.keys()):
            if k.startswith(f"draft_") and draft_key in k:
                del st.session_state[k]
        
        return result.data["vc_id"]
    else:
        st.session_state[f"supply_error_{business_id}"] = result.error
        return None

@st.dialog("确认物料供应执行单", width="large")
def confirm_material_supply_dialog(session, business_id):
    biz = get_business_detail(business_id)
    data = st.session_state.get(f"temp_supply_data_{business_id}")
    if not data:
        st.error("数据丢失")
        if st.button("返回"):
            st.session_state[f"show_supply_confirm_{business_id}"] = False
            st.rerun()
        return

    st.write("请核对以下物料供应清单及规则。确认后将立即在各个发货点位扣减相应物料库存并生成应收。")

    # 显示之前的错误信息
    err_key = f"supply_error_{business_id}"
    if err_key in st.session_state:
        st.error(st.session_state[err_key])
        del st.session_state[err_key]
    
    order = data['order']
    c1, c2, c3 = st.columns(3)
    c1.metric("关联客户", biz.get('customer_name', SystemConstants.UNKNOWN))
    c2.metric("供应总额", f"¥{order['total_amount']:,.2f}")
    c3.metric("品类总数", f"{len(order['summary']['sku_summary_list'])} 类")

    st.markdown("#### <i class='bi bi-truck'></i> 发货点位明细", unsafe_allow_html=True)
    # 扁平化展示所有明细（统一从 flat items 读取）
    flat_items = []
    for item in order.get('items', []):
        ni = normalize_item_data(item)
        flat_items.append({
            "收货点位": ni.get("receiving_point_name") or SystemConstants.UNKNOWN,
            "物料名称": ni["sku_name"],
            "批次号": ni.get("batch_no") or "-",
            "数量": ni["qty"],
            "单价": ni["price"],
            "金额": ni["qty"] * ni["price"],
            "发货点位": ni.get("shipping_point_name") or SystemConstants.DEFAULT_POINT
        })
    st.table(pd.DataFrame(flat_items))

    # 展示追加规则
    # 移除追加规则预览
    st.divider()
    c_sub1, c_sub2 = st.columns([2, 1])
    with c_sub1:
        if st.button("最终确认：提交供应并出库", type="primary", use_container_width=True):
            vc_id = _save_material_supply_vc(session, business_id, data)
            if vc_id:
                st.success("服务核算单已成功下达！")
                st.session_state[f"show_supply_confirm_{business_id}"] = False
                # 重置提交状态，下次可正常新建
                submitted_key = f"supply_row_{business_id}_submitted"
                if submitted_key in st.session_state:
                    st.session_state[submitted_key] = False
                st.rerun()

    with c_sub2:
        if st.button("返回修改", use_container_width=True):
            st.session_state[f"show_supply_confirm_{business_id}"] = False
            st.session_state[f"supply_row_{business_id}_submitted"] = False
            st.rerun()

def _save_mat_procurement_vc(_session, sc_id, data):
    """辅助物料采购保存，通过 Action 执行"""
    elems_payload = []
    for i in data['items']:
        norm = normalize_item_data(i)
        qty = float(norm.get('qty') or 0)
        price = float(norm.get('price') or 0)
        elem = VCElementSchema(
            shipping_point_id=int(norm.get('shipping_point_id') or 0),
            receiving_point_id=int(norm.get('receiving_point_id') or norm.get('point_id') or 0),
            sku_id=int(norm.get('sku_id') or 0),
            qty=qty,
            price=price,
            deposit=0.0,
            subtotal=qty * price,
            sn_list=[]
        )
        elems_payload.append(elem)

    payload = CreateMatProcurementVCSchema(
        sc_id=sc_id,
        elements=elems_payload,
        total_amt=data['total_amt'],
        payment=data['payment'],
        description=data.get('description')
    )
    
    draft_key = f"mat_proc_{sc_id}"
    draft_rules = st.session_state.get(f"draft_rules_{draft_key}", [])
    
    result = create_mat_procurement_vc_action(_session, payload, draft_rules=draft_rules)
    
    if result.success:
        # 清理 UI 状态
        st.session_state["show_mat_proc_confirm"] = False
        st.session_state["mat_proc_confirm_dialog_open"] = False
        if "temp_mat_proc_data" in st.session_state: del st.session_state["temp_mat_proc_data"]
        if "mat_proc_df" in st.session_state: del st.session_state["mat_proc_df"]
        if "mat_proc_extra_rules" in st.session_state: del st.session_state["mat_proc_extra_rules"]
        if f"draft_rules_{draft_key}" in st.session_state: del st.session_state[f"draft_rules_{draft_key}"]
        for k in list(st.session_state.keys()):
            if k.startswith(f"draft_") and draft_key in k:
                del st.session_state[k]
        
        return result.data["vc_id"]
    else:
        st.session_state[f"supply_error_{sc_id}"] = result.error
        return None

@st.dialog("确认物料采购执行单", width="large")
def confirm_mat_procurement_dialog(session, sc_id):
    st.session_state["mat_proc_confirm_dialog_open"] = True
    sc = get_supply_chain_detail(sc_id)
    data = st.session_state.get(f"temp_mat_proc_data")
    if not data:
        st.error("数据丢失")
        if st.button("返回"):
            st.session_state[f"show_mat_proc_confirm"] = False
            st.session_state["mat_proc_confirm_dialog_open"] = False
            st.rerun()
        return

    st.write(f"正在从供应商 **{sc['supplier']['name']}** 采购以下物料，请最后核对。")
    
    st.metric("采购总额", f"¥{data['total_amt']:,.2f}")
    
    st.markdown("#### <i class='bi bi-list-task'></i> 采购条目明细", unsafe_allow_html=True)
    norm_items = [normalize_item_data(i) for i in data['items']]
    df_p = pd.DataFrame(norm_items)
    df_preview = df_p.rename(columns={
        "sku_name": "品类名称",
        "qty": "数量",
        "price": "单价",
        "receiving_point_name": "存放点位"
    })
    st.table(df_preview[["品类名称", "数量", "单价", "存放点位"]])

    # 展示追加规则
    # 移除追加规则预览
    st.divider()
    c_sub1, c_sub2 = st.columns([2, 1])
    with c_sub1:
        if st.button("最终确认：生成执行合同", type="primary", use_container_width=True):
            _save_mat_procurement_vc(session, sc_id, data)
            st.success("采购合同已正式确认")
            st.rerun()

    with c_sub2:
        if st.button("返回修改", use_container_width=True):
            st.session_state["show_mat_proc_confirm"] = False
            st.session_state["mat_proc_confirm_dialog_open"] = False
            st.rerun()


def _save_return_vc(_session, target_vc_id, data):
    """辅助退货保存，通过 Action 执行"""
    elems_payload = []
    for i in data['return_items']:
        norm = normalize_item_data(i)
        qty = float(norm.get('qty') or 0)
        price = float(norm.get('price') or 0)
        elem = VCElementSchema(
            shipping_point_id=int(norm.get('shipping_point_id') or norm.get('point_id') or 0),
            receiving_point_id=int(norm.get('receiving_point_id') or 0),
            sku_id=int(norm.get('sku_id') or 0),
            qty=qty,
            price=price,
            deposit=0.0,
            subtotal=qty * price,
            sn_list=[norm.get('sn')] if norm.get('sn') and norm.get('sn') != '-' else []
        )
        elems_payload.append(elem)

    payload = CreateReturnVCSchema(
        target_vc_id=target_vc_id,
        return_direction=data['return_direction'],
        elements=elems_payload,
        goods_amount=data['goods_amount'],
        deposit_amount=data['deposit_amount'],
        logistics_cost=data['logistics_cost'],
        logistics_bearer=data['logistics_bearer'],
        total_refund=data['total_refund'],
        reason=data['reason'],
        description=data['description']
    )
    
    draft_key = f"return_{target_vc_id}"
    draft_rules = st.session_state.get(f"draft_rules_{draft_key}", [])
    
    result = create_return_vc_action(_session, payload, draft_rules=draft_rules)
    
    if result.success:
        # 清理 UI 状态
        st.session_state[f"show_return_confirm_{target_vc_id}"] = False
        if f"temp_return_data_{target_vc_id}" in st.session_state: del st.session_state[f"temp_return_data_{target_vc_id}"]
        if f"draft_rules_{draft_key}" in st.session_state: del st.session_state[f"draft_rules_{draft_key}"]
        for k in list(st.session_state.keys()):
            if k.startswith(f"draft_") and draft_key in k:
                del st.session_state[k]
        
        # 清理编辑器状态
        r_dir = data.get('return_direction')
        if r_dir:
            r_key = f"return_df_v2_{target_vc_id}_{r_dir}"
            if r_key in st.session_state: del st.session_state[r_key]
        
        return result.data["vc_id"]
    else:
        st.session_state[f"supply_error_{target_vc_id}"] = result.error
        return None
@st.dialog("确认退货执行单召回", width="large")
def confirm_return_dialog(session, target_vc_id):
    target_vc = get_vc_detail(target_vc_id)
    data = st.session_state.get(f"temp_return_data_{target_vc_id}")
    if not data:
        st.error("数据丢失")
        if st.button("返回"):
            st.session_state[f"show_return_confirm_{target_vc_id}"] = False
            st.rerun()
        return

    st.write("请从业务角度核对退货明细及规则配置。")
    
    # 核心指标
    c1, c2, c3 = st.columns(3)
    c1.info(f"**退货流向**\n{data['return_direction']}")
    
    is_deposit_only = (target_vc['type'] == VCType.EQUIPMENT_PROCUREMENT and ReturnDirection.CUSTOMER_TO_US in data['return_direction'])
    amount_label = "预计退款(或抵扣)" if not is_deposit_only else "预计退还押金"
    
    c2.metric(amount_label, f"¥{data['total_refund']:,.2f}")
    c3.metric("物流费用", f"¥{data['logistics_cost']:,.2f}", delta=f"({data['logistics_bearer']})", delta_color="normal")

    st.markdown("#### <i class='bi bi-box-arrow-right'></i> 拟退货物品清单", unsafe_allow_html=True)
    df_ret = pd.DataFrame(data['return_items'])
    # 映射列名以便预览
    df_preview = df_ret.rename(columns={
        "sku_name": "SKU",
        "sn": "SN码",
        "batch_no": "批次",
        "qty": "数量",
        "price": "执行单价",
        "deposit": "押金",
        "point_name": "当前所在位置",
        "target_warehouse": "退回目的地"  # 字段 key 不变，兼容已有数据
    })

    cols_to_show = ["SKU", "SN码", "批次", "数量", "当前所在位置", "退回目的地"]
    if is_deposit_only: cols_to_show.append("押金")
    else: cols_to_show.append("单价")
    
    st.table(df_preview[cols_to_show])

    # 移除追加规则预览
    st.divider()
    
    if data['reason']:
        st.info(f"**退货原因/备注**: {data['reason']}")

    st.divider()
    c_sub1, c_sub2 = st.columns([2, 1])
    with c_sub1:
        if st.button("最终确认：发起退货流转", type="primary", use_container_width=True):
            _save_return_vc(session, target_vc_id, data)
            st.success("退货流转已正式发起")
            st.rerun()

    with c_sub2:
        if st.button("返回修改", use_container_width=True):
            st.session_state[f"show_return_confirm_{target_vc_id}"] = False
            st.rerun()

# --- 附加业务管理模块 ---
def show_addon_management_page(session):
    """附加业务管理顶级页面"""
    st.markdown("### <i class='bi bi-plus-circle'></i> 附加业务管理", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 业务选择（仅 ACTIVE）
    # ------------------------------------------------------------------
    all_biz = get_businesses_for_execution()
    # 只保留 ACTIVE
    businesses = [b for b in all_biz if b["status"] == BusinessStatus.ACTIVE]
    if not businesses:
        st.info("当前无进行中的业务（ACTIVE 阶段），请先创建或推进业务至 ACTIVE。")
        return

    biz_options = {str(b["id"]): f"{b['id']} - {b.get('customer_name', '未知')}" for b in businesses}
    sel_biz_id = st.selectbox(
        "选择业务",
        options=list(biz_options.keys()),
        format_func=lambda bid: biz_options[bid],
        key="addon_biz_selector",
    )
    business_id = int(sel_biz_id)
    biz = get_business_detail(business_id)

    if biz['status'] != BusinessStatus.ACTIVE:
        st.warning(f"⚠️ 业务当前阶段「{biz['status']}」不允许管理附加项，仅可在 ACTIVE 阶段操作。")
        return

    # ------------------------------------------------------------------
    # 模式管理：None / "create" / "edit"
    # ------------------------------------------------------------------
    MODE_KEY = f"addon_mode_{business_id}"
    EDIT_ID_KEY = f"addon_edit_id_{business_id}"
    mode = st.session_state.get(MODE_KEY, None)

    # ------------------------------------------------------------------
    # addon 列表
    # ------------------------------------------------------------------
    active = get_active_addons(session, business_id)
    all_addons = get_business_addons(session, business_id, include_expired=True)

    list_tab_label = sac.tabs([
        sac.TabsItem(f"生效中 ({len(active)})", icon="lightning-charge"),
        sac.TabsItem(f"全部记录 ({len(all_addons)})", icon="list-ul"),
    ], align="left", variant="capsule", key=f"addon_listtabs_{business_id}")

    display_list = active if list_tab_label.startswith("生效") else all_addons

    sku_map = {str(s.id): s.name for s in session.query(SKU).all()}

    def _addon_row(a):
        sku_name = sku_map.get(str(a.sku_id), f"SKU-{a.sku_id}") if a.sku_id else "—"
        period = (
            f"{a.start_date.strftime('%Y-%m-%d')} ~ "
            f"{a.end_date.strftime('%Y-%m-%d') if a.end_date else '永久'}"
        )
        return {
            "ID": a.id,
            "类型": a.addon_type,
            "SKU": sku_name,
            "覆盖单价": f"¥{a.override_price:.2f}" if a.override_price is not None else "—",
            "覆盖押金": f"¥{a.override_deposit:.2f}" if a.override_deposit is not None else "—",
            "有效期": period,
            "状态": a.status,
        }

    sel_addon_id = None
    if display_list:
        df = pd.DataFrame([_addon_row(a) for a in display_list])
        sel = st.dataframe(
            df, use_container_width=True, hide_index=True,
            key=f"addon_list_{business_id}_{list_tab_label}",
            selection_mode="single-row",
            on_select="rerun",
        )
        selected_rows = sel.get("selection", {}).get("selectedRows", [])
        sel_addon_id = selected_rows[0]["ID"] if selected_rows else None
    else:
        st.info("暂无附加业务政策。")

    # ------------------------------------------------------------------
    # 模式切换 + 操作按钮
    # ------------------------------------------------------------------
    if mode == "create":
        st.markdown("---")
        _render_addon_create_form(session, business_id, biz)
    elif mode == "edit" and sel_addon_id is not None:
        st.markdown("---")
        _render_addon_edit_form(session, business_id, sel_addon_id)
    else:
        col_new, col_edit, col_deact = st.columns(3)
        with col_new:
            if st.button("➕ 新建附加项", key=f"addon_new_btn_{business_id}"):
                st.session_state[MODE_KEY] = "create"
                st.rerun()
        with col_edit:
            edit_disabled = sel_addon_id is None
            if st.button("✏️ 编辑选中项", key=f"addon_edit_btn_{business_id}", disabled=edit_disabled):
                st.session_state[MODE_KEY] = "edit"
                st.session_state[EDIT_ID_KEY] = sel_addon_id
                st.rerun()
        with col_deact:
            deact_disabled = sel_addon_id is None
            if st.button("🚫 失效选中项", key=f"addon_deact_btn_{business_id}", disabled=deact_disabled):
                result = deactivate_addon_business_action(session, sel_addon_id)
                if result.success:
                    st.success("✅ 已失效")
                    st.rerun()
                else:
                    st.error(f"❌ 失败：{result.error}")


def _render_addon_create_form(session, business_id, biz):
    """渲染新建 addon 表单"""
    st.markdown("**新建附加项**")

    col_type, col_sku = st.columns(2)
    with col_type:
        sel_addon_type = st.selectbox(
            "附加项类型",
            options=[AddonType.PRICE_ADJUST, AddonType.NEW_SKU],
            format_func=lambda x: {
                AddonType.PRICE_ADJUST: "价格调整 (PRICE_ADJUST)",
                AddonType.NEW_SKU: "新增 SKU (NEW_SKU)",
            }[x],
            key=f"new_addon_type_{business_id}",
        )

    with col_sku:
        pricing = biz.get("pricing", {})
        pricing_sku_ids = set(str(k) for k in pricing.keys() if str(k).isdigit())

        if sel_addon_type == AddonType.PRICE_ADJUST:
            avail = {sid: pricing[sid].get("price", 0) or 0 for sid in pricing_sku_ids}
            if not avail:
                st.warning("该业务下暂无定价 SKU，无法添加价格调整附加项。")
                sel_sku_id = None
                sel_sku_type = None
            else:
                sku_map = {str(s.id): s.name for s in session.query(SKU).all()}
                sel_sku_id = st.selectbox(
                    "选择 SKU",
                    options=[int(sid) for sid in avail],
                    format_func=lambda sid: sku_map.get(str(sid), f"SKU-{sid}"),
                    key=f"new_addon_sku_{business_id}",
                )
                sel_sku_type = session.query(SKU).get(sel_sku_id).type_level1
        else:
            all_skus = {str(s.id): s.name for s in session.query(SKU).all()}
            avail = {sid: name for sid, name in all_skus.items() if sid not in pricing_sku_ids}
            if not avail:
                st.warning("没有可新增的 SKU（所有 SKU 已在业务定价范围内）。")
                sel_sku_id = None
                sel_sku_type = None
            else:
                sel_sku_id = st.selectbox(
                    "选择 SKU（新增）",
                    options=[int(sid) for sid in avail],
                    format_func=lambda sid: avail.get(str(sid), f"SKU-{sid}"),
                    key=f"new_addon_sku_{business_id}",
                )
                sel_sku_type = session.query(SKU).get(sel_sku_id).type_level1

    # 日期
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("开始日期", value=datetime.now().date(),
                                    key=f"new_addon_start_{business_id}")
    with col_end:
        end_date = st.date_input("结束日期（留空 = 永久）", value=None,
                                  key=f"new_addon_end_{business_id}")

    # 覆盖值
    override_val = None
    if sel_addon_type in [AddonType.PRICE_ADJUST, AddonType.NEW_SKU] and sel_sku_type:
        if sel_sku_type == "设备":
            override_label = "覆盖押金（元）"
        elif sel_sku_type == "物料":
            override_label = "覆盖单价（元）"
        else:
            override_label = "覆盖单价或押金"
        override_val = st.number_input(override_label, min_value=0.0, format="%.2f",
                                       value=None, key=f"new_addon_override_{business_id}")

    remark = st.text_area("备注（可选）", placeholder="选填",
                          key=f"new_addon_remark_{business_id}")

    col_submit, col_cancel = st.columns([1, 4])
    with col_submit:
        if st.button("创建", type="primary", key=f"new_addon_submit_{business_id}"):
            if sel_addon_type in [AddonType.PRICE_ADJUST, AddonType.NEW_SKU] and not sel_sku_id:
                st.error("请先选择 SKU")
            else:
                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.min.time()) if end_date else None
                override_price = override_val if sel_sku_type == "物料" else None
                override_deposit = override_val if sel_sku_type == "设备" else None
                payload = CreateAddonSchema(
                    business_id=business_id,
                    addon_type=sel_addon_type,
                    sku_id=sel_sku_id,
                    override_price=override_price,
                    override_deposit=override_deposit,
                    start_date=start_dt,
                    end_date=end_dt,
                    remark=remark or None,
                )
                result = create_addon_business_action(session, payload)
                if result.success:
                    st.success(f"✅ {result.message}（ID: {result.data['addon_id']}）")
                    st.session_state[f"addon_mode_{business_id}"] = None
                    st.rerun()
                else:
                    st.error(f"❌ 创建失败：{result.error}")
    with col_cancel:
        if st.button("取消", key=f"new_addon_cancel_{business_id}"):
            st.session_state[f"addon_mode_{business_id}"] = None
            st.rerun()


def _render_addon_edit_form(session, business_id, addon_id):
    """渲染编辑 addon 表单"""
    st.markdown(f"**编辑附加项 #{addon_id}**")

    detail = get_addon_detail(session, addon_id)
    if not detail or detail.business_id != business_id:
        st.error("附加项不存在或不属于当前业务。")
        return

    sku_map = {str(s.id): s.name for s in session.query(SKU).all()}
    sku_name = sku_map.get(str(detail.sku_id), f"SKU-{detail.sku_id}") if detail.sku_id else "—"

    st.caption(f"类型：{detail.addon_type} | SKU：{sku_name}")

    col_price, col_deposit = st.columns(2)
    with col_price:
        new_price = st.number_input(
            "覆盖单价（元）",
            value=detail.override_price if detail.override_price is not None else 0.0,
            key=f"edit_price_{addon_id}",
        )
    with col_deposit:
        new_deposit = st.number_input(
            "覆盖押金（元）",
            value=detail.override_deposit if detail.override_deposit is not None else 0.0,
            key=f"edit_deposit_{addon_id}",
        )

    col_start, col_end = st.columns(2)
    with col_start:
        new_start = st.date_input(
            "开始日期",
            value=detail.start_date.date(),
            key=f"edit_start_{addon_id}",
        )
    with col_end:
        new_end = st.date_input(
            "结束日期",
            value=detail.end_date.date() if detail.end_date else None,
            key=f"edit_end_{addon_id}",
        )

    new_remark = st.text_area(
        "备注",
        value=detail.remark or "",
        key=f"edit_remark_{addon_id}",
    )

    col_save, col_close = st.columns([1, 4])
    with col_save:
        if st.button("💾 保存", type="primary", key=f"save_addon_{addon_id}"):
            payload = UpdateAddonSchema(
                addon_id=addon_id,
                override_price=new_price if new_price != 0.0 else None,
                override_deposit=new_deposit if new_deposit != 0.0 else None,
                start_date=datetime.combine(new_start, datetime.min.time()),
                end_date=datetime.combine(new_end, datetime.min.time()) if new_end else None,
                remark=new_remark or None,
            )
            result = update_addon_business_action(session, payload)
            if result.success:
                st.success("✅ 更新成功")
                st.session_state[f"addon_mode_{business_id}"] = None
                st.rerun()
            else:
                st.error(f"❌ 更新失败：{result.error}")
    with col_close:
        if st.button("关闭", key=f"close_edit_{addon_id}"):
            st.session_state[f"addon_mode_{business_id}"] = None
            st.rerun()


# --- 业务概览模块 ---
def show_business_overview(session):
    """业务全局概览 - 已重构为使用 queries 层"""
    st.markdown("### <i class='bi bi-globe'></i> 业务全局概览", unsafe_allow_html=True)
    
    # 过滤器
    all_biz_status = [
        BusinessStatus.DRAFT, BusinessStatus.EVALUATION, BusinessStatus.FEEDBACK, 
        BusinessStatus.LANDING, BusinessStatus.ACTIVE, BusinessStatus.PAUSED, BusinessStatus.TERMINATED
    ]
    sel_status = st.multiselect("业务阶段过滤", all_biz_status, default=[BusinessStatus.LANDING, BusinessStatus.ACTIVE])
    
    # 使用 queries 层获取业务列表
    results = get_business_list(status=sel_status)
    
    if results:
        df_data = pd.DataFrame([
            {
                "ID": b['id'],
                "客户": b['customer_name'],
                "当前阶段": b['status'],
                "创建时间": b['created_at']
            } for b in results
        ])
        
        df_config = {
            "use_container_width": True,
            "on_select": "rerun",
            "selection_mode": "single-row",
            "key": "biz_overview_df"
        }
        if len(df_data) > 10:
            df_config["height"] = 400
            
        event = st.dataframe(df_data, **df_config)
        
        selection = event.get("selection", {}).get("rows", [])
        if selection:
            idx = selection[0]
            target_biz_id = df_data.iloc[idx]["ID"]
            biz = get_business_detail(int(target_biz_id))
            
            if biz:
                st.divider()
                st.write(f"#### 业务详情 (ID: {biz['id']})")
                
                sel_b_tab = sac.tabs([
                    sac.TabsItem('业务明细', icon='info-circle'),
                    sac.TabsItem('关联虚拟合同', icon='link-45deg'),
                    sac.TabsItem('数据修正与管理', icon='pencil-square'),
                    sac.TabsItem('规则管理', icon='shield-check'),
                ], align='center', variant='outline', key=f"biz_tabs_{biz['id']}")
                
                if sel_b_tab == '业务明细':
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**客户主体**: {biz['customer']['name'] if biz['customer'] else 'N/A'}")
                        st.write(f"**当前状态**: `{biz['status']}`")
                        st.write(f"**创建日期**: {biz['created_at']}")

                    with col2:
                        st.write("**商务定价配置 (部分)**")
                        pricing = biz['pricing']
                        if pricing:
                            sku_name_map = {str(s.id): s.name for s in session.query(SKU).all()}
                            p_df_list = []
                            for sku_id_key, v in pricing.items():
                                sku_display_name = sku_name_map.get(str(sku_id_key), f"SKU-{sku_id_key}")
                                if isinstance(v, dict):
                                    p_df_list.append({"品类": sku_display_name, "执行价": v.get("price", 0), "押金": v.get("deposit", 0)})
                                else:
                                    p_df_list.append({"品类": sku_display_name, "执行价": v, "押金": 0})
                            st.dataframe(pd.DataFrame(p_df_list), hide_index=True)
                        else:
                            st.caption("暂无定价协议数据")
                            
                elif sel_b_tab == '关联虚拟合同':
                    vcs = get_vc_list(business_id=biz['id'])
                    if vcs:
                        vc_df = pd.DataFrame([
                            {
                                "VC ID": v['id'],
                                "类型": v['type'],
                                "总体状态": v['status'],
                                "标的状态": v.get('subject_status', '-'),
                                "资金状态": v.get('cash_status', '-'),
                                "描述": v.get('description', '')
                            } for v in vcs
                        ])
                        st.dataframe(vc_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("该业务下暂无任何执行中的虚拟合同。")

                elif sel_b_tab == '数据修正与管理':
                    st.warning("⚠️ 此处修改直接影响数据库底层数据，请谨慎操作")
                    
                    import json
                    
                    with st.form(f"biz_edit_form_{biz['id']}"):
                        st.markdown("**业务详情数据 (JSON 格式)**")
                        st.caption("包含定价配置、支付条款、历史记录等")
                        
                        details_json = json.dumps(biz['details'], indent=4, ensure_ascii=False) if biz.get('details') else "{}"
                        new_details_str = st.text_area("修改业务配置", value=details_json, height=400, label_visibility="collapsed")
                        
                        new_status = st.selectbox("业务状态", 
                            options=[BusinessStatus.DRAFT, BusinessStatus.EVALUATION, BusinessStatus.FEEDBACK, 
                                     BusinessStatus.LANDING, BusinessStatus.ACTIVE, BusinessStatus.PAUSED, BusinessStatus.TERMINATED],
                            index=[BusinessStatus.DRAFT, BusinessStatus.EVALUATION, BusinessStatus.FEEDBACK, 
                                   BusinessStatus.LANDING, BusinessStatus.ACTIVE, BusinessStatus.PAUSED, BusinessStatus.TERMINATED].index(biz['status']) if biz.get('status') in [BusinessStatus.DRAFT, BusinessStatus.EVALUATION, BusinessStatus.FEEDBACK, BusinessStatus.LANDING, BusinessStatus.ACTIVE, BusinessStatus.PAUSED, BusinessStatus.TERMINATED] else 0
                        )
                        
                        c1, c2 = st.columns([1, 1])
                        if c1.form_submit_button("确认并更新业务数据", type="primary"):
                            payload = UpdateBusinessStatusSchema(
                                business_id=biz['id'],
                                status=new_status,
                                details=json.loads(new_details_str)
                            )
                            result = update_business_status_action(session, payload)
                            if result.success:
                                st.success(result.message)
                                st.rerun()
                            else:
                                st.error(result.error)
                        
                        # 删除业务（仅当无关联VC时）
                        vc_count = get_vc_count_by_business(biz['id'])
                        can_delete = (vc_count == 0)
                        if c2.form_submit_button("删除此业务", disabled=not can_delete):
                            result = delete_business_action(session, biz['id'])
                            if result.success:
                                st.success(result.message)
                                st.rerun()
                            else:
                                st.error(result.error)
                        
                        if not can_delete:
                            st.caption(f"📌 该业务下有 {vc_count} 个关联虚拟合同，无法删除")

                elif sel_b_tab == '规则管理':
                    from ui.rule_components import show_rule_manager_tab
                    from logic.constants import TimeRuleRelatedType
                    show_rule_manager_tab(biz['id'], TimeRuleRelatedType.BUSINESS)
    else:
        st.info("暂无符合条件的业务记录。")

def show_business_management_page():
    st.markdown("<h2 style='font-size: 20px;'><i class='bi bi-briefcase'></i> 业务管理</h2>", unsafe_allow_html=True)

    with st.container():
        sel_tab = sac.tabs([
            sac.TabsItem('业务概览', icon='eye'),
            sac.TabsItem('客户导入', icon='person-plus'),
            sac.TabsItem('附加业务', icon='plus-circle'),
        ], align='center', variant='outline', key='business_mgmt_tabs')

        session = get_session()

        if sel_tab == '业务概览':
            show_business_overview(session)
        elif sel_tab == '客户导入':
            show_customer_inclusion()
        elif sel_tab == '附加业务':
            show_addon_management_page(session)

        session.close()

def show_supply_chain_management_page():
    st.markdown("<h2 style='font-size: 20px;'><i class='bi bi-link-45deg'></i> 供应链管理</h2>", unsafe_allow_html=True)
    
    with st.container():
        sel_tab = sac.tabs([
            sac.TabsItem('供应链概览', icon='bezier2'),
            sac.TabsItem('供应链导入', icon='box-arrow-in-right'),
        ], align='center', variant='outline', key='supply_chain_mgmt_tabs')
        
        if sel_tab == '供应链概览':
            # 复用原有的列表逻辑，稍作修改以适应作为概览
            show_supply_chain_list()
        elif sel_tab == '供应链导入':
            # 复用原有的导入逻辑
            show_supply_chain_import()

def show_supply_chain_list():
    """供应链概览：仅展示列表和详情"""
    session = get_session()
    st.markdown("### <i class='bi bi-list-columns-reverse'></i> 现有的供应链协议列表", unsafe_allow_html=True)
    chains = get_supply_chains()
    if chains:
        df_list = []
        for c in chains:
            terms = c.get('payment_terms', {})
            df_list.append({
                "ID": c['id'],
                "供应商": c['supplier_name'],
                "协议大类": c['type'],
                "结算模式": f"{int(terms.get('prepayment_ratio',0)*100)}% 预付 / {terms.get('balance_period',0)}天账期",
                "包含品类数": "-" # len(c.items) placeholder
            })
        
        sc_df = pd.DataFrame(df_list)
        sc_df_config = {
            "use_container_width": True, 
            "hide_index": True,
            "on_select": "rerun",
            "selection_mode": "single-row",
            "key": "sc_list_df_overview"
        }
        if len(sc_df) > 10:
            sc_df_config["height"] = 400

        event = st.dataframe(sc_df, **sc_df_config)

        selection = event.get("selection", {}).get("rows", [])
        if selection:
            idx = selection[0]
            target_sc_id = sc_df.iloc[idx]["ID"]
            sc = get_supply_chain_detail(int(target_sc_id))
            
            if sc:
                st.divider()
                supplier_display = html.escape(sc['supplier']['name'] if sc['supplier'] else '未知')
                type_display = html.escape(sc['type'])
                st.markdown(f"#### <i class='bi bi-search'></i> 协议详情: {supplier_display} ({type_display})", unsafe_allow_html=True)
                
                sel_det_tab = sac.tabs([
                    sac.TabsItem('价格协议明细', icon='tag'),
                    sac.TabsItem('结算条款详情', icon='file-earmark-ruled'),
                    sac.TabsItem('关联合同信息', icon='journal-text'),
                    sac.TabsItem('数据修正与管理', icon='pencil-square'),
                    sac.TabsItem('规则管理', icon='shield-check'),
                ], align='center', variant='outline', key=f"sc_det_tabs_{sc['id']}")
                
                if sel_det_tab == '价格协议明细':
                    st.write("**SKU 协议单价约定**")
                    items_data = []
                    # pricing_details 已有格式化好的数据，直接使用
                    pricing_details = sc.get('pricing_details', [])
                    sku_name_map = sc.get('sku_name_map', {})
                    for item in pricing_details:
                        sku_display_name = sku_name_map.get(str(item['sku_id']), item['sku_name'])
                        items_data.append({
                            "品类名称": sku_display_name,
                            "协议单价": item['price'],
                            "定价模式": "固定协议价" if not item.get('is_floating') else "按次浮动"
                        })
                    
                    if items_data:
                        st.dataframe(
                            pd.DataFrame(items_data),
                            use_container_width=True,
                            column_config={
                                "协议单价": st.column_config.NumberColumn(format="¥ %.2f")
                            },
                            hide_index=True
                        )
                    else:
                        st.warning("该协议下未配置具体品类价格")
                
                elif sel_det_tab == '结算条款详情':
                    terms = sc.get('payment_terms', {})
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("预付款比例", f"{int(terms.get('prepayment_ratio', 0) * 100)}%")
                    c2.metric("尾款账期", f"{terms.get('balance_period', 0)} 天")
                    c3.write(f"**计日规则**: {terms.get('day_rule', SettlementRule.NATURAL_DAY)}")
                    c4.write(f"**起算点**: {terms.get('start_trigger', '-')}")
                
                elif sel_det_tab == '关联合同信息':
                    contract = get_contract_detail(sc['contract_id']) if sc.get('contract_id') else None
                    if contract:
                        st.write(f"**关联正本合同**: `{contract['contract_number']}`")
                        st.write(f"**合同类型**: {contract['type']}")
                        st.write(f"**签约日期**: {contract['signed_date'] or '-'}")
                        
                        from logic.file_mgmt import get_contract_files
                        files = get_contract_files(contract['id'])
                        if files:
                            st.write("**📎 已上传附件**")
                            for f in files:
                                st.code(f)
                    else:
                        st.info("该供应链协议未关联正式合同记录")

                elif sel_det_tab == '数据修正与管理':
                    st.warning("⚠️ 此处修改直接影响数据库底层数据，请谨慎操作")

                    import json

                    with st.form(f"sc_edit_form_{sc['id']}"):
                        st.markdown("**供应链协议数据 (JSON 格式)**")
                        st.caption("包含定价配置、结算条款等")

                        pricing_json = json.dumps(sc.get('pricing_config', {}), indent=4, ensure_ascii=False) if sc.get('pricing_config') else "{}"
                        new_pricing_str = st.text_area("修改定价配置", value=pricing_json, height=200, label_visibility="collapsed")

                        payment_json = json.dumps(sc.get('payment_terms', {}), indent=4, ensure_ascii=False) if sc.get('payment_terms') else "{}"
                        new_payment_str = st.text_area("修改结算条款", value=payment_json, height=200, label_visibility="collapsed")

                        c1, c2 = st.columns([1, 1])
                        if c1.form_submit_button("确认并更新供应链数据", type="primary"):
                            try:
                                # 构建 items 列表（从 pricing_dict 逆向构建）
                                items = []
                                for sku_id_key, price_info in pricing_dict.items():
                                    sku_id_int = int(sku_id_key) if str(sku_id_key).isdigit() else None
                                    if sku_id_int:
                                        if isinstance(price_info, dict):
                                            items.append({
                                                "sku_id": sku_id_int,
                                                "price": price_info.get("price", 0),
                                                "is_floating": price_info.get("is_floating", False)
                                            })
                                        else:
                                            items.append({
                                                "sku_id": sku_id_int,
                                                "price": price_info if price_info != "浮动" else 0.0,
                                                "is_floating": (price_info == "浮动")
                                            })
                                payload = UpdateSupplyChainSchema(
                                    id=sc['id'],
                                    supplier_name=sc['supplier_name'],
                                    type=sc['type'],
                                    items=items,
                                    payment_terms=json.loads(new_payment_str)
                                )
                                from logic.supply_chain.actions import update_supply_chain_action
                                result = update_supply_chain_action(session, payload)
                                if result.success:
                                    st.success(result.message)
                                    st.rerun()
                                else:
                                    st.error(result.error)
                            except json.JSONDecodeError as e:
                                st.error(f"JSON 格式错误: {e}")
                            except Exception as e:
                                st.error(f"更新失败: {e}")

                        # 删除协议（仅当无关联合同时）
                        if c2.form_submit_button("删除此协议"):
                            from logic.supply_chain.actions import delete_supply_chain_action
                            delete_payload = DeleteSupplyChainSchema(id=sc['id'])
                            result = delete_supply_chain_action(session, delete_payload)
                            if result.success:
                                st.success(result.message)
                                st.rerun()
                            else:
                                st.error(result.error)

                elif sel_det_tab == '规则管理':
                    from ui.rule_components import show_rule_manager_tab
                    from logic.constants import TimeRuleRelatedType
                    show_rule_manager_tab(sc['id'], TimeRuleRelatedType.SUPPLY_CHAIN)
    else:
        st.info("暂无已建立的供应链协议记录")
    session.close()

def show_supply_chain_import():
    """供应链导入：仅展示新建表单"""
    session = get_session()
    
    # 1. 基础信息选择 (前置过滤)
    suppliers = get_suppliers()
    supplier_map = {s['name']: s['id'] for s in suppliers}
    
    col_s1, col_s2 = st.columns([2, 1])
    s_name = col_s1.selectbox("供应商主体", list(supplier_map.keys()) if supplier_map else ["无可用供应商"])
    sc_type = col_s2.radio("协议大类", [SKUType.EQUIPMENT, SKUType.MATERIAL], horizontal=True)
    
    # 2. 获取限定范围内的 SKU
    sid = supplier_map.get(s_name)
    available_skus = get_skus(supplier_id=sid)
    available_skus = [s for s in available_skus if s['type_level1'] == sc_type]
    sku_list = [sku['name'] for sku in available_skus]
    sku_id_map = {sku['name']: sku['id'] for sku in available_skus}
    
    if not sku_list:
        st.warning(f"该供应商 {s_name} 旗下暂未登记任何 {sc_type} 品类 SKU，请先在【信息录入】中添加。")

    # 3. 定价协议明细 (使用 data_editor)
    st.markdown("#### <i class='bi bi-pricetag'></i> 定价协议明细", unsafe_allow_html=True)
    st.caption("协议单价填 0 或留空将自动设为'浮动'（即每次执行需单独录入单价）")
    
    editor_key = f"sc_editor_{sid}_{sc_type}"
    if f"df_{editor_key}" not in st.session_state:
        st.session_state[f"df_{editor_key}"] = pd.DataFrame([{"品类": "", "协议单价": 0.0}])
        
    edited_df = st.data_editor(
        st.session_state[f"df_{editor_key}"],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "品类": st.column_config.SelectboxColumn("选择此供应商 SKU", options=sku_list, required=True),
            "协议单价": st.column_config.NumberColumn("协议单价 (元)", format="%.2f", min_value=0.0)
        },
        key=editor_key
    )

    # 4. 结算条款与提交
    st.markdown("#### <i class='bi bi-credit-card'></i> 结算与合同协议", unsafe_allow_html=True)
    with st.form("sc_create_form"):
        c1, c2, c3, c4 = st.columns(4)
        prepay_ratio_pct = c1.number_input("预付款比例 (%)", value=0, step=1)
        balance_days = c2.number_input("尾款账期 (天)", min_value=0, value=30)
        day_rule = c3.selectbox("计日规则", [SettlementRule.NATURAL_DAY, SettlementRule.WORK_DAY])
        start_trigger = c4.selectbox("起算锚点", [SettlementRule.TRIGGER_INBOUND, SettlementRule.TRIGGER_SHIPPED])

        contract_num = st.text_input("合同编号")
        contract_files = st.file_uploader("供货合同附件上传", accept_multiple_files=True)
        
        # --- [新] 供应链端初始模板规则配置 ---
        st.divider()
        st.markdown("#### <i class='bi bi-shield-check'></i> 预设协议模板规则 (将向下传播)", unsafe_allow_html=True)
        from logic.constants import TimeRuleParty, TimeRuleOffsetUnit, TimeRuleDirection, EventType, TimeRuleInherit
        sc_rules_key = f"sc_initial_rules_{sid}_{sc_type}"
        if sc_rules_key not in st.session_state: st.session_state[sc_rules_key] = []
        
        # SC 级可用事件
        sc_events = EventType.ContractLevel.ALL_EVENTS + EventType.VCLevel.ALL_EVENTS
        
        edited_sc_rules = st.data_editor(
            pd.DataFrame(st.session_state[sc_rules_key]) if st.session_state[sc_rules_key] else pd.DataFrame(columns=["责任方", "触发事件", "偏移", "单位", "方向", "目标事件"]),
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "责任方": st.column_config.SelectboxColumn(options=TimeRuleParty.ALL_PARTIES, required=True),
                "触发事件": st.column_config.SelectboxColumn(options=sc_events, required=True),
                "偏移": st.column_config.NumberColumn(min_value=0, step=1, default=0),
                "单位": st.column_config.SelectboxColumn(options=TimeRuleOffsetUnit.ALL_UNITS, default=TimeRuleOffsetUnit.NATURAL_DAY),
                "方向": st.column_config.SelectboxColumn(options=list(TimeRuleDirection.UI_LABELS.values()), default=TimeRuleDirection.UI_LABELS[TimeRuleDirection.AFTER]),
                "目标事件": st.column_config.SelectboxColumn(options=sc_events, required=True)
            },
            hide_index=True,
            key=f"sc_init_rules_editor_{sid}_{sc_type}"
        )
        
        def _get_rev_dir(label):
            for k,v in TimeRuleDirection.UI_LABELS.items():
                if v == label: return k
            return TimeRuleDirection.AFTER

        sc_final_rules = []
        for _, row in edited_sc_rules.iterrows():
            if row["责任方"] and row["触发事件"] and row["目标事件"]:
                rd = row.to_dict()
                rd['方向'] = _get_rev_dir(row['方向'])
                sc_final_rules.append(rd)
        st.session_state[sc_rules_key] = sc_final_rules
        
        st.divider()
        submit = st.form_submit_button("建立并激活供应链关系", type="primary", use_container_width=True)
        # submit_with_rules 已不再需要，逻辑并入上方

        if submit:
            sc_items = []
            for _, row in edited_df.iterrows():
                if row["品类"]:
                    sku_name = row["品类"]
                    sku = session.query(SKU).filter(SKU.name == sku_name).first()
                    if sku:
                        sc_items.append({
                            "sku_id": sku.id,
                            "price": row["协议单价"] if row["协议单价"] > 0 else 0.0,
                            "is_floating": (row["协议单价"] <= 0)
                        })

            payload = CreateSupplyChainSchema(
                supplier_id=sid,
                supplier_name=s_name,
                type=sc_type,
                items=sc_items,
                payment_terms={
                    "prepayment_ratio": prepay_ratio_pct / 100.0,
                    "balance_period": balance_days,
                    "day_rule": day_rule,
                    "start_trigger": start_trigger
                },
                contract_num=contract_num
            )
            
            # 集成初始模板规则
            result = create_supply_chain_action(session, payload, template_rules=sc_final_rules)
            
            if result.success:
                # 文件上传保留在 UI 层
                if contract_files and result.data.get("contract_id"):
                    from logic.file_mgmt import save_contract_files
                    save_contract_files(result.data["contract_id"], contract_files)
                
                st.success(result.message)
                if f"df_{editor_key}" in st.session_state: del st.session_state[f"df_{editor_key}"]
                if sc_rules_key in st.session_state: del st.session_state[sc_rules_key]
                st.rerun()
            else:
                st.error(result.error)
    session.close()

# show_management_page 已废弃，被拆分为 show_business_management_page 和 show_supply_chain_management_page
# def show_management_page(): ...


def show_virtual_contract_page():
    st.markdown("<h2 style='font-size: 20px;'><i class='bi bi-file-text'></i> 虚拟合同 (业务执行)</h2>", unsafe_allow_html=True)
    with st.container():
        show_business_execution()

def show_inventory_dashboard_page():
    st.markdown("<h2 style='font-size: 20px;'><i class='bi bi-boxes'></i> 库存看板</h2>", unsafe_allow_html=True)
    with st.container():
        show_inventory_dashboard_component()

def show_inventory_dashboard_component():
    """库存看板组件 - 已重构为使用 queries 层"""
    # 顶部指标 - 使用 queries 层获取汇总数据
    summary = get_equipment_inventory_summary()
    mat_summary = get_material_inventory_summary()
    
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(f"**总在册设备**: {html.escape(str(summary['total_count']))} 台", unsafe_allow_html=False)
    with sc2:
        st.markdown(f"**在库物料品类**: {html.escape(str(mat_summary['total_skus']))} 项", unsafe_allow_html=False)
    with sc3:
        st.markdown(f"**物料库存总量**: {html.escape(str(mat_summary['total_quantity']))} 件", unsafe_allow_html=False)

    # 检查 session_state 中的值是否有效，防止旧值导致 ValueError
    _valid_tabs = ['设备库存', '物料库存']
    if st.session_state.get('inv_dashboard_tabs') not in _valid_tabs:
        st.session_state['inv_dashboard_tabs'] = _valid_tabs[0]

    sel_tab = sac.tabs([
        sac.TabsItem('设备库存', icon='hdd-network'),
        sac.TabsItem('物料库存', icon='box-seam'),
    ], align='center', variant='outline', key='inv_dashboard_tabs')
    
    if sel_tab == '设备库存':
        st.markdown("#### <i class='bi bi-hdd-network'></i> 存量设备明细", unsafe_allow_html=True)
        # 使用 queries 层获取设备列表
        eq_data = get_equipment_inventory_list()
        if eq_data:
            eq_df = pd.DataFrame(eq_data)
            st.dataframe(eq_df, use_container_width=True)
        else:
            st.info("目前没有设备库存记录")

    elif sel_tab == '物料库存':
        st.markdown("#### <i class='bi bi-box-seam'></i> 存量物料统计", unsafe_allow_html=True)

        col1, col2 = st.columns([3, 1])
        col1.write("")
        if col2.button("刷新数据", key="refresh_mat_inv"):
            st.rerun()

        # 全局视角切换
        view_mode = sac.tabs([
            sac.TabsItem("按仓库", icon="geo-alt"),
            sac.TabsItem("按批次", icon="collection"),
        ], align="start", variant="pill", key="mat_inv_view_mode")

        # 使用完整批次明细数据构建两套视图
        all_rows = get_material_inventory_all()
        if not all_rows:
            st.info("目前没有物料库存记录")
        else:
            # 收集 sku 均价
            _s = get_session()
            sku_avg_map = {}
            sku_name_map = {}
            sku_ids_in_use = list({r["sku_id"] for r in all_rows})
            if sku_ids_in_use:
                sku_objs = _s.query(SKU).filter(SKU.id.in_(sku_ids_in_use)).all()
                for s in sku_objs:
                    sku_name_map[s.id] = s.name
                    sku_avg_map[s.id] = float(s.params.get("average_price", 0.0) or 0) if s.params else 0.0
            _s.close()

            by_sku = {}
            for r in all_rows:
                sid = r["sku_id"]
                if sid not in by_sku:
                    by_sku[sid] = {"sku_name": r["sku_name"], "batches": []}
                by_sku[sid]["batches"].append(r)

            # 仓库颜色映射
            WH_COLOR_MAP = {
                "成都仓": "#4CAF50", "天津仓": "#2196F3", "深圳仓": "#FF9800",
                "廊坊仓": "#9C27B0", "北京仓": "#F44336", "上海仓": "#00BCD4",
                "广州仓": "#FF5722", "武汉仓": "#795548", "西安仓": "#607D8B",
                "重庆仓": "#F06292",
            }

            for sku_id, sku_data in by_sku.items():
                sku_name = sku_name_map.get(sku_id, sku_data["sku_name"])
                batches = sku_data["batches"]
                total = sum(b["qty"] for b in batches)
                avg_price = sku_avg_map.get(sku_id, 0.0)

                with st.container():
                    st.markdown("---")
                    hdr_col1, hdr_col2, hdr_col3 = st.columns([1, 1, 1])
                    with hdr_col1:
                        st.markdown(f"**{html.escape(sku_name)}**")
                    with hdr_col2:
                        st.markdown(f"总库存：**<span style='color:#1976D2;font-size:15px;'>{int(total)}</span>** 件", unsafe_allow_html=True)
                    with hdr_col3:
                        if avg_price > 0:
                            st.markdown(f"均价：**<span style='color:#888;font-size:13px;'>¥{avg_price:.2f}</span>**", unsafe_allow_html=True)

                    # ── 按仓库视图 ──────────────────────────────────────
                    if view_mode == "按仓库":
                        # point -> [batch_rows]
                        pt_batches = {}
                        for b in batches:
                            pt = b["point_name"]
                            pt_batches.setdefault(pt, []).append(b)

                        for pt_name, pt_rows in sorted(pt_batches.items()):
                            pt_total = sum(r["qty"] for r in pt_rows)
                            pct = pt_total / total * 100 if total > 0 else 0
                            color = WH_COLOR_MAP.get(pt_name, "#90a4ae")
                            st.markdown(
                                f"<span style='color:{color};font-weight:600;'>●</span> "
                                f"<b>{html.escape(pt_name)}</b>  "
                                f"<span style='color:#555;font-size:13px;'>{int(pt_total)} 件（{pct:.0f}%）</span>",
                                unsafe_allow_html=True,
                            )
                            # 批次缩进
                            for r in sorted(pt_rows, key=lambda x: x["batch_no"]):
                                batch_pct = r["qty"] / total * 100 if total > 0 else 0
                                st.markdown(
                                    f"&nbsp;&nbsp;&nbsp;&nbsp;<span style='color:#aaa;font-size:12px;'>▸ {html.escape(r['batch_no'])}</span> "
                                    f"<span style='color:#777;font-size:12px;'>{int(r['qty'])} 件（{batch_pct:.0f}%）</span>",
                                    unsafe_allow_html=True,
                                )

                    # ── 按批次视图 ─────────────────────────────────────
                    elif view_mode == "按批次":
                        # batch_no -> [point_rows]
                        batch_pts = {}
                        for b in batches:
                            bn = b["batch_no"]
                            batch_pts.setdefault(bn, []).append(b)

                        for bn, bn_rows in sorted(batch_pts.items()):
                            bn_total = sum(r["qty"] for r in bn_rows)
                            pct = bn_total / total * 100 if total > 0 else 0
                            st.markdown(
                                f"<b>{html.escape(bn)}</b> "
                                f"<span style='color:#555;font-size:13px;'>{int(bn_total)} 件（{pct:.0f}%）</span>",
                                unsafe_allow_html=True,
                            )
                            # 仓库缩进
                            for r in sorted(bn_rows, key=lambda x: x["point_name"]):
                                pt_pct = r["qty"] / total * 100 if total > 0 else 0
                                color = WH_COLOR_MAP.get(r["point_name"], "#90a4ae")
                                st.markdown(
                                    f"&nbsp;&nbsp;&nbsp;&nbsp;<span style='color:{color};font-size:12px;'>●</span> "
                                    f"<span style='color:#777;font-size:12px;'>{html.escape(r['point_name'])} — {int(r['qty'])} 件（{pt_pct:.0f}%）</span>",
                                    unsafe_allow_html=True,
                                )

                    with st.expander("查看出入库时间线"):
                        movements = get_material_movement_timeline(sku_id=sku_id)
                        if not movements:
                            st.info("暂无出入库记录")
                        else:
                            rows = []
                            for m in movements:
                                ts = m.get("timestamp")
                                date_str = ts.strftime("%Y-%m-%d %H:%M") if ts else "-"
                                rows.append({
                                    "日期": date_str,
                                    "类型": "入库 ↑" if m.get("direction") == "入库" else "出库 ↓",
                                    "仓库": m.get("warehouse") or "-",
                                    "数量": m.get("qty") or 0,
                                    "摘要": m.get("description") or "",
                                })
                            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=180)

# show_execution_page 已废弃，被拆分为 show_virtual_contract_page 和 show_inventory_dashboard_page
# def show_execution_page(): ...

def show_customer_inclusion():
    st.markdown("### <i class='bi bi-folder-plus'></i> 客户与业务导入", unsafe_allow_html=True)
    st.caption("管理业务全生命周期的初始阶段：从前期接洽到合作落地")
    
    session = get_session()
    
    # 1. 新业务录入窗口
    with st.expander("发起新业务条目", expanded=False):
        with st.form("new_business_form"):
            customers = get_customers()
            customer_options = {c['name']: c['id'] for c in customers}
            
            c1, c2 = st.columns([3, 1])
            customer_name = c1.selectbox("选择目标客户主体", list(customer_options.keys()) if customer_options else [f"请先在【信息录入】添加客户"])
            
            st.info(f"💡 创建后，业务将默认进入【{BusinessStatus.DRAFT}】状态")
            submit = st.form_submit_button("建立业务关联", type="primary")
            
            if submit and customer_options:
                result = create_business_action(session, CreateBusinessSchema(customer_id=customer_options[customer_name]))
                if result.success:
                    st.success(result.message)
                    st.rerun()
                else:
                    st.error(result.error)

    st.write("---")
    
    # 2. 现有业务列表 (推进与概览)
    st.markdown("#### <i class='bi bi-bar-chart'></i> 现有业务列表 (导入/评估阶段)", unsafe_allow_html=True)
    
    inclusion_statuses = BusinessStatus.INCLUSION_PHASE
    active_businesses = get_business_list(status=inclusion_statuses)
    
    if not active_businesses:
        st.info("当前暂无处于【导入/评估】阶段的业务。")
    else:
        # A. 概览表
        summary_data = []
        for b in active_businesses:
            summary_data.append({
                "业务ID": b['id'],
                "客户主体": b['customer_name'],
                "当前所处阶段": b['status'],
                "建立日期": b['created_at'][:10] if b['created_at'] else "今日"
            })
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
        
        st.markdown("#### <i class='bi bi-gear-wide-connected'></i> 阶段推进操作", unsafe_allow_html=True)
        for b in active_businesses:
            customer_name = b['customer_name']
            with st.expander(f"📍 ID: {b['id']} | {customer_name} ({b['status']})"):
                next_status_map = {
                    BusinessStatus.DRAFT: BusinessStatus.EVALUATION,
                    BusinessStatus.EVALUATION: BusinessStatus.FEEDBACK,
                    BusinessStatus.FEEDBACK: BusinessStatus.LANDING,
                    BusinessStatus.LANDING: BusinessStatus.ACTIVE
                }
                
                col_btn1, col_btn2, col_btn3, _ = st.columns([1.2, 1, 1, 1.5])
                if col_btn1.button(f"推进至 {next_status_map[b['status']]}", key=f"adv_{b['id']}", type="primary"):
                    st.session_state[f"adv_process_{b['id']}"] = True
                
                if col_btn2.button("业务暂缓", key=f"pause_{b['id']}"):
                    result = update_business_status_action(session, UpdateBusinessStatusSchema(business_id=b['id'], status=BusinessStatus.PAUSED))
                    if result.success: st.rerun()
                    else: st.error(result.error)
                if col_btn3.button("业务终止", key=f"cancel_{b['id']}"):
                    result = update_business_status_action(session, UpdateBusinessStatusSchema(business_id=b['id'], status=BusinessStatus.TERMINATED))
                    if result.success: st.rerun()
                    else: st.error(result.error)

                if st.session_state.get(f"adv_process_{b['id']}"):
                    is_landing = (b['status'] == BusinessStatus.LANDING)
                    with st.form(f"adv_form_{b['id']}"):
                        st.write(f"### ⚙️ {b['status']} -> {next_status_map[b['status']]} 阶段推进")
                        
                        if is_landing:
                            st.info("💡 业务进入【业务开展】前，需完成商务结算协议的固化（参考供应链模式）")
                            
                            # A. SKU 定价协议 (销售侧)
                            st.markdown("#### <i class='bi bi-pricetag'></i> 合作协议明细", unsafe_allow_html=True)
                            
                            # 获取物料与设备 SKU 列表
                            all_skus = get_skus()
                            equip_skus = [s['name'] for s in all_skus if s['type_level1'] == SKUType.EQUIPMENT]
                            mat_skus = [s['name'] for s in all_skus if s['type_level1'] == SKUType.MATERIAL]
                            
                            # 1. 设备投放表 (关注押金)
                            st.markdown("##### <i class='bi bi-hdd-network'></i> 设备投放约定 (押金模式)", unsafe_allow_html=True)
                            df_e_key = f"biz_e_pricing_{b['id']}"
                            if df_e_key not in st.session_state:
                                st.session_state[df_e_key] = pd.DataFrame([{"设备品类": "", "计划投放量": 0, "单台押金": 0.0}])
                            
                            biz_e_df = st.data_editor(
                                st.session_state[df_e_key],
                                num_rows="dynamic",
                                use_container_width=True,
                                column_config={
                                    "设备品类": st.column_config.SelectboxColumn("选择设备", options=equip_skus, required=True),
                                    "计划投放量": st.column_config.NumberColumn("计划投放量", min_value=0, step=1),
                                    "单台押金": st.column_config.NumberColumn("单台押金 (元)", format="%.2f", min_value=0.0)
                                },
                                key=f"editor_e_biz_{b['id']}"
                            )

                            # 2. 物料供货表 (关注价格)
                            st.markdown("##### <i class='bi bi-cart'></i> 物料供货约定 (供货价格)", unsafe_allow_html=True)
                            df_m_key = f"biz_m_pricing_{b['id']}"
                            if df_m_key not in st.session_state:
                                st.session_state[df_m_key] = pd.DataFrame([{"物料品类": "", "供货单价": 0.0}])
                            
                            biz_m_df = st.data_editor(
                                st.session_state[df_m_key],
                                num_rows="dynamic",
                                use_container_width=True,
                                column_config={
                                    "物料品类": st.column_config.SelectboxColumn("选择物料", options=mat_skus, required=True),
                                    "供货单价": st.column_config.NumberColumn("销售单价 (元)", format="%.2f", min_value=0.0)
                                },
                                key=f"editor_m_biz_{b['id']}"
                            )
                            
                            # B. 结算条款
                            st.markdown("#### <i class='bi bi-credit-card'></i> 财务结算条款", unsafe_allow_html=True)
                            c1, c2, c3, c4 = st.columns(4)
                            prepay_pct = c1.number_input("预付款比例 (%)", value=0, step=1, key=f"pp_{b['id']}")
                            bal_days = c2.number_input("尾款账期 (天)", min_value=0, value=30, key=f"bd_{b['id']}")
                            d_rule = c3.selectbox("计日规则", [SettlementRule.NATURAL_DAY, SettlementRule.WORK_DAY], key=f"dr_{b['id']}")
                            trigger = c4.selectbox("起算锚点", [SettlementRule.TRIGGER_INBOUND, SettlementRule.TRIGGER_SHIPPED], key=f"st_{b['id']}")
                            
                            # C. 合同附件
                            st.markdown("#### <i class='bi bi-file-earmark-pdf'></i> 商务合同附件", unsafe_allow_html=True)
                            c_num = st.text_input("正式合同编号", key=f"cn_{b['id']}")
                            c_files = st.file_uploader("上传合同扫描件 (PDF) 及 逻辑配置 (JSON)", accept_multiple_files=True, key=f"cf_{b['id']}")
                            
                            # D. 时间规则配置说明
                            st.markdown("#### <i class='bi bi-clock-history'></i> 时间规则配置", unsafe_allow_html=True)
                            st.info("💡 请先在下方【规则预配置】区域添加账期规则，然后再点击'确认并完成签约落地'")
                            
                        comment = st.text_area("阶段推进小结/备注", placeholder="请输入该阶段的关键信息...", key=f"cm_{b['id']}")
                        
                        c_sub1, c_sub2 = st.columns(2)
                        submit_at_landing = c_sub1.form_submit_button("确认并完成签约落地" if is_landing else "确认推进", type="primary")
                        
                        if submit_at_landing:
                            p_config = {}
                            if is_landing:
                                for _, row in biz_e_df.iterrows():
                                    if row["设备品类"]:
                                        sku_name = row["设备品类"]
                                        sku = session.query(SKU).filter(SKU.name == sku_name).first()
                                        if sku:
                                            p_config[str(sku.id)] = {"price": 0, "deposit": row["单台押金"]}
                                for _, row in biz_m_df.iterrows():
                                    if row["物料品类"]:
                                        sku_name = row["物料品类"]
                                        sku = session.query(SKU).filter(SKU.name == sku_name).first()
                                        if sku:
                                            p_config[str(sku.id)] = {"price": row["供货单价"], "deposit": 0}
                                        
                            # 执行推进 Action
                            payload = AdvanceBusinessStageSchema(
                                business_id=b['id'],
                                next_status=next_status_map[b['status']],
                                comment=comment,
                                pricing=p_config if is_landing else None,
                                payment_terms={
                                    "prepayment_ratio": prepay_pct / 100.0,
                                    "balance_period": bal_days,
                                    "day_rule": d_rule,
                                    "start_trigger": trigger
                                } if is_landing else None,
                                contract_num=c_num if is_landing else None
                            )
                            
                            result = advance_business_stage_action(session, payload)
                            
                            if result.success:
                                # 处理文件 (Action 不处理文件 IO，保留在此)
                                if is_landing and c_files and result.data.get("contract_id"):
                                    from logic.file_mgmt import save_contract_files
                                    save_contract_files(result.data["contract_id"], c_files)
                                
                                # 清理状态
                                if is_landing:
                                    if df_e_key in st.session_state: del st.session_state[df_e_key]
                                    if df_m_key in st.session_state: del st.session_state[df_m_key]
                                
                                del st.session_state[f"adv_process_{b['id']}"]
                                st.success(result.message)
                                st.rerun()
                            else:
                                st.error(result.error)
                            
                        if c_sub2.form_submit_button("返回"):
                            del st.session_state[f"adv_process_{b['id']}"]
                            st.rerun()
                    
                    # === 规则预配置区域（表单外部） ===
                    if is_landing:
                        with st.expander("规则预配置（可添加多条）", expanded=False):
                            st.caption("在此为即将落地的业务预先配置时间规则（如账期、付款期限等），规则将在业务推进后生效。")
                            from ui.rule_components import show_rule_manager_tab
                            from logic.constants import TimeRuleRelatedType
                            show_rule_manager_tab(b['id'], TimeRuleRelatedType.BUSINESS)

    session.close()

# show_supply_chain_mgmt 已完全拆解到 show_supply_chain_list 和 show_supply_chain_import 中
# def show_supply_chain_mgmt(): ...

def show_business_execution():
    """业务运营 - 已重构为使用 queries 层"""
    st.subheader("业务运营")

    session = get_session()
    
    sel_sub_tab = sac.tabs([
        sac.TabsItem('设备采购', icon='cart-plus'),
        sac.TabsItem('物料供应', icon='box-arrow-right'),
        sac.TabsItem('物料采购', icon='cart-check'),
        sac.TabsItem('退货操作', icon='arrow-return-left'),
        sac.TabsItem('合同概览', icon='eye'),
    ], align='center', variant='outline', key='business_execution_sub_tabs')
    
    # 使用 queries 层获取执行业务列表
    businesses = get_businesses_for_execution()
    
    if sel_sub_tab == '设备采购':
        st.write("### 设备采购")
        
        proc_mode = sac.segmented(
            items=[
                sac.SegmentedItem(label='客户采购', icon='person-check'),
                sac.SegmentedItem(label='库存采购', icon='box-arrow-in-down'),
                sac.SegmentedItem(label='库存拨付', icon='box-arrow-right'),
            ], align='center', size='sm', key='proc_mode_segment'
        )
        
        if proc_mode == '客户采购':
            st.caption("为特定客户业务采购设备，部署到客户点位")
            if businesses:
                for b in businesses:
                    cust_name = b['customer_name']
                    with st.expander(f"业务ID: {b['id']} | 客户: {cust_name}"):
                        if st.button("发起设备采购", key=f"proc_btn_{b['id']}"):
                            st.session_state[f"proc_form_{b['id']}"] = True
                        
                        if st.session_state.get(f"proc_form_{b['id']}"):
                            show_procurement_form(session, b)
            else:
                st.info("当前没有正式开展中的业务。")
        
        elif proc_mode == '库存采购':
            st.caption("不关联客户，向供应商采购设备入自有仓，作为库存储备")
            show_stock_procurement_form(session)
        
        elif proc_mode == '库存拨付':
            st.caption("从现有库存设备中拨付到客户业务，无需重新采购")
            show_inventory_allocation_form(session, businesses)

    elif sel_sub_tab == '物料供应':
        st.write("### 物料供应 (针对生效业务)")
        if businesses:
            for b in businesses:
                cust_name = b['customer_name']
                with st.expander(f"业务ID: {b['id']} | 客户: {cust_name}"):
                    if st.button("发起物料供应", key=f"supply_btn_{b['id']}"):
                        st.session_state[f"supply_form_{b['id']}"] = True
                    
                    if st.session_state.get(f"supply_form_{b['id']}"):
                        show_supply_form(session, b)
        else:
            st.info("当前没有正式开展中的业务。")

    elif sel_sub_tab == '物料采购':
        st.write("### 独立物料采购 (补充库存)")
        show_material_procurement_form(session)
    
    elif sel_sub_tab == '退货操作':
        st.markdown("### <i class='bi bi-arrow-return-left'></i> 退货/售后管理", unsafe_allow_html=True)
        
        # 1. 选择要退货的原订单 - 使用 queries 层
        returnable_vcs = get_returnable_vcs(
            vc_types=[VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT, VCType.MATERIAL_SUPPLY, VCType.MATERIAL_PROCUREMENT],
            statuses=[VCStatus.FINISH, VCStatus.EXE],
            subject_statuses=[SubjectStatus.SIGNED, SubjectStatus.FINISH, SubjectStatus.SHIPPED]
        )
        
        vc_opts = {f"{v['id']}: {v['description']} ({v['type']} - {v['subject_status']})": v for v in returnable_vcs}
        
        if not vc_opts:
            st.info("当前没有可进行退货操作的订单（需处于发货/签收/完成状态）")
        else:
            sel_vc_label = st.selectbox("选择关联的原订单", options=list(vc_opts.keys()))
            target_vc = vc_opts[sel_vc_label]
            
            # --- 业务深度定制逻辑 ---
            if target_vc['type'] == VCType.EQUIPMENT_PROCUREMENT:
                sel_direction_label = st.radio(
                    "选择退货业务流向",
                    options=list(ReturnDirection.UI_LABELS.values()),
                    help="客户向我们退回：物品从点位/客户处回库；向供应商退货：物品所有权转移回供应商（涉及货款退款）",
                    horizontal=True
                )
                return_direction = ReturnDirection.from_ui(sel_direction_label)
            elif target_vc['type'] == VCType.MATERIAL_PROCUREMENT:
                return_direction = ReturnDirection.US_TO_SUPPLIER
                st.info(f"💡 当前业务流向：{ReturnDirection.UI_LABELS[return_direction]}")
            elif target_vc['type'] == VCType.MATERIAL_SUPPLY:
                return_direction = ReturnDirection.CUSTOMER_TO_US
                st.info(f"💡 当前业务流向：{ReturnDirection.UI_LABELS[return_direction]}")
            else:
                return_direction = SystemConstants.UNKNOWN
            
            st.divider()
            
            # 2. 定制化解析物品明细
            origin_items = []
            elements = target_vc['elements'] or {}

            # 使用新的 query 函数获取退货目的地选项
            receiving_pts = get_valid_receiving_points_for_return(session, target_vc['id'], return_direction)
            point_options = [f"{p['name']} ({p['type']})" for p in receiving_pts]

            # 构建点位名称->Point ID 映射（使用带类型的显示名）
            point_map = {f"{p['name']} ({p['type']})": p['id'] for p in receiving_pts}

            # 2. 调用 Service 层获取精算后的可退明细
            origin_items = get_returnable_items(session, target_vc['id'], return_direction)

            # 根据退货类型确定小计标签
            if target_vc['type'] == VCType.EQUIPMENT_PROCUREMENT:
                subtotal_label = "📊 货品押金小计"
            else:
                subtotal_label = "📊 货品价值小计"

            if not origin_items:
                st.warning("当前无符合退货条件的物品（检查运营状态或订单明细）")
            else:
                # 3. 退货明细编辑
                r_key = f"return_df_v2_{target_vc['id']}_{return_direction}"
                
                # --- 优化：自动检测数据变化并刷新缓存 ---
                # 使用当前可退货设备的 SN 列表作为缓存验证签名
                current_sns = sorted([item.get("sn", "-") for item in origin_items])
                cache_signature_key = f"{r_key}_signature"
                cached_signature = st.session_state.get(cache_signature_key, [])
                
                # 如果签名不匹配（设备列表有变化），自动清除旧缓存
                if cached_signature != current_sns:
                    if r_key in st.session_state:
                        del st.session_state[r_key]
                    st.session_state[cache_signature_key] = current_sns
                
                # 顶部显示设备数量和手动刷新按钮
                top_col1, top_col2 = st.columns([4, 1])
                top_col1.caption(f"📋 共 {len(origin_items)} 项可退货设备/物品")
                if top_col2.button("🔄 刷新", key=f"refresh_{r_key}", help="手动刷新以获取最新数据"):
                    if r_key in st.session_state: del st.session_state[r_key]
                    if cache_signature_key in st.session_state: del st.session_state[cache_signature_key]
                    st.rerun()

                if r_key not in st.session_state:
                    init_data = []
                    for i, item in enumerate(origin_items):
                        row = {
                            "SKU": item["sku_name"],
                            "SN码": item.get("sn", "-"),
                            "批次": item.get("batch_no") or "-",
                            "目前位置": item["point_name"],
                        }
                        if target_vc['type'] == VCType.EQUIPMENT_PROCUREMENT and return_direction == ReturnDirection.CUSTOMER_TO_US:
                            row["单台押金"] = item["deposit"]
                        else:
                            row["执行单价"] = item["price"]

                        row.update({
                            "可退数量": item["qty"],
                            "本次退货": 0,
                            "退货目的地": point_options[0] if point_options else SystemConstants.DEFAULT_POINT,
                            "_raw_idx": i
                        })
                        init_data.append(row)
                    st.session_state[r_key] = pd.DataFrame(init_data)
                
                # 配置列
                col_config = {
                    "SKU": st.column_config.TextColumn(disabled=True),
                    "SN码": st.column_config.TextColumn(disabled=True),
                    "批次": st.column_config.TextColumn(disabled=True),
                    "目前位置": st.column_config.TextColumn(disabled=True),
                    "可退数量": st.column_config.NumberColumn(disabled=True),
                    "本次退货": st.column_config.NumberColumn(min_value=0, max_value=None if target_vc['type'] != VCType.EQUIPMENT_PROCUREMENT else 1, step=1),
                    "退货目的地": st.column_config.SelectboxColumn("退货目的地", options=point_options),
                    "_raw_idx": None # 明确隐藏内部列
                }
                if "执行单价" in st.session_state[r_key].columns:
                    col_config["执行单价"] = st.column_config.NumberColumn(format="%.2f", disabled=True)
                if "单台押金" in st.session_state[r_key].columns:
                    col_config["单台押金"] = st.column_config.NumberColumn(format="%.2f", disabled=True)

                edited_return = st.data_editor(
                    st.session_state[r_key],
                    column_config=col_config,
                    use_container_width=True,
                    hide_index=True,
                    key=f"ret_editor_v2_{target_vc['id']}_{return_direction}"
                )
                
                # 计算总额
                calc_total = 0.0
                return_list = []
                for _, row in edited_return.iterrows():
                    qty = row["本次退货"]
                    if qty > 0:
                        val = row.get("单台押金", row.get("执行单价", 0.0))
                        calc_total += qty * val
                        
                        raw = origin_items[int(row["_raw_idx"])]
                        tgt_wh = row["退货目的地"]
                        tgt_point_id = point_map.get(tgt_wh)  # 从映射表获取 Point ID
                        return_list.append({
                            "sku_id": raw.get("sku_id"),
                            "sn": raw.get("sn"),
                            "sku_name": raw.get("sku_name"),
                            "price": raw["price"],
                            "deposit": raw.get("deposit", 0.0),
                            "qty": qty,
                            "point_id": raw.get("point_id"),
                            "point_name": raw.get("point_name"),
                            "target_point_id": tgt_point_id,
                            "receiving_point_name": tgt_wh
                        })
                
                st.info(f"{subtotal_label}: ¥{calc_total:,.2f}")
                
                # 物流与结算
                st.write("#### 2. 物流与资金结算")
                c_l1, c_l2 = st.columns(2)
                log_fee = c_l1.number_input("预计物流费用 (元)", min_value=0.0, key=f"ret_fee_{target_vc['id']}")
                bearer = c_l2.radio("物流承担方", [LogisticsBearer.SENDER, LogisticsBearer.RECEIVER], key=f"ret_bearer_{target_vc['id']}")
                
                # 退款计算
                # 只有涉及到“退款”的（非客户退回设备）才需要建议收回金额
                is_deposit_only = (target_vc['type'] == VCType.EQUIPMENT_PROCUREMENT and return_direction == ReturnDirection.CUSTOMER_TO_US)
                
                final_refund = calc_total
                if not is_deposit_only:
                    if bearer == "退货方承担 (自付)":
                        final_refund = max(0.0, calc_total - log_fee)
                    
                st.markdown(f"### 💰 建议待处理金额: ¥{final_refund:,.2f} {'(押金项)' if is_deposit_only else ''}")
                refund_reason = st.text_area("详细说明", placeholder="退货原因、物流单号预填等...", key=f"ret_reason_{target_vc['id']}")
                
                # === [新] 时间规则配置前移 ===
                st.divider()
                st.write("#### ⏱️ 追加退货相关时间规则")
                from models import TimeRule
                from logic.constants import TimeRuleRelatedType, TimeRuleInherit
                
                st.caption("📋 预期继承规则预览")
                parent_rules = get_inherited_rules_for_ui(target_vc['business_id'])
                
                if parent_rules:
                    st.dataframe(pd.DataFrame(parent_rules), use_container_width=True, hide_index=True)
                else:
                    st.caption("暂无继承规则")
                st.divider()
                
                btn_r1, btn_r2 = st.columns([2, 1])
                if btn_r1.button("🚀 生成退货执行单", type="primary", disabled=(len(return_list)==0), key=f"btn_ret_sub_{target_vc['id']}"):
                    # 进入弹窗确认
                    st.session_state[f"temp_return_data_{target_vc['id']}"] = {
                        "return_direction": return_direction,
                        "return_items": return_list,
                        "goods_amount": calc_total if not is_deposit_only else 0.0,
                        "deposit_amount": calc_total if is_deposit_only else 0.0,
                        "logistics_cost": log_fee,
                        "logistics_bearer": bearer,
                        "total_refund": final_refund,
                        "reason": refund_reason,
                        "extra_rules": st.session_state.get(f"return_extra_rules_{target_vc['id']}", []),
                        "description": f"退货({return_direction}): {target_vc['description']}"
                    }
                    st.session_state[f"show_return_confirm_{target_vc['id']}"] = True
                    st.rerun()

                from ui.rule_components import get_draft_rules_count, draft_rule_manager_dialog
                draft_key = f"return_{target_vc['id']}"
                draft_count = get_draft_rules_count(draft_key)

                rule_btn_label = f"⚙️ 合同规则 ({draft_count})" if draft_count > 0 else "⚙️ 合同规则"
                if btn_r2.button(rule_btn_label, key=f"btn_ret_rules_{target_vc['id']}", use_container_width=True):
                    st.session_state[f"trigger_draft_rule_mgr_{draft_key}"] = True
                    st.rerun()

                # 弹窗触发
                if st.session_state.get(f"trigger_draft_rule_mgr_{draft_key}"):
                    draft_rule_manager_dialog(draft_key, target_type="退货执行")


    elif sel_sub_tab == '合同概览':
        st.write("### 虚拟合同全局概览")
        
        # 过滤器区域
        col1, col2, col3, col4 = st.columns(4)
        all_st = [VCStatus.EXE, VCStatus.FINISH, VCStatus.TERMINATED]
        all_sub = [SubjectStatus.EXE, SubjectStatus.SHIPPED, SubjectStatus.SIGNED, SubjectStatus.FINISH]
        all_ca = [CashStatus.EXE, CashStatus.PREPAID, CashStatus.FINISH]
        all_types = [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT, VCType.INVENTORY_ALLOCATION, VCType.MATERIAL_PROCUREMENT, VCType.MATERIAL_SUPPLY, VCType.RETURN]
        
        sel_st = col1.multiselect("总体状态", all_st, default=all_st)
        sel_sub = col2.multiselect("标的状态", all_sub, default=all_sub)
        sel_ca = col3.multiselect("资金状态", all_ca, default=all_ca)
        sel_type = col4.multiselect("合同类型", all_types, default=all_types)
        
        # 使用 queries 层获取虚拟合同列表
        results = get_vc_list_for_overview(
            status_list=sel_st if sel_st else None,
            subject_status_list=sel_sub if sel_sub else None,
            cash_status_list=sel_ca if sel_ca else None,
            type_list=sel_type if sel_type else None
        )
        
        if results:
            df_data = pd.DataFrame([
                {
                    "ID": r['id'],
                    "类型": r['type'],
                    "业务描述": r['description'],
                    "总体状态": r['status'],
                    "标的状态": r['subject_status'],
                    "资金状态": r['cash_status'],
                    "更新时间": r['created_at']
                } for r in results
            ])
            
            # 使用带有选择功能的 dataframe
            event = st.dataframe(
                df_data, 
                use_container_width=True, 
                on_select="rerun", 
                selection_mode="single-row",
                height=350,
                key="vc_overview_table"
            )
            
            # 处理选择事件
            selected_rows = event.get("selection", {}).get("rows", [])
            if selected_rows:
                idx = selected_rows[0]
                target_vc_id = int(df_data.iloc[idx]["ID"])
                vc = get_vc_detail(target_vc_id)
                
                if vc:
                    elements = vc['elements'] or {}
                    st.divider()
                    st.markdown(f"#### <i class='bi bi-file-text'></i> 虚拟合同详情 (ID: {vc['id']})", unsafe_allow_html=True)
                    
                    sel_ov_tab = sac.tabs([
                        sac.TabsItem('交易详情', icon='file-earmark-text'),
                        sac.TabsItem('数据修正与管理', icon='pencil-square'),
                        sac.TabsItem('规则管理', icon='shield-check'),
                    ], align='center', variant='outline', key=f"vc_ov_tabs_{vc['id']}")
                    
                    if sel_ov_tab == '交易详情':
                        # 0. 关键摘要信息
                        # 逻辑穿透：针对退货等类型，如果自身没有关联 ID，则追溯原始合同
                        effective_vc = vc
                        if not (vc['business_id'] or vc['supply_chain_id']) and vc['related_vc_id']:
                            effective_vc = get_vc_detail(vc['related_vc_id']) or vc
                        
                        biz_info = "无关联项目"
                        if effective_vc['business_id']:
                            biz = get_business_detail(effective_vc['business_id'])
                            if biz:
                                biz_info = f"{biz['customer_name']} (业务ID:{biz['id']})"
                        
                        supp_info = "无关联供应商"
                        if effective_vc['supply_chain_id']:
                            sc = get_supply_chain_by_id(effective_vc['supply_chain_id'])
                            if sc:
                                supp_info = f"{sc['supplier_name']} (协议ID:{sc['id']})"
                        
                        st.markdown(f"""
                        <div style='background: #f8fafc; border-left: 5px solid #64748b; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>
                            <div style='display: flex; flex-wrap: wrap; gap: 35px;'>
                                <div><span style='color:#64748b; font-size:12px; font-weight:bold;'><i class='bi bi-journal-text'></i> 虚拟合同类型</span><br><span style='color:#1e293b; font-size:14px; font-weight:500;'>{vc['type']}</span></div>
                                <div><span style='color:#64748b; font-size:12px; font-weight:bold;'><i class='bi bi-building'></i> 关联业务</span><br><span style='color:#1e293b; font-size:14px; font-weight:500;'>{biz_info}</span></div>
                                <div><span style='color:#64748b; font-size:12px; font-weight:bold;'><i class='bi bi-truck'></i> 供应商</span><br><span style='color:#1e293b; font-size:14px; font-weight:500;'>{supp_info}</span></div>
                                <div style='flex-grow: 1;'><span style='color:#64748b; font-size:12px; font-weight:bold;'><i class='bi bi-card-text'></i> 项目描述</span><br><span style='color:#1e293b; font-size:14px;'>{vc['description'] or "未录入"}</span></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # 1. 状态看板

                        # 时间戳折叠展示
                        with st.expander("状态变更历史时间线"):
                            # 从日志表查询完整历史
                            logs = get_vc_status_logs(vc['id'])
                            
                            if logs:
                                t_col1, t_col2, t_col3 = st.columns(3)
                                with t_col1:
                                    st.write("**总体状态记录**")
                                    for l in [x for x in logs if x['category'] == 'status']:
                                        st.caption(f"{l['status_name']}: {l['timestamp']}")
                                with t_col2:
                                    st.write("**标的状态记录**")
                                    for l in [x for x in logs if x['category'] == 'subject']:
                                        st.caption(f"{l['status_name']}: {l['timestamp']}")
                                with t_col3:
                                    st.write("**资金状态记录**")
                                    for l in [x for x in logs if x['category'] == 'cash']:
                                        st.caption(f"{l['status_name']}: {l['timestamp']}")
                            else:
                                st.caption("暂无详细历史记录")
                        
                        # 2. 货品/服务明细表
                        st.markdown("##### <i class='bi bi-box-seam'></i> 包含货品/服务明细", unsafe_allow_html=True)
                        
                        display_type, items_data = format_vc_items_for_display(vc)
                        
                        if display_type == 'empty':
                            st.json(vc['elements'] or {}, expanded=False)
                        else:
                            st.dataframe(
                                pd.DataFrame(items_data), 
                                use_container_width=True,
                                height=200 if display_type == 'points' else "auto"
                            )

                        # 3. 财务概览
                        st.markdown("##### <i class='bi bi-credit-card'></i> 财务条款", unsafe_allow_html=True)
                        f_col1, f_col2, f_col3 = st.columns(3)
                        total_amt = (vc['elements'] or {}).get("total_amount", 0)
                        f_col1.metric("合同总金额", f"¥{total_amt:,.2f}")
                        
                        pay_terms = (vc['elements'] or {}).get("payment_terms", {})
                        if pay_terms:
                            p_ratio = pay_terms.get('prepayment_ratio', 0)
                            term_str = f"预付 {int(p_ratio * 100)}% | 尾款 {pay_terms.get('balance_period')}天"
                            f_col2.info(f"**结算**: {term_str}")
                        
                        dep_info = vc['deposit_info'] or {}
                        if dep_info:
                            f_col3.metric("应收/付押金", f"¥{dep_info.get('should_receive', 0):,.2f}")

                        # 4. 关联物流信息
                        st.markdown("---")
                        st.markdown("##### <i class='bi bi-truck'></i> 关联物流进度", unsafe_allow_html=True)
                        logs_log = get_logistics_list_by_vc(vc['id'])
                        if logs_log:
                            for idx, l in enumerate(logs_log, 1):
                                l_col1, l_col2 = st.columns([1, 4])
                                l_col1.markdown(f"**物流批次 #{idx}**")
                                l_col1.caption(f"状态: {l['status']}")
                                l_col1.caption(f"创建: {l['timestamp']}")
                                
                                orders = l.get('orders', [])
                                if orders:
                                    order_data = []
                                    for o in orders:
                                        order_data.append({
                                            "单号": o['tracking_number'],
                                            "状态": o['status'],
                                            "发货点位": o.get('发货点位', '未知'),
                                            "收货点位": o.get('收货点位', '未知'),
                                            "品类明细": ", ".join([f"{i.get('sku_name') or 'N/A'} x{i.get('qty') or 0}" for i in o.get('items', [])])
                                        })
                                    l_col2.dataframe(
                                        pd.DataFrame(order_data), 
                                        use_container_width=True, 
                                        hide_index=True, 
                                        height=215 if len(order_data) > 5 else "auto"
                                    )
                                else:
                                    l_col2.info("该物流阶段尚无运单记录")
                        else:
                            st.info("该合同暂无关联物流记录")

                        # 5. 资金流流水
                        st.markdown("---")
                        st.markdown("##### <i class='bi bi-cash-stack'></i> 关联资金流水", unsafe_allow_html=True)
                        cfs = get_vc_cash_flows(vc['id'])
                        if cfs:
                            cf_df = pd.DataFrame([
                                {
                                    "日期": cf['date'],
                                    "类型": cf['type'],
                                    "金额": cf['amount'],
                                    "备注": cf['description']
                                } for cf in cfs
                            ])
                            st.dataframe(
                                cf_df, 
                                use_container_width=True, 
                                hide_index=True,
                                column_config={
                                    "金额": st.column_config.NumberColumn("金额", format="¥%.2f")
                                }
                            )
                        else:
                            st.info("该合同暂无资金往来记录")

                    elif sel_ov_tab == '数据修正与管理':
                        st.warning("此处修改直接影响数据库底层数据，请谨慎操作")
                        with st.form(f"edit_vc_form_{vc['id']}"):
                            new_desc = st.text_input("业务项目描述", value=vc['description'])
                            
                            import json
                            elements_json = json.dumps(vc['elements'], indent=4, ensure_ascii=False)
                            st.markdown("**<i class='bi bi-code-square'></i> 交易要素明细 (JSON 格式)**", unsafe_allow_html=True)
                            new_elements_str = st.text_area("修改核心数据", value=elements_json, height=280)
                            
                            deposit_json = json.dumps(vc['deposit_info'], indent=4, ensure_ascii=False) if vc['deposit_info'] else "{}"
                            st.markdown("**<i class='bi bi-wallet2'></i> 押金信息 (JSON 格式)**", unsafe_allow_html=True)
                            new_deposit_str = st.text_area("修改押金配置", value=deposit_json, height=120)
                            
                            c1, c2 = st.columns([1, 1])
                            if c1.form_submit_button("提交底数修正"):
                                try:
                                    from logic.vc.schemas import UpdateVCSchema
                                    e_data = json.loads(new_elements_str)
                                    d_data = json.loads(new_deposit_str) if new_deposit_str.strip() else {}
                                    payload = UpdateVCSchema(id=vc['id'], description=new_desc, elements=e_data, deposit_info=d_data)
                                    result = update_vc_action(session, payload)
                                    if result.success:
                                        st.success(result.message)
                                        st.rerun()
                                    else: st.error(result.error)
                                except Exception as e:
                                    st.error(f"解析 JSON 失败: {e}")
                            
                            # 删除逻辑
                            can_delete = (vc['status'] == VCStatus.EXE and vc['subject_status'] == SubjectStatus.EXE and vc['cash_status'] == CashStatus.EXE)
                            if c2.form_submit_button("删除此虚拟合同", disabled=not can_delete):
                                result = delete_vc_action(session, vc['id'])
                                if result.success:
                                    st.success(result.message)
                                    st.rerun()
                                else: st.error(result.error)
                            
                            if not can_delete:
                                st.caption("提示：仅当所有状态均为'执行'时才允许物理删除。")
                    
                    elif sel_ov_tab == '规则管理':
                        from ui.rule_components import show_rule_manager_tab
                        from logic.constants import TimeRuleRelatedType
                        show_rule_manager_tab(vc['id'], TimeRuleRelatedType.VIRTUAL_CONTRACT)
    # 库存看板已移至单独页面
    pass

    session.close()

def show_procurement_form(session, business):
    """设备批量采购申请 - 已重构为使用 queries 层"""
    st.markdown("### <i class='bi bi-hdd-network'></i> 设备批量采购申请", unsafe_allow_html=True)
    st.caption("基于已建立的供应链协议发起执行需求。支持从 Excel 直接粘贴部署点位与品类数据。")

    # 1. 选择供应链主体 - 使用 queries 层
    sc_result = get_supply_chain_with_pricing(session, SKUType.EQUIPMENT)
    chain_options = {f"{sc['supplier_name']} (协议ID:{sc['id']})": sc['id'] for sc in sc_result}
    
    if not chain_options:
        st.warning("当前没有可用的设备供应链协议，请先在【管理面板】中建立。")
        return

    sc_label = st.selectbox("选择协议主约 (供应链)", list(chain_options.keys()), key=f"sc_sel_proc_{business['id']}")
    sc = get_supply_chain_by_id(chain_options[sc_label])
    if not sc:
        st.error("无法加载供应链协议详情")
        return
    
    # 2. 协议配置查询
    pricing = sc['pricing_dict']
    payment = sc['payment_terms'] or {}
    sku_list = list(pricing.keys())

    # 3. 客户点位查询（收货点 = 客户所有点位，不限类型）
    c_points = get_valid_receiving_points_for_procurement(session, business['id'])
    point_list = [f"{p['name']} ({p['type']})" for p in c_points]
    point_map = {f"{p['name']} ({p['type']})": p['id'] for p in c_points}

    if not sku_list:
        st.error("该供应链协议中未配置任何品类价格，请先完善协议。")
        return

    # 4. 初始化表格数据
    if f"proc_df_{business['id']}" not in st.session_state:
        st.session_state[f"proc_df_{business['id']}"] = pd.DataFrame(
            columns=["部署点位", "设备品类", "采购数量", "执行单价", "单台押金"]
        )

    # --- 核心交互逻辑：捕获数据编辑器的变更并实时更新 (通过版本切换避免 Key 冲突异常) ---
    df_key = f"proc_df_{business['id']}"
    version_key = f"proc_ver_{business['id']}"
    if version_key not in st.session_state: st.session_state[version_key] = 0
    
    editor_key = f"proc_editor_{business['id']}_{st.session_state[version_key]}"
    biz_agreement = business.get('details', {}).get("pricing", {})

    # 检查是否有待处理的编辑动作
    if editor_key in st.session_state:
        state = st.session_state[editor_key]
        if state.get("edited_rows") or state.get("added_rows") or state.get("deleted_rows"):
            df = st.session_state[df_key].copy()
            
            # 1. 处理删除
            if state.get("deleted_rows"):
                df = df.drop(index=state["deleted_rows"]).reset_index(drop=True)
            
            # 2. 处理修改
            for idx_str, change in state.get("edited_rows", {}).items():
                idx = int(idx_str)
                if idx < len(df):
                    for col, val in change.items():
                        df.at[idx, col] = val
                        if col == "设备品类":
                            u_price, u_dep, _ = get_sku_agreement_price(session, sc['id'], business, val)
                            df.at[idx, "执行单价"] = u_price
                            df.at[idx, "单台押金"] = u_dep

            # 3. 处理新增
            for row_data in state.get("added_rows", []):
                if "设备品类" in row_data:
                    sku = row_data["设备品类"]
                    u_price, u_dep, _ = get_sku_agreement_price(session, sc['id'], business, sku)
                    row_data["执行单价"] = u_price
                    row_data["单台押金"] = u_dep
                if "采购数量" not in row_data: row_data["采购数量"] = 0
                df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)

            # 更新数据并切换版本号以重置组件
            st.session_state[df_key] = df
            st.session_state[version_key] += 1
            
            # 关键修复：强制刷新 SKU 列表前，清理所有可能残留的规则管理触发键，防止弹窗自动跳出
            for k in list(st.session_state.keys()):
                if k.startswith("trigger_rule_mgr_"):
                    del st.session_state[k]
            st.rerun()

    st.markdown(f"""
    <div style='background-color: rgba(30, 144, 255, 0.1); padding: 10px; border-radius: 5px; border-left: 4px solid #1E90FF; margin-bottom: 1rem;'>
        <b>结算条款继承：</b> 预付 {int(payment.get('prepayment_ratio',0)*100)}% | 
        尾款 {payment.get('balance_period',0)} {payment.get('day_rule', SettlementRule.NATURAL_DAY)} | 
        起算: {payment.get('start_trigger', SettlementRule.TRIGGER_INBOUND)}
    </div>
    """, unsafe_allow_html=True)

    edited_df = st.data_editor(
        st.session_state[df_key].reset_index(drop=True),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "部署点位": st.column_config.SelectboxColumn("部署/收货点位", options=point_list),
            "设备品类": st.column_config.SelectboxColumn("协议内品类", options=sku_list),
            "采购数量": st.column_config.NumberColumn("采购数量", min_value=0, step=1),
            "执行单价": st.column_config.NumberColumn("执行单价 (元)", format="%.2f"),
            "单台押金": st.column_config.NumberColumn("单台押金 (元)", format="%.2f")
        },
        hide_index=True,
        key=editor_key
    )
    
    # 及时保存最新的编辑结果
    st.session_state[df_key] = edited_df

    # === [新] 时间规则配置前移 ===
    st.divider()
    st.divider()
    st.markdown("#### <i class='bi bi-clock-history'></i> 时间规则与结算配置", unsafe_allow_html=True)
    
    # A. 预览即将继承的规则
    st.caption("预期继承自协议的规则预览")
    
    parent_rules = get_inherited_rules_for_ui(business['id'], sc['id'])
    
    if parent_rules:
        st.dataframe(pd.DataFrame(parent_rules), use_container_width=True, hide_index=True)
    else:
        st.caption("暂无继承规则 (将根据结算条款生成标准付款规则)")

    st.divider()
    from ui.rule_components import get_draft_rules_count, draft_rule_manager_dialog
    draft_key = f"proc_{business['id']}"
    draft_count = get_draft_rules_count(draft_key)
    
    btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
    if btn_col1.button("确认提交 (进入复核)", type="primary", key=f"btn_p_sub_{business['id']}", use_container_width=True):
        valid_items = []
        total_amt = 0.0
        total_deposit = 0.0
        
        mats = get_skus_by_names(sku_list, supplier_id=sc['supplier_id'])
        sku_id_map = {s['name']: s['id'] for s in mats}

        for idx, row in edited_df.iterrows():
            # 过滤没有任何输入的纯空行
            has_any_val = row["部署点位"] or row["设备品类"] or (row["采购数量"] and row["采购数量"] > 0)
            if not has_any_val: continue
            
            # 强制检查：有效项必须三要素齐全
            if not row["部署点位"] or not row["设备品类"] or not (row["采购数量"] and row["采购数量"] > 0):
                st.error(f"提交失败：第 {idx+1} 行信息不完整。请确保【部署点位】、【设备品类】已选且【采购数量】大于 0。")
                return

            p_id = point_map.get(row["部署点位"])
            s_id = sku_id_map.get(row["设备品类"])
            qty = int(row["采购数量"])
            price = float(row["执行单价"])
            dep = float(row["单台押金"])
            
            valid_items.append({
                "sku_id": s_id, "sku_name": row["设备品类"],
                "point_id": p_id, "point_name": row["部署点位"],
                "qty": qty, "price": price, "deposit": dep,
                "shipping_point_name": f"{sc['supplier_name']}仓库" if sc.get('supplier_name') else SystemConstants.DEFAULT_POINT
            })
            total_amt += qty * price
            total_deposit += qty * dep

        if valid_items:
            # 不直接保存，而是存入临时 Session 并触发弹窗
            st.session_state[f"temp_proc_data_{business['id']}"] = {
                "items": valid_items,
                "total_amt": total_amt,
                "total_deposit": total_deposit,
                "sc_id": sc['id'],
                "payment": payment,
                "description": f"设备采购: {len(valid_items)}项部署计划 (来自 {sc['supplier_name']})"
            }
            st.session_state[f"show_proc_confirm_{business['id']}"] = True
            st.rerun()
        else:
            st.error("请输入至少一项有效的采购数量（必须大于0）")

    if btn_col2.button("取消并重置", key=f"btn_p_can_{business['id']}", use_container_width=True):
        del st.session_state[f"proc_df_{business['id']}"]
        # 同时清理草稿规则
        for k in list(st.session_state.keys()):
            if f"draft_" in k and draft_key in k:
                del st.session_state[k]
        st.rerun()
    
    rule_btn_label = f"合同规则 ({draft_count})" if draft_count > 0 else "合同规则"
    if btn_col3.button(rule_btn_label, key=f"btn_p_rules_{business['id']}", use_container_width=True):
        st.session_state[f"trigger_draft_rule_mgr_{draft_key}"] = True
        st.rerun()
    
    # 弹窗触发
    if st.session_state.get(f"trigger_draft_rule_mgr_{draft_key}"):
        draft_rule_manager_dialog(draft_key, target_type="采购合同")


def show_supply_form(session, business):
    st.markdown("### <i class='bi bi-box-seam-fill'></i> 高级物料供应录入", unsafe_allow_html=True)
    
    # 1. 准备批次级库存数据
    batch_rows = get_material_inventory_all()
    if not batch_rows:
        st.warning("当前物料库存全部为空，无法进行供应。请先执行【物料采购】入库。")
        return

    # 构建 SKU 维度数据（汇总 + 列表）
    sku_name_to_id = {}
    for r in batch_rows:
        sn = r["sku_name"]
        sku_name_to_id[sn] = r["sku_id"]
    sku_list = sorted(sku_name_to_id.keys())

    # 构建批次级下拉选项
    # batch_options_by_sku: sku_name -> [batch_no, ...]
    batch_options_by_sku = {}
    # point_options_by_sku_batch: (sku_name, batch_no) -> [(point_name, qty), ...]
    point_options_by_sku_batch = {}
    for r in batch_rows:
        sn = r["sku_name"]
        bn = r["batch_no"]
        pt = r["point_name"]
        qty = r["qty"]
        if bn not in batch_options_by_sku.get(sn, []):
            batch_options_by_sku.setdefault(sn, []).append(bn)
        batch_options_by_sku[sn] = sorted(batch_options_by_sku[sn])
        point_options_by_sku_batch.setdefault((sn, bn), []).append((pt, qty))

    # 所有批次选项（用于 data_editor 列配置）
    all_batch_options = sorted(set(r["batch_no"] for r in batch_rows))
    # 所有点位选项
    all_point_options = sorted(set(r["point_name"] for r in batch_rows))

    # --- 环境准备 ---
    df_key = f"supply_df_{business['id']}"
    editor_key = f"supply_editor_{business['id']}"

    st.markdown(f"""
    <div style='background-color: rgba(109, 40, 217, 0.1); padding: 1rem; border-radius: 10px; border-left: 5px solid #6D28D9; margin-bottom: 1rem;'>
        <b>库存优先模式：</b> 可选物料仅限当前库存 > 0 的品类。提交前系统将校验总供应量是否超出库存。
    </div>
    """, unsafe_allow_html=True)

    # 2. 准备收货点位（客户点位，用于"配送点位"列）
    c_points = get_valid_receiving_points_for_material_supply(session, business['id'])
    recv_point_list = sorted([f"{p['name']} ({p['type']})" for p in c_points])
    recv_point_detail_map = {f"{p['name']} ({p['type']})": {"id": p['id'], "address": p.get('address', '')} for p in c_points}

    # 3. 初始化/获取数据状态
    if df_key not in st.session_state:
        st.session_state[df_key] = pd.DataFrame(
            columns=["配送点位", "选择库存物料", "物料批次", "发货仓库", "供应数量", "执行单价"]
        )

    # 获取价格协议
    pricing_config = business.get('details', {}).get("pricing", {})
    payment = business.get('details', {}).get("payment_terms", {})

    def _default_point_for(sku, batch):
        opts = point_options_by_sku_batch.get((sku, batch), [])
        return opts[0][0] if opts else SystemConstants.DEFAULT_POINT

    def _default_batch_for(sku):
        return batch_options_by_sku.get(sku, [None])[0]

    # ── 快速录入区（自定义表单）───────────────────────────────────────────
    st.markdown("##### **快速添加批次明细**")

    # 统一行高 CSS
    st.markdown("""
    <style>
    .add-row-btn > button { height: 34px; line-height: 34px; padding-top: 0; padding-bottom: 0; font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

    add_cols = st.columns([2, 2, 2, 2, 1, 1])
    with add_cols[0]:
        add_recv = st.selectbox("配送点位", recv_point_list, index=0, label_visibility="collapsed", key="add_recv")
    with add_cols[1]:
        sku_idx = sku_list.index(st.session_state.get("add_sku", sku_list[0] if sku_list else "")) if st.session_state.get("add_sku", "") in sku_list else 0
        add_sku = st.selectbox("选择库存物料", sku_list, index=sku_idx, label_visibility="collapsed", key="add_sku")
    with add_cols[2]:
        batch_opts = batch_options_by_sku.get(add_sku, [])
        add_batch = st.selectbox("物料批次", batch_opts, index=0, label_visibility="collapsed", key="add_batch")
    with add_cols[3]:
        pt_opts = [pt for pt, _ in point_options_by_sku_batch.get((add_sku, add_batch), [])] if add_batch else []
        add_pt = st.selectbox("发货仓库", pt_opts, index=0, label_visibility="collapsed", key="add_pt")
    with add_cols[4]:
        add_qty = st.number_input("数量", value=1, min_value=1, step=1, label_visibility="collapsed", key="add_qty")
    with add_cols[5]:
        if st.button("➕", key="add_row_btn", help="添加一行"):
            auto_price, _, _ = get_sku_agreement_price(session, None, business, add_sku) if add_sku else 0.0
            existing = st.session_state.get(df_key, pd.DataFrame())
            new_row = pd.DataFrame([{
                "配送点位": add_recv,
                "选择库存物料": add_sku,
                "物料批次": add_batch,
                "发货仓库": add_pt,
                "供应数量": add_qty,
                "执行单价": auto_price,
            }])
            st.session_state[df_key] = pd.concat([existing, new_row], ignore_index=True)
            st.rerun()

    st.markdown("---")

    # ── 已有明细表格（data_editor）────────────────────────────────────────
    edited_df = st.data_editor(
        st.session_state.get(df_key, pd.DataFrame(
            columns=["配送点位", "选择库存物料", "物料批次", "发货仓库", "供应数量", "执行单价"]
        )),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "配送点位": st.column_config.SelectboxColumn("配送点位", options=recv_point_list),
            "选择库存物料": st.column_config.SelectboxColumn("选择库存物料", options=sku_list),
            "物料批次": st.column_config.SelectboxColumn("物料批次", options=all_batch_options),
            "发货仓库": st.column_config.SelectboxColumn("发货仓库", options=all_point_options),
            "供应数量": st.column_config.NumberColumn("供应数量", min_value=1, step=1),
            "执行单价": st.column_config.NumberColumn("执行单价", format="%.2f"),
        },
        hide_index=True,
        key=editor_key
    )
    st.session_state[df_key] = edited_df

    # --- 实时总金额预览 ---
    preview_total = 0.0
    for _, row in edited_df.iterrows():
        try:
            q = float(row["供应数量"]) if not pd.isna(row["供应数量"]) else 0.0
            p = float(row["执行单价"]) if not pd.isna(row["执行单价"]) else 0.0
            preview_total += q * p
        except:
            pass
    st.info(f"💰 当前明细总金额：**¥{preview_total:,.2f}**")

    # === [新] 时间规则配置前移 ===
    st.divider()
    st.markdown("#### <i class='bi bi-clock-history'></i> 时间规则与结算配置", unsafe_allow_html=True)
    
    st.caption("预期继承自协议的规则预览")
    from models import TimeRule
    from logic.constants import TimeRuleRelatedType, TimeRuleInherit
    
    parent_rules = get_inherited_rules_for_ui(business['id'])
    
    if parent_rules:
        st.dataframe(pd.DataFrame(parent_rules), use_container_width=True, hide_index=True)
    else:
        st.caption("暂无继承规则 (将根据结算条款生成标准付款规则)")

    st.divider()
    col1, col2, col3 = st.columns([2, 1, 1])
    submit_btn = col1.button("生成并提交供应单", type="primary", key=f"btn_sub_{business['id']}", use_container_width=True)
    if submit_btn:
        # A. 调用 Service 层进行库存充足性校验
        check_items = []
        for _, row in edited_df.iterrows():
            check_items.append((row["选择库存物料"], row["发货仓库"], row["供应数量"]))

        is_ok, over_stock = validate_inventory_availability(session, check_items)
        
        if not is_ok:
            st.error(f"供应确认失败：部分仓库可用库存不足！\n\n" + "\n- ".join(over_stock))
        else:
            # B. 构建虚拟合同 JSON
            supply_order = {
                "order_id": f"SO{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "order_time": datetime.now().isoformat(),
                "customer": {
                    "customer_id": business['customer_id'],
                    "name": business.get('customer_name', '未知客户'),
                    "business_id": business['id']
                },
                "summary": {
                    "total_skus": 0,
                    "total_qty": 0,
                    "total_amount": 0.0,
                    "sku_summary_list": []
                },
                "items": [],
                "payment_terms": business.get('details', {}).get("payment_terms", {})
            }

            sku_sums = {}

            # 构建发货仓库名 -> point_id 映射
            wh_name_to_id = {}
            for r in batch_rows:
                wh_name_to_id[r["point_name"]] = r["point_id"]

            for _, row in edited_df.iterrows():
                p_name = row["选择库存物料"]
                p_id = recv_point_detail_map[row["配送点位"]]["id"]
                sku_id = sku_name_to_id[p_name]
                qty = int(row["供应数量"])
                price = float(row["执行单价"])
                src_wh = row["发货仓库"]
                batch_no = row.get("物料批次") or ""

                # 汇总
                sku_sums[p_name] = sku_sums.get(p_name, 0) + qty
                supply_order["summary"]["total_qty"] += qty
                supply_order["summary"]["total_amount"] += qty * price

                # 统一 flat items 结构（与其他 VC 类型保持一致）
                supply_order["items"].append({
                    "sku_id": sku_id,
                    "sku_name": p_name,
                    "batch_no": batch_no,
                    "qty": qty,
                    "price": price,
                    "shipping_point_name": src_wh,
                    "shipping_point_id": wh_name_to_id.get(src_wh, 0),
                    "receiving_point_id": p_id,
                    "receiving_point_name": row["配送点位"],
                    "receiving_point_address": recv_point_detail_map[row["配送点位"]]["address"],
                })

            supply_order["summary"]["total_skus"] = len(sku_sums)
            supply_order["summary"]["sku_summary_list"] = [{"sku_name": k, "total_qty": v} for k, v in sku_sums.items()]

            # 增加顶层字段以保持与其他虚拟合同类型的兼容性
            supply_order["total_amount"] = supply_order["summary"]["total_amount"]

            if supply_order["items"]:
                # 改为弹窗确认模式
                st.session_state[f"temp_supply_data_{business['id']}"] = {
                    "order": supply_order,
                    "extra_rules": st.session_state.get(f"supply_extra_rules_{business['id']}", []),
                    "description": f"物料供应: {len(sku_sums)}项物料, 总计{supply_order['summary']['total_qty']}件"
                }
                st.session_state[f"show_supply_confirm_{business['id']}"] = True
                st.session_state[f"{wk}_submitted"] = True
                st.rerun()

    from ui.rule_components import get_draft_rules_count, draft_rule_manager_dialog
    draft_key = f"supply_{business['id']}"
    draft_count = get_draft_rules_count(draft_key)

    rule_btn_label = f"合同规则 ({draft_count})" if draft_count > 0 else "合同规则"
    if col2.button(rule_btn_label, key=f"btn_s_rules_{business['id']}", use_container_width=True):
        st.session_state[f"trigger_draft_rule_mgr_{draft_key}"] = True
        st.rerun()

    if col3.button("取消重置", key=f"btn_can_{business['id']}", use_container_width=True):
        if f"supply_df_{business['id']}" in st.session_state:
            del st.session_state[f"supply_df_{business['id']}"]
        # 清理草稿规则
        for k in list(st.session_state.keys()):
            if f"draft_" in k and draft_key in k:
                del st.session_state[k]
        st.rerun()
    
    # 弹窗触发
    if st.session_state.get(f"trigger_draft_rule_mgr_{draft_key}"):
        draft_rule_manager_dialog(draft_key, target_type="物料供应")

    # --- 结算协议摘要预览 ---
    st.markdown(f"""
    <div style='background-color: rgba(16, 185, 129, 0.1); padding: 10px; border-radius: 5px; border-left: 4px solid #10B981; margin-top: 10px;'>
        <b>结算模式：</b> 预付 {int(payment.get('prepayment_ratio',0)*100)}% | 
        尾款 {payment.get('balance_period',0)} {payment.get('day_rule', SettlementRule.NATURAL_DAY)}
    </div>
    """, unsafe_allow_html=True)


def show_material_procurement_form(session):
    st.markdown("### <i class='bi bi-cart-plus'></i> 物料批量采购录入", unsafe_allow_html=True)
    st.caption("基于已建立的供应链协议发起采购执行需求")
    
    sc_result = get_supply_chains_by_type(SKUType.MATERIAL)
    chain_options = {f"{sc['supplier_name']} (协议ID:{sc['id']})": sc['id'] for sc in sc_result}
    
    if not chain_options:
        st.warning("当前没有可用的物料供应链协议，请先在【管理面板】中建立。")
        return

    chain_label = st.selectbox("选择执行协议 (供应链)", list(chain_options.keys()))
    sc = get_supply_chain_by_id(chain_options[chain_label])
    if not sc:
        st.error("无法加载供应链协议详情")
        return
    
    # 提取协议配置
    pricing_config = sc['pricing_dict']
    sku_name_map = sc.get('sku_name_map', {})  # {sku_id: sku_name}
    payment = sc['payment_terms'] or {}
    # sku_list 用于 UI 显示（SKU 名称）
    sku_list = list(sku_name_map.values())

    # 反转映射：sku_name -> sku_id
    sku_name_to_id = {v: k for k, v in sku_name_map.items()}

    # 准备可用点位列表（统一按 Point 体系管理）
    # 发货点 = 供应商仓库；收货点 = 我们仓库 + 供应商仓库
    shipping_pts = get_valid_shipping_points_for_mat_procurement(session, sc['id'])
    receiving_pts = get_valid_receiving_points_for_mat_procurement(session, sc['id'])

    point_options = []   # 收货点选项（入库点位列）
    point_map = {}       # 显示名称 -> Point ID 映射
    # 保存发货点位：供应商点位中 ID 最小的（用于统一发货）
    _shipping_pt = min(shipping_pts, key=lambda p: p['id']) if shipping_pts else None
    _shipping_pt_name = _shipping_pt['name'] if _shipping_pt else SystemConstants.DEFAULT_POINT

    # 收货点选项
    for p in receiving_pts:
        display_name = f"{p['name']} ({p['type']})"
        point_options.append(display_name)
        point_map[display_name] = p['id']

    if not point_options:
        point_options = [SystemConstants.DEFAULT_POINT]
        point_map[SystemConstants.DEFAULT_POINT] = None

    # 初始化/切换协议时重置表格
    if f"mat_proc_df" not in st.session_state or st.session_state.get("mat_proc_sc_id") != sc['id']:
        initial_sku = sku_list[0] if sku_list else ""
        initial_price = 0.0
        # initial_sku 是 SKU 名称，需要转换为 sku_id 才能查询 pricing_config
        initial_sku_id = sku_name_to_id.get(initial_sku)
        if initial_sku_id and initial_sku_id in pricing_config:
            p_val = pricing_config[initial_sku_id]
            # get_pricing_dict() 返回 {sku_id: {"price": x}} 格式；旧格式直接是价格值
            if isinstance(p_val, dict):
                initial_price = float(p_val.get("price") or 0)
            else:
                initial_price = float(p_val) if p_val != "浮动" else 0.0

        st.session_state["mat_proc_df"] = pd.DataFrame([
            {"物料": initial_sku, "数量": 0, "单价": initial_price, "存放点位": point_options[0] if point_options else SystemConstants.DEFAULT_POINT}
        ])
        st.session_state["mat_proc_sc_id"] = sc['id']

    # --- 核心交互逻辑：捕获变动并实时联动价格 ---
    version_key = "mat_proc_ver"
    if version_key not in st.session_state: st.session_state[version_key] = 0
    editor_key = f"mat_proc_editor_{st.session_state[version_key]}"
    
    if editor_key in st.session_state:
        state = st.session_state[editor_key]
        if state.get("edited_rows") or state.get("added_rows") or state.get("deleted_rows"):
            df = st.session_state["mat_proc_df"].copy()
            
            # 1. 处理删除
            if state.get("deleted_rows"):
                df = df.drop(index=state["deleted_rows"]).reset_index(drop=True)
            
            # 2. 处理现有行的修改
            for idx_str, change in state.get("edited_rows", {}).items():
                idx = int(idx_str)
                if idx < len(df):
                    for col, val in change.items():
                        df.at[idx, col] = val
                        if col == "物料":
                            u_price, _, _ = get_sku_agreement_price(session, sc['id'], None, val)
                            df.at[idx, "单价"] = u_price

            # 3. 处理新增行
            for row_data in state.get("added_rows", []):
                if "物料" in row_data:
                    sku = row_data["物料"]
                    u_price, _, _ = get_sku_agreement_price(session, sc['id'], None, sku)
                    row_data["单价"] = u_price
                if "数量" not in row_data: row_data["数量"] = 0
                if "存放点位" not in row_data:
                    row_data["存放点位"] = point_options[0] if point_options else SystemConstants.DEFAULT_POINT
                df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)

            # 更新数据并切换版本以重置组件
            st.session_state["mat_proc_df"] = df
            st.session_state[version_key] += 1
            st.rerun()

    st.markdown(f"""
    <div style='background-color: rgba(46, 204, 113, 0.1); padding: 10px; border-radius: 5px; border-left: 4px solid #2ECC71; margin-bottom: 1rem;'>
        <b>结算协议摘要：</b> 预付 {int(payment.get('prepayment_ratio',0)*100)}% | 
        尾款账期 {payment.get('balance_period',0)} {payment.get('day_rule', SettlementRule.NATURAL_DAY)} | 
        起算点: {payment.get('start_trigger', SettlementRule.TRIGGER_INBOUND)}
    </div>
    """, unsafe_allow_html=True)

    edited_df = st.data_editor(
        st.session_state["mat_proc_df"].reset_index(drop=True),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "物料": st.column_config.SelectboxColumn("协议内物料品类", options=sku_list),
            "数量": st.column_config.NumberColumn("采购数量", min_value=0, step=1),
            "单价": st.column_config.NumberColumn("执行单价 (元)", format="%.2f", help="若协议价非浮动，系统将自动纠正"),
            "存放点位": st.column_config.SelectboxColumn("入库点位", options=point_options, help="选择采购后的存放点位")
        },
        hide_index=True,
        key=editor_key
    )

    st.session_state["mat_proc_df"] = edited_df.reset_index(drop=True)

    # === [新] 时间规则配置前移 ===
    st.divider()
    st.divider()
    st.write("#### <i class='bi bi-clock-history'></i> 时间规则与结算配置", unsafe_allow_html=True)
    
    st.caption("预期继承自协议的规则预览")
    from models import TimeRule
    from logic.constants import TimeRuleRelatedType, TimeRuleInherit
    
    parent_rules = get_inherited_rules_for_ui(0, sc['id']) # business_id set to 0 as it's not applicable
    
    if parent_rules:
        st.dataframe(pd.DataFrame(parent_rules), use_container_width=True, hide_index=True)
    else:
        st.caption("暂无继承规则 (将根据结算条款生成标准付款规则)")

    st.divider()
    btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
    if btn_col1.button("锁定采购并生成合同", type="primary", use_container_width=True):
        valid_items = []
        total_amt = 0.0
        for idx, row in edited_df.iterrows():
            p_name = row["物料"]
            w_name = row.get("存放点位")
            qty = row["数量"]

            # 过滤没有任何输入的纯空行
            if not p_name and not w_name and (not qty or qty <= 0): continue

            # 强制检查
            if not p_name or not w_name or not qty or qty <= 0:
                st.error(f"提交失败：第 {idx+1} 行信息不完整。请确保【物料】、【入库点位】已选且【采购数量】大于 0。")
                return

            item_price = float(row["单价"])
            w_name = row.get("存放点位", SystemConstants.DEFAULT_POINT)
            w_point_id = point_map.get(w_name)  # 从映射表获取 Point ID
            valid_items.append({
                "sku_id": sku_name_to_id.get(row["物料"]),
                "sku_name": row["物料"],
                "qty": row["数量"],
                "price": item_price,
                "point_id": w_point_id,
                "point_name": w_name,
                "shipping_point_name": _shipping_pt_name
            })
            total_amt += row["数量"] * item_price
        
        if valid_items:
            # 进入弹窗确认
            st.session_state["temp_mat_proc_data"] = {
                "items": valid_items,
                "total_amt": total_amt,
                "payment": payment,
                "extra_rules": st.session_state.get("mat_proc_extra_rules", [])
            }
            st.session_state["show_mat_proc_confirm"] = True
            st.rerun()
        else:
            st.error("请输入至少一项有效的物料及数量")

    from ui.rule_components import get_draft_rules_count, draft_rule_manager_dialog
    draft_key = f"mat_proc_{sc['id']}"
    draft_count = get_draft_rules_count(draft_key)

    rule_btn_label = f"合同规则 ({draft_count})" if draft_count > 0 else "合同规则"
    if btn_col2.button(rule_btn_label, key="btn_mp_rules", use_container_width=True):
        st.session_state[f"trigger_draft_rule_mgr_{draft_key}"] = True
        st.rerun()

    if btn_col3.button("清空并返回", use_container_width=True):
        del st.session_state["mat_proc_df"]
        # 清理草稿规则
        for k in list(st.session_state.keys()):
            if f"draft_" in k and draft_key in k:
                del st.session_state[k]
        st.rerun()

    # 弹窗触发 - 只在未打开其他 dialog 时打开规则管理
    if st.session_state.get(f"trigger_draft_rule_mgr_{draft_key}") and not st.session_state.get("mat_proc_confirm_dialog_open"):
        draft_rule_manager_dialog(draft_key, target_type="物料采购")


# =====================================================
# 新增：库存采购管理 (无 Business ID)
# =====================================================

def show_stock_procurement_form(session):
    st.markdown("### <i class='bi bi-box-arrow-in-down'></i> 库存采购单录入", unsafe_allow_html=True)
    st.caption("向供应商采购设备并直接入库存放（自有仓），不关联客户业务。")
    
    sc_result = get_supply_chain_with_pricing(session, SKUType.EQUIPMENT)
    chain_options = {f"{sc['supplier_name']} (协议ID:{sc['id']})": sc['id'] for sc in sc_result}
    
    if not chain_options:
        st.warning("当前没有可用的设备供应链协议，请建立后再试。")
        return

    chain_label = st.selectbox("选择采购来源 (供应链)", list(chain_options.keys()), key="stock_proc_sc")
    sc = get_supply_chain_by_id(chain_options[chain_label])
    
    pricing_config = sc['pricing_dict']
    sku_name_map = sc.get('sku_name_map', {})  # {sku_id: sku_name}
    payment = sc['payment_terms'] or {}
    # sku_list 用于 UI 显示（SKU 名称）
    sku_list = list(sku_name_map.values())

    # 反转映射：sku_name -> sku_id
    sku_name_to_id = {v: k for k, v in sku_name_map.items()}
    
    # 准备可用点位列表（统一按 Point 体系管理）
    # 发货点 = 供应商仓库；收货点 = 我们仓库 + 供应商仓库
    shipping_pts = get_valid_shipping_points_for_mat_procurement(session, sc['id'])
    receiving_pts = get_valid_receiving_points_for_mat_procurement(session, sc['id'])

    point_options = []   # 收货点选项（入库点位列）
    point_map = {}       # 显示名称 -> Point ID 映射
    # 保存发货点位：供应商点位中 ID 最小的（用于统一发货）
    _shipping_pt = min(shipping_pts, key=lambda p: p['id']) if shipping_pts else None
    _shipping_pt_name = _shipping_pt['name'] if _shipping_pt else SystemConstants.DEFAULT_POINT

    # 收货点选项
    for p in receiving_pts:
        display_name = f"{p['name']} ({p['type']})"
        point_options.append(display_name)
        point_map[display_name] = p['id']

    if not point_options:
        point_options = [SystemConstants.DEFAULT_POINT]
        point_map[SystemConstants.DEFAULT_POINT] = None

    if "stock_proc_df" not in st.session_state or st.session_state.get("stock_proc_sc_id") != sc['id']:
        initial_sku = sku_list[0] if sku_list else ""
        initial_price = 0.0
        # initial_sku 是 SKU 名称，需要转换为 sku_id 才能查询 pricing_config
        initial_sku_id = sku_name_to_id.get(initial_sku)
        if initial_sku_id and initial_sku_id in pricing_config:
            p_val = pricing_config[initial_sku_id]
            # get_pricing_dict() 返回 {sku_id: {"price": x}} 格式；旧格式直接是价格值
            if isinstance(p_val, dict):
                initial_price = float(p_val.get("price") or 0)
            else:
                initial_price = float(p_val) if p_val != "浮动" else 0.0

        st.session_state["stock_proc_df"] = pd.DataFrame([
            {"设备/配件": initial_sku, "数量": 0, "单价": initial_price, "入库位置": point_options[0]}
        ])
        st.session_state["stock_proc_sc_id"] = sc['id']

    version_key = "stock_proc_ver"
    if version_key not in st.session_state: st.session_state[version_key] = 0
    editor_key = f"stock_proc_editor_{st.session_state[version_key]}"
    
    if editor_key in st.session_state:
        state = st.session_state[editor_key]
        if state.get("edited_rows") or state.get("added_rows") or state.get("deleted_rows"):
            df = st.session_state["stock_proc_df"].copy()
            if state.get("deleted_rows"):
                df = df.drop(index=state["deleted_rows"]).reset_index(drop=True)
            for idx_str, change in state.get("edited_rows", {}).items():
                idx = int(idx_str)
                if idx < len(df):
                    for col, val in change.items():
                        df.at[idx, col] = val
                        if col == "设备/配件":
                            u_price, _, _ = get_sku_agreement_price(session, sc['id'], None, val)
                            df.at[idx, "单价"] = u_price
            for row_data in state.get("added_rows", []):
                if "设备/配件" in row_data:
                    u_price, _, _ = get_sku_agreement_price(session, sc['id'], None, row_data["设备/配件"])
                    row_data["单价"] = u_price
                if "数量" not in row_data: row_data["数量"] = 0
                if "入库位置" not in row_data: row_data["入库位置"] = point_options[0]
                df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)
            st.session_state["stock_proc_df"] = df
            st.session_state[version_key] += 1
            st.rerun()

    st.markdown(f"""
    <div style='background-color: rgba(46, 204, 113, 0.1); padding: 10px; border-radius: 5px; border-left: 4px solid #2ECC71; margin-bottom: 1rem;'>
        <b>结算协议摘要：</b> 预付 {int(payment.get('prepayment_ratio',0)*100)}% |
        尾款账期 {payment.get('balance_period',0)} {payment.get('day_rule', SettlementRule.NATURAL_DAY)}
    </div>
    """, unsafe_allow_html=True)

    edited_df = st.data_editor(
        st.session_state["stock_proc_df"].reset_index(drop=True),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "设备/配件": st.column_config.SelectboxColumn("协议内品类", options=sku_list),
            "数量": st.column_config.NumberColumn("采购数量", min_value=0, step=1),
            "单价": st.column_config.NumberColumn("单价 (元)", format="%.2f"),
            "入库位置": st.column_config.SelectboxColumn("入库点位", options=point_options)
        },
        hide_index=True,
        key=editor_key
    )
    st.session_state["stock_proc_df"] = edited_df.reset_index(drop=True)

    st.divider()
    btn_col1, btn_col2 = st.columns([2, 1])
    if btn_col1.button("锁定库存采购单", type="primary", use_container_width=True, key="btn_lock_stock_proc"):
        valid_items = []
        total_amt = 0.0
        for idx, row in edited_df.iterrows():
            p_name = row["设备/配件"]
            qty = row["数量"]
            if not p_name and (not qty or qty <= 0): continue
            if not p_name or not qty or qty <= 0:
                st.error(f"提交失败：第 {idx+1} 行信息不完整。")
                return
            
            item_price = float(row["单价"])
            w_name = row.get("入库位置")
            w_point_id = point_map.get(w_name)  # 从映射表获取 Point ID
            # 发货点位：取供应商点位中 ID 最小的
            shipping_pt = min(shipping_pts, key=lambda p: p['id']) if shipping_pts else None
            shipping_pt_name = shipping_pt['name'] if shipping_pt else SystemConstants.DEFAULT_POINT
            valid_items.append({
                "sku_id": sku_id_map.get(row["设备/配件"]),
                "sku_name": row["设备/配件"],
                "qty": row["数量"],
                "price": item_price,
                "deposit": 0.0,  # 库存采购无押金
                "point_id": w_point_id,
                "point_name": w_name,
                "shipping_point_name": shipping_pt_name
            })
            total_amt += row["数量"] * item_price
        
        if valid_items:
            st.session_state["temp_stock_proc_data"] = {
                "items": valid_items, "total_amt": total_amt, "payment": payment
            }
            st.session_state["show_stock_proc_confirm"] = True
            st.rerun()
        else:
            st.error("请输入至少一项有效的设备及数量")

    if btn_col2.button("清空并返回", use_container_width=True, key="btn_clear_stock_proc"):
        del st.session_state["stock_proc_df"]
        st.rerun()

@st.dialog("🎯 库存采购单确认")
def confirm_stock_procurement_dialog(session, sc_id: int):
    data = st.session_state.get("temp_stock_proc_data")
    if not data:
        st.error("数据丢失")
        if st.button("关闭"): st.rerun()
        return

    sc = get_supply_chain_by_id(sc_id)
    if not sc:
        st.error("无法加载供应链详情")
        if st.button("关闭"): st.rerun()
        return
    payment = data['payment']
    prepay_amt = data['total_amt'] * payment.get('prepayment_ratio', 0)

    st.markdown(f"**供应商:** {sc['supplier_name']}")
    st.markdown(f"**采购总金额:** ¥ {data['total_amt']:,.2f}  |  **需付预付款:** ¥ {prepay_amt:,.2f}")
    
    st.write("---")
    st.write("📦 **入库明细:**")
    df_show = pd.DataFrame(data['items'])[['sku_name', 'qty', 'price', 'point_name']]
    df_show.columns = ['设备型号', '数量', '单价(元)', '入库点位']
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    desc = st.text_input("采购说明 (附言)", placeholder="选填，如：Q3季度备库存")
    
    st.write("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("✅ 确认生成采购单", type="primary", use_container_width=True):
        st.session_state["temp_stock_proc_desc"] = desc
        _save_stock_procurement_vc(session, sc_id)
    if c2.button("取消", use_container_width=True):
        del st.session_state["show_stock_proc_confirm"]
        st.rerun()

def _save_stock_procurement_vc(session, sc_id: int):
    data = st.session_state["temp_stock_proc_data"]
    desc = st.session_state.get("temp_stock_proc_desc", "")
    elems_payload = []
    for i in data["items"]:
        norm = normalize_item_data(i)
        qty = float(norm.get('qty') or 0)
        price = float(norm.get('price') or 0)
        deposit = float(norm.get('deposit') or 0)
        elem = VCElementSchema(
            shipping_point_id=int(norm.get('shipping_point_id') or 0),
            receiving_point_id=int(norm.get('receiving_point_id') or norm.get('point_id') or 0),
            sku_id=int(norm.get('sku_id') or 0),
            qty=qty,
            price=price,
            deposit=deposit,
            subtotal=qty * price,
            sn_list=[norm.get('sn')] if norm.get('sn') and norm.get('sn') != '-' else []
        )
        elems_payload.append(elem)

    payload = CreateStockProcurementVCSchema(
        sc_id=sc_id,
        elements=elems_payload,
        total_amt=data["total_amt"],
        payment=data["payment"],
        description=desc
    )
    
    # 获取草稿时间规则(可以复用逻辑，但目前简化为不带额外继承)
    draft_rules = []
    
    with st.spinner("系统处理中..."):
        res = create_stock_procurement_vc_action(session, payload, draft_rules)
    
    if res.success:
        st.success(res.message)
        del st.session_state["show_stock_proc_confirm"]
        if "temp_stock_proc_data" in st.session_state: del st.session_state["temp_stock_proc_data"]
        if "stock_proc_df" in st.session_state: del st.session_state["stock_proc_df"]
        st.session_state.last_page = "运行看板"
        st.rerun()
    else:
        st.error(f"操作失败: {res.error}")

# =====================================================
# 新增：库存拨付管理 (分配库存到客户)
# =====================================================

def show_inventory_allocation_form(session, active_businesses):
    st.markdown("### <i class='bi bi-box-arrow-right'></i> 库存拨付 (支持多点位分配)", unsafe_allow_html=True)
    st.caption("将自有仓设备拨付给客户业务。支持将不同设备分配到该业务下的不同点位。")
    
    if not active_businesses:
        st.warning("当前没有可用于拨付的客户业务。")
        return
        
    biz_options = {f"{b['customer_name']} (业务ID: {b['id']})": b['id'] for b in active_businesses if b.get('customer_name')}
    sel_biz_label = st.selectbox("1. 选择目标业务", list(biz_options.keys()))
    biz_id = biz_options[sel_biz_label]
    biz = get_business_detail(biz_id)

    # 获取目标业务下的所有点位（收货点 = 客户所有点位，不限类型）
    points = get_valid_receiving_points_for_allocation(session, biz_id)
    if not points:
        st.warning("该客户没有配置点位，无法拨付设备。")
        return
    point_names = sorted([f"{p['name']} ({p['type']})" for p in points])
    point_id_map = {f"{p['name']} ({p['type']})": p['id'] for p in points}

    # 获取库存设备
    available_equipments = get_equipment_inventory_list(status=OperationalStatus.STOCK)
    
    if not available_equipments:
        st.info("当前自有仓中无可用的库存设备。")
        return
        
    st.write("**2. 选择并分配设备点位**")
    eq_data = []
    for eq in available_equipments:
        wh_name = eq['所在点位']
        eq_data.append({
            "选中": False,
            "ID": eq['设备ID'],
            "品类": eq['品类名称'],
            "SN序列号": eq['SN序列号'],
            "当前位置": wh_name,
            "目标点位": point_names[0] if point_names else None
        })
    df_eq = pd.DataFrame(eq_data)
    
    edited_eq_df = st.data_editor(
        df_eq,
        use_container_width=True,
        hide_index=True,
        column_config={
            "选中": st.column_config.CheckboxColumn("勾选拨付", default=False),
            "ID": st.column_config.NumberColumn("设备ID", disabled=True),
            "品类": st.column_config.TextColumn(disabled=True),
            "SN序列号": st.column_config.TextColumn(disabled=True),
            "当前位置": st.column_config.TextColumn("所在仓库", disabled=True),
            "目标点位": st.column_config.SelectboxColumn("分配到客户点位", options=point_names, required=True)
        },
        key=f"alloc_eq_ed_{biz_id}"
    )
    
    selected_rows = edited_eq_df[edited_eq_df["选中"] == True]
    
    st.divider()
    if st.button("确认拨付选中设备", type="primary", use_container_width=True, disabled=len(selected_rows)==0):
        # 构建设备到点位的映射
        alloc_map = {}
        for _, row in selected_rows.iterrows():
            alloc_map[int(row["ID"])] = point_id_map[row["目标点位"]]
            
        st.session_state[f"temp_alloc_data_{biz_id}"] = {
            "allocation_map": alloc_map,
            "display_data": selected_rows[["品类", "SN序列号", "当前位置", "目标点位"]].to_dict('records')
        }
        st.session_state[f"show_alloc_confirm_{biz_id}"] = True
        st.rerun()

@st.dialog("🔄 库存拨付确认")
def confirm_allocation_dialog(session, biz_id: int):
    data = st.session_state.get(f"temp_alloc_data_{biz_id}")
    if not data:
        st.error("数据丢失")
        if st.button("关闭"): st.rerun()
        return

    biz = get_business_detail(biz_id)
    st.markdown(f"**目标客户:** {biz['customer_name']}")
    st.markdown(f"**拨付总量:** {len(data['allocation_map'])} 台")
    
    st.write("---")
    st.write("📦 **分配清单预览:**")
    st.table(pd.DataFrame(data["display_data"]))

    desc = st.text_input("拨付说明 (可选)", placeholder="例如：首批设备调拨", key=f"alloc_desc_input_{biz_id}")
    
    st.write("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("🚀 确定拨付并更新库存", type="primary", use_container_width=True):
        st.session_state[f"temp_alloc_desc_{biz_id}"] = desc
        _save_inventory_allocation(session, biz_id)
    if c2.button("取消", use_container_width=True):
        del st.session_state[f"show_alloc_confirm_{biz_id}"]
        st.rerun()

def _save_inventory_allocation(session, biz_id: int):
    data = st.session_state[f"temp_alloc_data_{biz_id}"]
    desc = st.session_state.get(f"temp_alloc_desc_{biz_id}", "")
    allocation_map = data["allocation_map"]

    # 按目标点位分组，构建 elements
    pt_groups = {}
    for eq_id, tgt_pt_id in allocation_map.items():
        if tgt_pt_id not in pt_groups:
            pt_groups[tgt_pt_id] = []
        pt_groups[tgt_pt_id].append(str(eq_id))

    elems_payload = []
    from models import EquipmentInventory
    for tgt_pt_id, eq_ids in pt_groups.items():
        # 获取第一条记录的设备信息用于获取 sku_id 和 deposit
        first_eq = session.query(EquipmentInventory).get(int(eq_ids[0]))
        sku_id = first_eq.sku_id if first_eq else 0
        deposit = 0.0
        elem = VCElementSchema(
            shipping_point_id=int(first_eq.point_id) if first_eq else 0,
            receiving_point_id=int(tgt_pt_id),
            sku_id=int(sku_id),
            qty=len(eq_ids),
            price=0.0,
            deposit=deposit,
            subtotal=0.0,
            sn_list=eq_ids
        )
        elems_payload.append(elem)

    payload = AllocateInventorySchema(
        business_id=biz_id,
        elements=elems_payload,
        description=desc
    )
    
    with st.spinner("正在处理资产状态切换..."):
        res = create_inventory_allocation_action(session, payload)
    
    if res.success:
        st.success(res.message)
        # 清除临时数据
        keys_to_del = [f"show_alloc_confirm_{biz_id}", f"temp_alloc_data_{biz_id}", f"temp_alloc_desc_{biz_id}"]
        for k in keys_to_del:
            if k in st.session_state: del st.session_state[k]
        st.session_state.last_page = "运行看板"
        st.rerun()
    else:
        st.error(f"拨付拦截: {res.error}")

