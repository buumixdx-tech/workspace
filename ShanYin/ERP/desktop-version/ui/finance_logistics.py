import streamlit as st

from models import get_session, SKU
from logic.state_machine import logistics_state_machine, virtual_contract_state_machine
from logic.finance import finance_module
from logic.inventory import inventory_module
import logic.business
from logic.offset_manager import check_and_split_excess
import pandas as pd
import streamlit_antd_components as sac
from logic.constants import (
    VCType, VCStatus, SubjectStatus, CashStatus, ReturnDirection, CashFlowType, LogisticsStatus,
    AccountOwnerType, SystemConstants, TimeRuleRelatedType, BankInfoKey, BusinessStatus
)
from ui.rule_components import show_rule_manager_tab
from logic.services import get_suggested_cashflow_parties, normalize_item_data, format_item_list_preview, calculate_cashflow_progress
from logic.time_rules import RuleManager
from logic.logistics import (
    create_logistics_plan_action, confirm_inbound_action,
    update_express_order_action, update_express_order_status_action,
    bulk_progress_express_orders_action,
    CreateLogisticsPlanSchema, ConfirmInboundSchema,
    UpdateExpressOrderSchema, ExpressOrderStatusSchema,
    BatchItemSchema,
)
from logic.file_mgmt import save_batch_certificate
from logic.finance import create_cash_flow_action, CreateCashFlowSchema
from logic.vc.queries import get_vc_by_id, get_vc_list_for_overview
from logic.logistics.queries import (
    get_logistics_by_id, get_logistics_by_vc, 
    get_express_orders_by_logistics, get_logistics_list_for_ui
)
from logic.master.queries import (
    get_customer_by_id, get_supplier_by_id, get_external_partner_by_id, 
    get_point_by_id, get_points_for_ui, get_point_by_name, get_supplier_by_name
)
from logic.supply_chain.queries import get_supply_chain_detail_for_ui
from logic.finance.queries import get_cash_flow_list_for_ui, get_bank_account_list_for_ui

@st.dialog("确认物流发货计划", width="large")
def confirm_logistics_plan_dialog(session, vc_id):
    vc_data = get_vc_by_id(vc_id)
    data = st.session_state.get(f"temp_log_plan_{vc_id}")
    if not data:
        st.error("数据丢失")
        if st.button("返回"):
            st.session_state[f"show_log_plan_confirm_{vc_id}"] = False
            st.rerun()
        return

    st.write(f"请核对 **{vc_data['description']}** 的物流发货计划。")
    
    st.markdown("#### <i class='bi bi-truck'></i> 待生成的快递单明细", unsafe_allow_html=True)
    display_data = []
    for row in data['edited_data']:
        # 构建货品预览
        items_list = row.get("raw_items") or []
        items_preview = "; ".join([f"{it.get('sku_name', it.get('name', '?'))} x{it.get('qty', 0)}" for it in items_list]) or "无明细"
        display_data.append({
            "快递单号": row.get("快递单号", "-"),
            "发货点位": row.get("发货点位名称", "-"),
            "发货地址": row.get("发货地址", "-"),
            "收货点位": row.get("收货点位名称", "-"),
            "收货地址": row.get("收货地址", "-"),
            "货品明细": items_preview
        })
    st.table(pd.DataFrame(display_data))

    st.divider()
    c_sub1, c_sub2 = st.columns(2)
    with c_sub1:
        if st.button("确认生成发货单", type="primary", use_container_width=True):
            orders_payload = []
            for row in data['edited_data']:
                ad_info = {
                    "收货点位Id": row.get("收货点位Id"),
                    "收货点位名称": row.get("收货点位名称"),
                    "收货地址": row.get("收货地址"),
                    "收货联系电话": row.get("收货联系电话") or None,
                    "发货点位Id": row.get("发货点位Id"),
                    "发货点位名称": row.get("发货点位名称") or "",
                    "发货地址": row.get("发货地址") or "",
                    "发货联系电话": row.get("发货联系电话") or None
                }

                orders_payload.append({
                    "tracking_number": row["快递单号"],
                    "items": row["raw_items"],
                    "address_info": ad_info
                })

            payload = CreateLogisticsPlanSchema(vc_id=vc_id, orders=orders_payload)
            result = create_logistics_plan_action(session, payload)
            
            if result.success:
                st.session_state[f"show_log_plan_confirm_{vc_id}"] = False
                if f"edit_eo_{vc_id}" in st.session_state: del st.session_state[f"edit_eo_{vc_id}"]
                if f"temp_log_plan_{vc_id}" in st.session_state: del st.session_state[f"temp_log_plan_{vc_id}"]
                st.success("物流计划已正式下达")
                st.rerun()
            else:
                st.error(f"操作失败: {result.error}")

    with c_sub2:
        if st.button("返回修改", use_container_width=True):
            st.session_state[f"show_log_plan_confirm_{vc_id}"] = False
            st.rerun()

@st.dialog("核心凭证确认：资产/标的物入库同步", width="large")
def confirm_inbound_dialog(session, log_id, sn_list):
    log = get_logistics_by_id(log_id)
    vc = get_vc_by_id(log['virtual_contract_id']) if log else None
    if not vc:
        st.error("合同数据丢失")
        return

    st.write("即将完成物流终结操作。系统将同步更新库存位置、资产状态并生成财务应付/应收凭证。")

    # 汇总所有快递单的物品
    orders = get_express_orders_by_logistics(log_id)
    all_items = []
    for o in orders:
        norm_items = [normalize_item_data(i) for i in (o.get('items') or [])]
        addr_info = o.get('address_info') or {}
        for ni in norm_items:
            all_items.append({
                "快递单号": o['tracking_number'],
                "点位/仓库": addr_info.get("收货点位名称") or addr_info.get("发货点位名称") or SystemConstants.UNKNOWN,
                "货品名称": ni["sku_name"],
                "数量": ni["qty"]
            })

    st.markdown("#### <i class='bi bi-list-check'></i> 待确认收货明细汇总", unsafe_allow_html=True)
    if all_items:
        st.table(pd.DataFrame(all_items))
    else:
        st.warning("未检测到具体货品明细，建议检查快递单配置。")

    # ============ 设备/库存采购：SN 录入 ============
    if vc['type'] in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT]:
        st.markdown("#### <i class='bi bi-upc-scan'></i> 资产SN码核对", unsafe_allow_html=True)
        if sn_list:
            st.code("\n".join(sn_list))
        else:
            st.error("设备采购必须录入SN码")

    # ============ 物料采购：批次信息录入 ============
    elif vc['type'] == VCType.MATERIAL_PROCUREMENT:
        st.markdown("#### <i class='bi bi-box-seam'></i> 物料批次分配", unsafe_allow_html=True)

        from logic.vc.queries import get_valid_receiving_points_for_mat_procurement
        receiving_pts = get_valid_receiving_points_for_mat_procurement(session, vc['supply_chain_id'])
        pt_options_map = {p['id']: p['name'] for p in receiving_pts}

        # 获取 SKU 信息
        sku_ids = set()
        for o in orders:
            for item in (o.get('items') or []):
                sku_ids.add(item.get('sku_id'))
        sku_map = {}
        sku_model_map = {}
        if sku_ids:
            skus = session.query(SKU).filter(SKU.id.in_(sku_ids)).all()
            sku_map = {s.id: s.name for s in skus}
            sku_model_map = {s.id: s.model for s in skus}

        # 构建 (SKU × 收货点) 聚合数据（仅用于 Step 2 显示总量）
        sku_recv_groups = {}  # key = f"{sku_id}-{recv_pt_id}"
        for o in orders:
            addr_info = o.get('address_info') or {}
            recv_pt_id = addr_info.get('收货点位Id')
            recv_pt_name = addr_info.get('收货点位名称') or ''
            for item in (o.get('items') or []):
                sid = item.get('sku_id')
                qty = float(item.get('qty', 0))
                if sid and qty > 0:
                    gk = f"{sid}-{recv_pt_id}"
                    if gk not in sku_recv_groups:
                        sku_recv_groups[gk] = {
                            'sku_id': sid, 'sku_name': sku_map.get(sid, f'SKU-{sid}'),
                            'recv_pt_id': recv_pt_id, 'recv_pt_name': recv_pt_name,
                            'total_qty': 0.0
                        }
                    sku_recv_groups[gk]['total_qty'] += qty

        # session_state 结构：
        # batch_definitions: { sku_id: [ {'pd': str, 'cert': UploadedFile} ] }  -- Step1 定义批次
        # batch_allocations: { group_key: { total_qty, per_batch_qty: { pd: qty } } }  -- Step2 分配数量
        def_key = f"batch_def_{log_id}"
        alloc_key = f"batch_alloc_{log_id}"

        if def_key not in st.session_state:
            # 初始化：每个 SKU 一个默认批次行
            st.session_state[def_key] = {sid: [{'pd': '', 'cert': None}] for sid in sku_ids}
        if alloc_key not in st.session_state:
            st.session_state[alloc_key] = {}

        step_key = f"batch_step_{log_id}"
        if step_key not in st.session_state:
            st.session_state[step_key] = 1

        # ── Step 1：定义各 SKU 的批次（生产日期 + 质检报告）────────────────────
        if st.session_state[step_key] == 1:
            st.info("**步骤 1/2**：为每个入库 SKU 定义所有批次并上传质检报告")

            for sid in sorted(sku_ids):
                sku_name = sku_map.get(sid, f'SKU-{sid}')
                with st.expander(f"📦 {sku_name}", expanded=True):
                    batches = st.session_state[def_key].get(sid, [])
                    to_del = None
                    for bi, batch in enumerate(batches):
                        bc = st.columns([3, 1])
                        with bc[0]:
                            new_pd = st.text_input(
                                f"生产日期（{sku_name} 第{bi+1}批）",
                                value=batch['pd'],
                                placeholder="YYYYMMDD",
                                label_visibility="collapsed",
                                key=f"def_pd_{log_id}_{sid}_{bi}"
                            )
                        with bc[1]:
                            st.write("")
                            if len(batches) > 1 and st.button("删除", key=f"def_del_{log_id}_{sid}_{bi}", use_container_width=True):
                                to_del = bi
                        new_cert = st.file_uploader(
                            f"质检报告（{sku_name} 第{bi+1}批）",
                            accept_multiple_files=False,
                            label_visibility="collapsed",
                            key=f"def_cert_{log_id}_{sid}_{bi}"
                        )
                        # 暂存
                        st.session_state[def_key][sid][bi]['pd'] = new_pd
                        st.session_state[def_key][sid][bi]['cert'] = new_cert
                    if to_del is not None:
                        st.session_state[def_key][sid].pop(to_del)
                        st.rerun()
                    if st.button(f"+ 添加 {sku_name} 批次", key=f"def_add_{log_id}_{sid}", use_container_width=True):
                        st.session_state[def_key][sid].append({'pd': '', 'cert': None})
                        st.rerun()

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                if st.button("下一步：分配批次数量 →", type="primary", use_container_width=True):
                    # 验证 Step1：每个 SKU 至少有一个生产日期
                    missing = [sku_map.get(sid, f'SKU-{sid}') for sid in sku_ids
                               if not any(b['pd'] for b in st.session_state[def_key].get(sid, []))]
                    if missing:
                        st.error(f"以下 SKU 尚未填写任何生产日期：{', '.join(missing)}")
                        st.rerun()
                    st.session_state[step_key] = 2
                    st.rerun()
            with c2:
                if st.button("返回修改", use_container_width=True):
                    st.session_state[f"show_inbound_confirm_{log_id}"] = False
                    st.rerun()

        # ── Step 2：按收货点分配批次数量 ───────────────────────────────────────
        else:
            st.info("**步骤 2/2**：为每个 SKU×收货点 分配各批次的数量（总和须等于收货总量）")

            # 显示验证错误（rerun后出现在 dialog 顶部）
            err_key = f"batch_alloc_errors_{log_id}"
            if st.session_state.get(err_key):
                for err in st.session_state[err_key]:
                    st.error(f"❌ {err}")
                st.session_state[err_key] = []
                col_b = st.columns([1, 1, 2])[1]
                if col_b.button("← 退回上一步", use_container_width=True):
                    st.session_state[step_key] = 1
                    st.rerun()
                return

            # 确保 allocation 初始状态完整（每次进入 Step2 重建，保证与 SKU 定义一致）
            all_pds_by_sku = {}  # sku_id -> [pd1, pd2, ...] 稳定顺序
            for sid in sorted(sku_ids):
                batches = st.session_state[def_key].get(sid, [])
                all_pds_by_sku[sid] = [b['pd'] for b in batches if b['pd']]

            # 初始化 / 重建 allocation
            for gk, grp in sku_recv_groups.items():
                sid = grp['sku_id']
                pds = all_pds_by_sku.get(sid, [])
                if gk not in st.session_state[alloc_key]:
                    st.session_state[alloc_key][gk] = {
                        'total_qty': grp['total_qty'],
                        'per_batch_qty': {pd: 0.0 for pd in pds}
                    }
                else:
                    # sku 批次定义变了（用户回退 Step1 修改了），重建
                    existing = st.session_state[alloc_key][gk]['per_batch_qty']
                    new_alloc = {pd: existing.get(pd, 0.0) for pd in pds}
                    st.session_state[alloc_key][gk] = {
                        'total_qty': grp['total_qty'],
                        'per_batch_qty': new_alloc
                    }

            for gk, grp in sku_recv_groups.items():
                sid = grp['sku_id']
                sku_name = grp['sku_name']
                total = grp['total_qty']
                pds = all_pds_by_sku.get(sid, [])
                alloc = st.session_state[alloc_key][gk]['per_batch_qty']

                gk_cols = st.columns([1, 3, 1])
                with gk_cols[0]:
                    st.write(f"**{sku_name}**")
                with gk_cols[1]:
                    st.caption(f"→ {grp['recv_pt_name']}  |  收货总量: {int(total)}")
                used_placeholder = gk_cols[2].empty()

                # 每个批次一行：显示完整批次号 + 数量输入框
                for pd_val in pds:
                    pd_short = pd_val.replace("-", "")
                    model = sku_model_map.get(sid, f"SKU{sid}")
                    batch_no_label = f"{pd_short}-{model}"
                    batch_qty = st.number_input(
                        batch_no_label,
                        min_value=0.0,
                        max_value=float(total),
                        value=float(alloc.get(pd_val, 0)),
                        step=1.0,
                        format="%.0f",
                        label_visibility="visible",
                        key=f"alloc_{log_id}_{gk}_{pd_val}"
                    )
                    st.session_state[alloc_key][gk]['per_batch_qty'][pd_val] = batch_qty

                # compute AFTER number_input loop so session_state is current
                used = sum(st.session_state[alloc_key][gk]['per_batch_qty'].values())
                if abs(used - total) < 0.001:
                    color = "blue"
                elif used > total:
                    color = "red"
                else:
                    color = "green"
                used_placeholder.markdown(f"已分配: <b style='color:{color}'>{int(used)}</b> / {int(total)}", unsafe_allow_html=True)

                st.divider()

            # 提交
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                if st.button("准予结单并同步系统", type="primary", use_container_width=True):
                    # 验证：每个组的数量之和
                    errors = []
                    formal_batch_items = []
                    for gk, grp in sku_recv_groups.items():
                        sid = grp['sku_id']
                        total = grp['total_qty']
                        alloc = st.session_state[alloc_key][gk]['per_batch_qty']
                        used = sum(alloc.values())
                        if abs(used - total) > 0.001:
                            errors.append(f"{grp['sku_name']}（{grp['recv_pt_name']}）：已分配 {int(used)}，不等于收货总量 {int(total)}")

                    if errors:
                        st.session_state[err_key] = errors
                        st.rerun()

                    # 构建 batch_items
                    for gk, grp in sku_recv_groups.items():
                        sid = grp['sku_id']
                        recv_pt_id = grp['recv_pt_id']
                        alloc = st.session_state[alloc_key][gk]['per_batch_qty']
                        batches = st.session_state[def_key].get(sid, [])

                        for bi_idx, batch in enumerate(batches):
                            pd_val = batch['pd']
                            qty = alloc.get(pd_val, 0.0)
                            if qty <= 0:
                                continue
                            cert_path = None
                            cert_file = batch.get('cert')
                            if cert_file:
                                prod_date_str = pd_val.replace("-", "")
                                model = sku_model_map.get(sid, f"SKU{sid}")
                                batch_no = f"{prod_date_str}-{model}"
                                cert_path = save_batch_certificate(batch_no, cert_file)

                            formal_batch_items.append(BatchItemSchema(
                                sku_id=sid,
                                production_date=pd_val,
                                receiving_point_id=recv_pt_id,
                                qty=qty,
                                certificate_filename=cert_path
                            ))

                    payload = ConfirmInboundSchema(
                        log_id=log_id,
                        sn_list=sn_list or [],
                        batch_items=formal_batch_items
                    )
                    result = confirm_inbound_action(session, payload)

                    if result.success:
                        st.session_state[f"show_inbound_confirm_{log_id}"] = False
                        st.session_state[f"temp_sn_list_{log_id}"] = []
                        st.session_state.pop(def_key, None)
                        st.session_state.pop(alloc_key, None)
                        st.session_state.pop(step_key, None)
                        st.success("系统状态与账务已成功同步！")
                        st.rerun()
                    else:
                        st.error(f"操作失败: {result.error}")
            with c2:
                if st.button("← 上一步", use_container_width=True):
                    st.session_state[step_key] = 1
                    st.rerun()


@st.dialog("财务审签确认：资金流水录入", width="large")
def confirm_cash_flow_dialog(session, cf_data):
    st.write("请从财务审核角度最后核对以下流水信息。确认后将立即触发账务引擎并更新合同状态。")
    
    vc = get_vc_by_id(cf_data['vc_id'])
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**流水基本信息**")
        st.write(f"- 关联合同: {vc['description'] if vc else 'N/A'}")
        st.write(f"- 资金类型: **{cf_data['type']}**")
        st.metric("操作金额", f"¥{cf_data['amount']:,.2f}")
    
    with col2:
        st.write("**收付款账户**")
        st.write(f"- 付款账户: {cf_data['payer_label']}")
        st.write(f"- 收款账户: {cf_data['payee_label']}")
        st.write(f"- 交易日期: {cf_data['date'][:16]}")

    if cf_data['description']:
        st.info(f"**备注说明**: {cf_data['description']}")

    st.divider()
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("确认执行并记账", type="primary", use_container_width=True):
            payload = CreateCashFlowSchema(
                vc_id=cf_data['vc_id'],
                type=cf_data['type'],
                amount=cf_data['amount'],
                payer_id=cf_data['payer_id'],
                payee_id=cf_data['payee_id'],
                transaction_date=pd.to_datetime(cf_data['date']),
                description=cf_data['description']
            )
            result = create_cash_flow_action(session, payload)
            
            if result.success:
                st.session_state["show_cf_confirm"] = False
                if "temp_cf_data" in st.session_state: del st.session_state["temp_cf_data"]
                st.success("资金流水处理成功！")
                st.rerun()
            else:
                st.error(f"处理失败: {result.error}")

def _get_account_identity_html(session, acc):
    """辅助函数：解析账户所属主体的富文本标识"""
    if not acc:
        return "<span style='color: #95a5a6; font-size: 12px;'>[外部/现金]</span>"
    
    owner_name = "未知主体"
    role_label = "未知"
    role_color = "#95a5a6"
    
    if acc['owner_type'] == AccountOwnerType.CUSTOMER:
        obj = get_customer_by_id(acc['owner_id'])
        owner_name = obj['name'] if obj else f"客户ID:{acc['owner_id']}"
        role_label = "客户"
        role_color = "#3498DB" # Blue
    elif acc['owner_type'] == AccountOwnerType.SUPPLIER:
        obj = get_supplier_by_id(acc['owner_id'])
        owner_name = obj['name'] if obj else f"供应商ID:{acc['owner_id']}"
        role_label = "供应商"
        role_color = "#E67E22" # Orange
    elif acc['owner_type'] == AccountOwnerType.OURSELVES:
        owner_name = "闪饮业务中心 (我方)"
        role_label = "我方"
        role_color = "#2ECC71" # Green
    elif acc['owner_type'] == AccountOwnerType.PARTNER:
        obj = get_external_partner_by_id(acc['owner_id'])
        owner_name = obj['name'] if obj else f"合作伙伴ID:{acc['owner_id']}"
        role_label = "伙伴"
        role_color = "#9B59B6" # Purple

    bank_info = acc.get('account_info') or {}
    bank_name = bank_info.get(BankInfoKey.BANK_NAME, '未知银行')
    acc_no_raw = str(bank_info.get(BankInfoKey.ACCOUNT_NO) or '****')
    short_no = f"*{acc_no_raw[-4:]}" if len(acc_no_raw) >= 4 else acc_no_raw
    
    return f"""
    <div style='display: inline-block; border: 1px solid #dfe6e9; padding: 4px 10px; border-radius: 6px; background: #ffffff; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>
        <span style='background-color: {role_color}; color: white; padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-right: 8px; vertical-align: middle;'>{role_label}</span>
        <span style='color: #2d3436; font-size: 13px; font-weight: 600; vertical-align: middle;'>{owner_name}</span>
        <span style='color: #636e72; font-size: 12px; margin-left: 8px; vertical-align: middle; font-family: monospace;'>{bank_name} {short_no}</span>
    </div>
    """
    
    with c_btn2:
        if st.button("返回修改", use_container_width=True):
            st.session_state["show_cf_confirm"] = False
            st.rerun()

def show_logistics_page():
    st.markdown("<h1 style='font-size: 24px;'><i class='bi bi-truck'></i> 物流管理</h1>", unsafe_allow_html=True)
    with st.container():
        sel_tab = sac.tabs([
            sac.TabsItem('执行物流任务', icon='activity'),
            sac.TabsItem('物流全局概览', icon='globe'),
        ], align='center', variant='outline', key='logistics_tabs')
    
    session = get_session()
    
    # 用于紧凑和高级 UI 的自定义 CSS
    st.markdown("""
        <style>
        .express-card {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 8px;
            border-left: 4px solid #dee2e6;
            transition: all 0.2s;
        }
        .express-card:hover {
            border-left-color: #3498db;
            background-color: #f1f3f5;
        }
        .status-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            margin-right: 8px;
        }
        .status-ready { background-color: #fef9c3; color: #a16207; }
        .status-transit { background-color: #dbeafe; color: #1e40af; }
        .status-signed { background-color: #dcfce7; color: #166534; }
        
        .compact-info {
            font-size: 13px;
            color: #495057;
            margin-top: 4px;
        }
        /* Tighten streamlit columns */
        [data-testid="stVerticalBlock"] > div:has(div.express-card) {
            gap: 0rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    if sel_tab == '执行物流任务':
        st.subheader("执行物流任务")
        st.markdown("<div style='color: #999; margin-bottom: 1rem;'>显示所有物流状态未完成的虚拟合同及其明细</div>", unsafe_allow_html=True)
        
        # 查询需要物流的虚拟合同
        # 允许查看已完成的任务以供追溯
        show_completed = st.checkbox("显示已完成的任务", value=False, key="show_finished_log")
        
        vcs = get_vc_list_for_overview(
            type_list=[VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT, VCType.MATERIAL_PROCUREMENT, VCType.MATERIAL_SUPPLY, VCType.RETURN],
            status_list=None if show_completed else None, # status_list handled by SubjectStatus in original
            subject_status_list=None if show_completed else [SubjectStatus.EXE, SubjectStatus.SHIPPED, SubjectStatus.SIGNED] 
        )
        # Note: Original logic for show_completed was filtering subject_status != FINISH
        if not show_completed:
            vcs = [v for v in vcs if v['subject_status'] != SubjectStatus.FINISH]
            
        if not vcs:
            if show_completed:
                st.info("尚无任何物流相关的合同记录")
            else:
                st.info("当前没有待处理的物流任务，勾选“显示已完成的任务”可查看历史记录")
        
        for vc in vcs:
            with st.expander(f"合同: {vc['description'] or vc['type']} | 标的状态: {vc['subject_status']}"):
                st.write(f"**合同类型**: {vc['type']}")
                st.write(f"**当前状态**: 总体 {vc['status']} | 标的 {vc['subject_status']} | 资金 {vc['cash_status']}")
                
                # Fetch associated Logistics
                log = get_logistics_by_vc(vc['id'])
                
                # 如果不存在快递单，则手动初始化
                orders = get_express_orders_by_logistics(log['id'] if log else -1)
                
                if not orders:
                    st.info("尚未为此合同安排物流发货。")
                    if st.button("初始化物流方案建议", key=f"init_log_{vc['id']}", type="primary"):
                        suggested_rows = []

                        # 格式化 raw_items 为可读字符串
                        def _format_raw_items(items: list) -> str:
                            return " | ".join([f"{item.get('sku_name', '未知')}×{item.get('qty', 0)}" for item in items])

                        # 1. Advanced Material Supply format - group by destination AND source warehouse
                        if vc['type'] == VCType.MATERIAL_SUPPLY:
                            vc_elems = vc['elements'].get("items", []) if vc['elements'] else []
                            # 兼容旧结构：points[]
                            if not vc_elems:
                                vc_elems = vc['elements'].get("points", []) if vc['elements'] else []

                            if vc_elems and isinstance(vc_elems, list) and len(vc_elems) > 0 and isinstance(vc_elems[0], dict) and "items" in vc_elems[0]:
                                # 旧结构：points[].items[]
                                shipment_groups = {}
                                for p in vc_elems:
                                    p_id = p.get("point_id") or p.get("pointId")
                                    p_name = p.get("point_name") or p.get("pointName")
                                    p_addr = p.get("pointAddress")
                                    for item in p["items"]:
                                        ni = normalize_item_data(item)
                                        src_point = ni.get("shipping_point_name") or SystemConstants.DEFAULT_POINT
                                        group_key = (p_id, src_point)
                                        if group_key not in shipment_groups:
                                            shipment_groups[group_key] = {
                                                "收货点位Id": p_id,
                                                "收货点位名称": p_name,
                                                "收货地址": p_addr,
                                                "发货点位名称": src_point,
                                                "items": []
                                            }
                                        shipment_groups[group_key]["items"].append({
                                            "sku_id": ni["sku_id"],
                                            "sku_name": ni["sku_name"],
                                            "qty": int(ni["qty"])
                                        })
                                for (p_id, src_point), group in shipment_groups.items():
                                    source_points = get_points_for_ui(search_keyword=src_point.split(' ')[0], limit=1)
                                    source_point = source_points[0] if source_points else None
                                    source_point_id = source_point['id'] if source_point else None
                                    source_addr = source_point['address'] if source_point else "请填写发货地址"
                                    source_phone = source_point.get('contact_info', {}).get('phone') if source_point else None
                                    recv_point_id = group["收货点位Id"]
                                    recv_point = get_point_by_id(recv_point_id) if recv_point_id else None
                                    recv_phone = recv_point.get('contact_info', {}).get('phone') if recv_point else None
                                    suggested_rows.append({
                                        "快递单号": f"EXP{pd.Timestamp.now().strftime('%m%d%H%M')}{p_id or ''}{len(suggested_rows)}",
                                        "收货点位Id": recv_point_id,
                                        "收货点位名称": group["收货点位名称"],
                                        "收货地址": group["收货地址"],
                                        "收货联系电话": recv_phone or "",
                                        "发货点位Id": source_point_id,
                                        "发货点位名称": src_point,
                                        "发货地址": source_addr,
                                        "发货联系电话": source_phone or "",
                                        "raw_items": group["items"],
                                        "raw_items_display": _format_raw_items(group["items"])
                                    })
                            elif vc_elems:
                                # 新结构：elements[{shipping_point_id, receiving_point_id, sku_id, qty, ...}]
                                # 批量查询SKU名称
                                sku_ids = list(set(e.get("sku_id") for e in vc_elems if e.get("sku_id")))
                                sku_map = {}
                                if sku_ids:
                                    session = get_session()
                                    skus = session.query(SKU).filter(SKU.id.in_(sku_ids)).all()
                                    sku_map = {s.id: s.name for s in skus}
                                    session.close()

                                shipment_groups = {}
                                for e in vc_elems:
                                    sp_id = e.get("shipping_point_id")
                                    rp_id = e.get("receiving_point_id")
                                    sp_name = e.get("shipping_point_name", "")
                                    rp_name = e.get("receiving_point_name", "")
                                    # 从 ID 解析点位信息
                                    sp_point = get_point_by_id(sp_id) if sp_id else None
                                    rp_point = get_point_by_id(rp_id) if rp_id else None
                                    sp_name_resolved = sp_point['name'] if sp_point else (sp_name or SystemConstants.DEFAULT_POINT)
                                    rp_name_resolved = rp_point['name'] if rp_point else (rp_name or "未知")
                                    rp_addr = rp_point['address'] if rp_point else "请填写收货地址"
                                    rp_phone = rp_point.get('contact_info', {}).get('phone') if rp_point else None
                                    group_key = (sp_id, rp_id)
                                    if group_key not in shipment_groups:
                                        shipment_groups[group_key] = {
                                            "收货点位Id": rp_id,
                                            "收货点位名称": rp_name_resolved,
                                            "收货地址": rp_addr,
                                            "收货联系电话": rp_phone or "",
                                            "发货点位Id": sp_id,
                                            "发货点位名称": sp_name_resolved,
                                            "发货地址": sp_point['address'] if sp_point else "请填写发货地址",
                                            "发货联系电话": sp_point.get('contact_info', {}).get('phone') if sp_point else None,
                                            "items": []
                                        }
                                    shipment_groups[group_key]["items"].append({
                                        "sku_id": e.get("sku_id"),
                                        "sku_name": sku_map.get(e.get("sku_id")) or e.get("sku_name") or e.get("name") or f"SKU{e.get('sku_id')}",
                                        "qty": int(e.get("qty", 0))
                                    })
                                for group in shipment_groups.values():
                                    suggested_rows.append({
                                        "快递单号": f"EXP{pd.Timestamp.now().strftime('%m%d%H%M')}{group['收货点位Id'] or ''}{len(suggested_rows)}",
                                        "收货点位Id": group["收货点位Id"],
                                        "收货点位名称": group["收货点位名称"],
                                        "收货地址": group["收货地址"],
                                        "收货联系电话": group["收货联系电话"] or "",
                                        "发货点位Id": group["发货点位Id"],
                                        "发货点位名称": group["发货点位名称"],
                                        "发货地址": group["发货地址"],
                                        "发货联系电话": group["发货联系电话"] or "",
                                        "raw_items": group["items"],
                                        "raw_items_display": _format_raw_items(group["items"])
                                    })

                        # 2. Return Order format - group by destination warehouse
                        elif vc['type'] == VCType.RETURN:
                            vc_elems = vc['elements'].get("items", []) if vc['elements'] else []
                            # 兼容旧结构：return_items[]
                            if not vc_elems:
                                vc_elems = vc['elements'].get("return_items", []) if vc['elements'] else []

                            if vc_elems:
                                # 批量查询SKU名称
                                sku_ids = list(set(item.get("sku_id") for item in vc_elems if item.get("sku_id")))
                                sku_map = {}
                                if sku_ids:
                                    session = get_session()
                                    skus = session.query(SKU).filter(SKU.id.in_(sku_ids)).all()
                                    sku_map = {s.id: s.name for s in skus}
                                    session.close()

                                return_groups = {}
                                for item in vc_elems:
                                    # 新结构：shipping_point_id / receiving_point_id；旧结构：point_name / receiving_point_name
                                    src_pt = item.get("shipping_point_name") or item.get("point_name") or SystemConstants.UNKNOWN
                                    tgt_pt = item.get("receiving_point_name") or SystemConstants.DEFAULT_POINT
                                    src_pt_id = item.get("shipping_point_id")
                                    tgt_pt_id = item.get("receiving_point_id")
                                    # 如果有 ID，尝试解析为名称
                                    if src_pt_id and src_pt == SystemConstants.UNKNOWN:
                                        sp = get_point_by_id(src_pt_id)
                                        src_pt = sp['name'] if sp else src_pt
                                    if tgt_pt_id and tgt_pt == SystemConstants.DEFAULT_POINT:
                                        tp = get_point_by_id(tgt_pt_id)
                                        tgt_pt = tp['name'] if tp else tgt_pt
                                    group_key = (src_pt, tgt_pt)
                                    if group_key not in return_groups:
                                        return_groups[group_key] = []
                                    return_groups[group_key].append({
                                        "sku_id": item.get("sku_id"),
                                        "sku_name": sku_map.get(item.get("sku_id")) or item.get("sku_name") or item.get("name") or f"SKU{item.get('sku_id')}",
                                        "qty": item.get("qty")
                                    })

                            # 为每对 (起点, 终点) 生成一个快递单
                            for (src_pt, tgt_pt), items in return_groups.items():
                                # A. 查找始发地属性 (发货方)
                                s_points = get_points_for_ui(search_keyword=src_pt, limit=1)
                                s_obj = s_points[0] if s_points else None
                                if not s_obj and src_pt != SystemConstants.UNKNOWN:
                                    s_points = get_points_for_ui(search_keyword=src_pt.split(' ')[0], limit=1)
                                    s_obj = s_points[0] if s_points else None

                                s_id = s_obj['id'] if s_obj else None
                                s_addr = s_obj['address'] if s_obj else "请补充发货地址"
                                s_phone = s_obj.get('contact_info', {}).get('phone') if s_obj else None

                                # B. 查找目的地属性 (收货方)
                                tgt_pt_clean = tgt_pt.strip()
                                d_obj = get_point_by_name(tgt_pt_clean)
                                if not d_obj:
                                    # 尝试模糊匹配或去掉括号备注
                                    search_term = tgt_pt_clean.split('(')[0].strip()
                                    d_obj = get_point_by_name(search_term, fuzzy=True)

                                if d_obj:
                                    d_id = d_obj['id']
                                    d_name = d_obj['name']
                                    d_addr = d_obj.get('receiving_address') or d_obj['address']
                                    d_phone = d_obj.get('contact_info', {}).get('phone')
                                else:
                                    # 针对向供应商退货的情况，尝试在供应商表查找地址
                                    d_id = None
                                    supp = get_supplier_by_name(tgt_pt_clean)
                                    if not supp:
                                        search_term = tgt_pt_clean.split('(')[0].strip()
                                        supp = get_supplier_by_name(search_term, fuzzy=True)

                                    if supp:
                                        d_name = supp['name']
                                        d_addr = supp.get('contact_info', {}).get("address") or "请补充供应商收货地址"
                                    else:
                                        d_name = tgt_pt_clean
                                        d_addr = "请补充具体退货地址"
                                    d_phone = None

                                suggested_rows.append({
                                    "快递单号": f"RET{pd.Timestamp.now().strftime('%m%d%H%M')}{len(suggested_rows)}",
                                    "收货点位Id": d_id,
                                    "收货点位名称": d_name,
                                    "收货地址": d_addr,
                                    "收货联系电话": d_phone or "",
                                    "发货点位Id": s_id,
                                    "发货点位名称": src_pt,
                                    "发货地址": s_addr,
                                    "发货联系电话": s_phone or "",
                                    "raw_items": items,
                                    "raw_items_display": _format_raw_items(items)
                                })

                        # 3. 设备/库存采购 - 按收货点位分组
                        elif vc['type'] in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT]:
                            vc_elems = vc['elements'].get("items", []) if vc['elements'] else []
                            if vc_elems:
                                # 批量查询SKU名称
                                sku_ids = list(set(item.get("sku_id") for item in vc_elems if item.get("sku_id")))
                                sku_map = {}
                                if sku_ids:
                                    session = get_session()
                                    skus = session.query(SKU).filter(SKU.id.in_(sku_ids)).all()
                                    sku_map = {s.id: s.name for s in skus}
                                    session.close()

                                groups = {}
                                for item in vc_elems:
                                    pid = item.get("point_id")
                                    if pid not in groups: groups[pid] = []
                                    sku_id = item.get("sku_id")
                                    sku_name = sku_map.get(sku_id) or item.get("sku_name") or item.get("name") or f"SKU{sku_id}"
                                    groups[pid].append({
                                        "sku_id": sku_id,
                                        "sku_name": sku_name,
                                        "qty": item.get("qty")
                                    })

                                for pid, g_items in groups.items():
                                    p_obj = get_point_by_id(pid) if pid else None
                                    p_name = p_obj['name'] if p_obj else f"{SystemConstants.UNKNOWN}点位"
                                    p_addr = (p_obj.get('receiving_address') or p_obj['address']) if p_obj else "地址不详"
                                    p_phone = p_obj.get('contact_info', {}).get('phone') if p_obj else None
                                    suggested_rows.append({
                                        "快递单号": f"EXP{pd.Timestamp.now().strftime('%m%d%H%M')}{len(suggested_rows)}",
                                        "收货点位Id": pid,
                                        "收货点位名称": p_name,
                                        "收货地址": p_addr,
                                        "收货联系电话": p_phone or "",
                                        "发货点位Id": None,
                                        "发货点位名称": "",
                                        "发货地址": "",
                                        "发货联系电话": "",
                                        "raw_items": g_items,
                                        "raw_items_display": _format_raw_items(g_items)
                                    })

                        # 4. 物料采购 - 按入库点位分组
                        elif vc['type'] == VCType.MATERIAL_PROCUREMENT:
                            vc_elems = vc['elements'].get("items", []) if vc['elements'] else []
                            if vc_elems:
                                # 批量查询SKU名称
                                sku_ids = list(set(item.get("sku_id") for item in vc_elems if item.get("sku_id")))
                                sku_map = {}
                                if sku_ids:
                                    session = get_session()
                                    skus = session.query(SKU).filter(SKU.id.in_(sku_ids)).all()
                                    sku_map = {s.id: s.name for s in skus}
                                    session.close()

                                point_groups = {}
                                # 收集所有发货点ID（通常一致）
                                sp_id = None
                                for item in vc_elems:
                                    if sp_id is None:
                                        sp_id = item.get("shipping_point_id")
                                    rp_id = item.get("receiving_point_id")
                                    if rp_id:
                                        rp_point = get_point_by_id(rp_id)
                                        point_name = rp_point['name'] if rp_point else f"点位-{rp_id}"
                                    else:
                                        point_name = item.get("point_name") or item.get("pointName") or SystemConstants.DEFAULT_POINT
                                    if point_name not in point_groups:
                                        point_groups[point_name] = {"point_id": rp_id, "items": []}
                                    sku_id = item.get("sku_id")
                                    sku_name = sku_map.get(sku_id) or item.get("sku_name") or item.get("name") or f"SKU{sku_id}"
                                    point_groups[point_name]["items"].append({
                                        "sku_id": sku_id,
                                        "sku_name": sku_name,
                                        "qty": item.get("qty")
                                    })

                                # 获取发货点信息
                                sp_point = get_point_by_id(sp_id) if sp_id else None
                                sp_name = sp_point['name'] if sp_point else ""
                                sp_addr = (sp_point.get('receiving_address') or sp_point['address']) if sp_point else ""
                                sp_phone = sp_point.get('contact_info', {}).get('phone') if sp_point else ""

                                # 为每个点位生成一个快递单
                                for point_name, group_data in point_groups.items():
                                    p_id = group_data["point_id"]
                                    p_point = get_point_by_id(p_id) if p_id else None
                                    p_addr = (p_point.get('receiving_address') or p_point['address']) if p_point else "请填写收货地址"
                                    p_phone = p_point.get('contact_info', {}).get('phone') if p_point else None

                                    suggested_rows.append({
                                        "快递单号": f"EXP{pd.Timestamp.now().strftime('%m%d%H%M')}{len(suggested_rows)}",
                                        "收货点位Id": p_id,
                                        "收货点位名称": point_name,
                                        "收货地址": p_addr,
                                        "收货联系电话": p_phone or "",
                                        "发货点位Id": sp_id,
                                        "发货点位名称": sp_name,
                                        "发货地址": sp_addr,
                                        "发货联系电话": sp_phone or "",
                                        "raw_items": group_data["items"],
                                        "raw_items_display": _format_raw_items(group_data["items"])
                                    })

                        st.session_state[f"edit_eo_{vc['id']}"] = suggested_rows
                        st.rerun()

                    # 交互式编辑器
                    if f"edit_eo_{vc['id']}" in st.session_state:
                        st.markdown("##### <i class='bi bi-gear'></i> 调整并确认发货安排", unsafe_allow_html=True)
                        all_points = get_points_for_ui(limit=500)
                        point_names = [p['name'] for p in all_points]
                        point_addr_map = {p['name']: p.get('receiving_address') or p['address'] for p in all_points}

                        edited_df = st.data_editor(
                            pd.DataFrame(st.session_state[f"edit_eo_{vc['id']}"]),
                            num_rows="dynamic",
                            use_container_width=True,
                            column_config={
                                "快递单号": st.column_config.TextColumn("快递单号", help="可手动修改为真实面单号"),
                                "收货点位名称": st.column_config.SelectboxColumn("收货点位", options=point_names),
                                "收货地址": st.column_config.TextColumn("收货地址"),
                                "收货联系电话": st.column_config.TextColumn("收货电话"),
                                "发货点位名称": st.column_config.TextColumn("发货点位"),
                                "发货地址": st.column_config.TextColumn("发货地址"),
                                "发货联系电话": st.column_config.TextColumn("发货电话"),
                                "raw_items": None,
                                "raw_items_display": st.column_config.TextColumn("SKU明细", help="SKU名称和数量")
                            },
                            key=f"eo_editor_{vc['id']}"
                        )

                        # Sync address if point name changed
                        # Convert edited_df back to list of dicts for processing
                        edited_data_list = edited_df.to_dict(orient='records')
                        for row in edited_data_list:
                            if row["收货点位名称"] in point_addr_map:
                                row["收货地址"] = point_addr_map[row["收货点位名称"]]
                        
                        # Re-render data_editor with updated addresses if needed, or just use the updated list for submission
                        # For simplicity, we'll use the updated list directly for submission.
                        # If real-time update in data_editor is needed, it would require more complex state management.

                        col1, col2 = st.columns(2)
                        if col1.button("生成物流单", key=f"save_eo_{vc['id']}", type="primary"):
                            st.session_state[f"temp_log_plan_{vc['id']}"] = {
                                "edited_data": edited_data_list,
                                "point_id_map": {p['name']: p['id'] for p in all_points}
                            }
                            st.session_state[f"show_log_plan_confirm_{vc['id']}"] = True
                            st.rerun()
                        
                        if col2.button("取消初始化", key=f"cancel_eo_{vc['id']}"):
                            del st.session_state[f"edit_eo_{vc['id']}"]
                            st.rerun()
                    continue
                
                if orders:
                    statuses = set(o['status'] for o in orders)
                    is_uniform = len(statuses) == 1
                    current_status = list(statuses)[0] if is_uniform else None
                    
                    next_status_map = {LogisticsStatus.PENDING: LogisticsStatus.TRANSIT, LogisticsStatus.TRANSIT: LogisticsStatus.SIGNED}
                    target_status = next_status_map.get(current_status)
                    
                    bulk_col1, bulk_col2 = st.columns([1, 4])
                    if is_uniform and target_status:
                        label = f"批量推进至: {target_status}"
                        if bulk_col1.button(label, key=f"bulk_progress_{vc['id']}", type="primary", use_container_width=True):
                            result = bulk_progress_express_orders_action(
                                session, 
                                order_ids=[o['id'] for o in orders], 
                                target_status=target_status, 
                                logistics_id=log['id']
                            )
                            if result.success:
                                st.success(result.message)
                                st.rerun()
                            else:
                                st.error(result.error)
                    else:
                        bulk_col1.button("批量操作不可用", key=f"bulk_disabled_{vc['id']}", disabled=True, use_container_width=True)
                    st.divider()

                for o in orders:
                    # Edit mode check
                    edit_key = f"edit_eo_item_{o['id']}"
                    if st.session_state.get(edit_key):
                        with st.form(f"f_edit_eo_{o['id']}"):
                            addr_data = o.get('address_info') or {}
                            st.markdown("**<i class='bi bi-pencil-square'></i> 修改快递信息**", unsafe_allow_html=True)
                            c_f1, c_f2 = st.columns(2)
                            new_tn = c_f1.text_input("单号", value=o['tracking_number'])
                            new_pname = c_f2.text_input("点位", value=addr_data.get("收货点位名称", ""))
                            new_addr = st.text_input("详细地址", value=addr_data.get("收货地址") or addr_data.get("发货地址") or "")

                            c_col1, c_col2 = st.columns([1, 4])
                            if c_col1.form_submit_button("保存", type="primary"):
                                payload = UpdateExpressOrderSchema(
                                    order_id=o['id'],
                                    tracking_number=new_tn,
                                    address_info={"收货点位名称": new_pname, "address": new_addr}
                                )
                                result = update_express_order_action(session, payload)
                                if result.success:
                                    st.success(result.message)
                                    del st.session_state[edit_key]
                                    st.rerun()
                                else:
                                    st.error(result.error)
                            if c_col2.form_submit_button("取消"):
                                del st.session_state[edit_key]
                                st.rerun()
                    else:
                        # Premium Compact Card
                        status_class = "status-ready"
                        status_icon = "bi-circle"
                        if o['status'] == LogisticsStatus.TRANSIT:
                            status_class = "status-transit"
                            status_icon = "bi-arrow-right-circle"
                        elif o['status'] == LogisticsStatus.SIGNED:
                            status_class = "status-signed"
                            status_icon = "bi-check-circle"

                        addr_data = o.get('address_info') or {}
                        addr_str = addr_data.get("收货地址") or addr_data.get("发货地址") or addr_data.get("address") or "未知地址"
                        p_name = addr_data.get("收货点位名称") or addr_data.get("发货点位名称") or "未知点位"
                        
                        items_str = format_item_list_preview(o.get('items')) if o.get('items') else "无明细"

                        # Render card shell
                        st.markdown(f"""
                            <div class="express-card">
                                <span class="status-badge {status_class}"><i class='bi {status_icon}'></i> {o['status']}</span>
                                <code style="color: #2c3e50; font-weight: bold; font-size: 14px;">{o['tracking_number']}</code>
                                <span style="margin-left: 10px; color: #6c757d; font-size: 13px;"><i class='bi bi-geo-alt'></i> {p_name}</span>
                                <div class="compact-info">
                                    <i class='bi bi-house'></i> {addr_str}<br>
                                    <i class='bi bi-box-seam'></i> {items_str}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

                        # 直接位于下方或覆盖的动作栏（使用小按钮）
                        btn_c1, btn_c2, btn_spacer = st.columns([1, 1, 4])
                        with btn_c1:
                            if st.button("修改", key=f"btn_edit_{o['id']}", use_container_width=True):
                                st.session_state[edit_key] = True
                                st.rerun()
                        with btn_c2:
                            if o['status'] == LogisticsStatus.PENDING:
                                if st.button("发货", key=f"ship_{o['id']}", type="primary", use_container_width=True):
                                    payload = ExpressOrderStatusSchema(
                                        order_id=o['id'],
                                        target_status=LogisticsStatus.TRANSIT,
                                        logistics_id=log['id']
                                    )
                                    result = update_express_order_status_action(session, payload)
                                    if result.success: st.rerun()
                                    else: st.error(result.error)
                            elif o['status'] == LogisticsStatus.TRANSIT:
                                if st.button("签收", key=f"sign_{o['id']}", type="primary", use_container_width=True):
                                    payload = ExpressOrderStatusSchema(
                                        order_id=o['id'],
                                        target_status=LogisticsStatus.SIGNED,
                                        logistics_id=log['id']
                                    )
                                    result = update_express_order_status_action(session, payload)
                                    if result.success: st.rerun()
                                    else: st.error(result.error)
                        st.write("") # Minimal spacer
                
                # Logistics level action
                # --- 物流终结与入库操作 ---
                # 只有签收态（未入库）的物流单才显示入库按钮，已完成的不再显示
                all_signed = all(o['status'] == LogisticsStatus.SIGNED for o in orders) if orders else False
                is_ready_for_inbound = (log['status'] == LogisticsStatus.SIGNED or all_signed) and log['status'] != LogisticsStatus.FINISH
                if is_ready_for_inbound:
                    st.markdown("---")
                    
                    # 动态文案与逻辑
                    action_label = "办理入库"
                    help_text = "确认物流单已妥投，并同步更新实物库存与业务状态。"
                    
                    if vc['type'] == VCType.RETURN:
                        action_label = "确认退货/回库完成"
                        help_text = "确认退货物流已签收，系统将根据退货流向自动更新设备状态或物料库存。"
                    elif vc['type'] == VCType.MATERIAL_SUPPLY:
                        action_label = "确认客户签收/交付完成"
                        help_text = "确认客户已收到货品，将扣减相应库存并生成财务应收/营收凭证。"
                    
                    sn_list = []
                    if vc['type'] in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT]:
                        st.info("检测到新设备采购，请输入设备SN码进行资产建档")
                        sn_input = st.text_area("输入SN码 (多个请用逗号或换行分隔)", key=f"sn_input_{log['id']}")
                        if sn_input:
                            sn_list = [s.strip() for s in sn_input.replace("\n", ",").split(",") if s.strip()]
                    
                    if st.button(action_label, key=f"stockfin_{log['id']}", type="primary", help=help_text):
                        if vc['type'] in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT] and not sn_list:
                            st.error("设备采购入库必须提供至少一个有效SN码")
                        else:
                            # 进入弹窗确认
                            st.session_state[f"temp_sn_list_{log['id']}"] = sn_list
                            st.session_state[f"show_inbound_confirm_{log['id']}"] = True
                            st.rerun()

    elif sel_tab == '物流全局概览':
        st.subheader("物流任务全局概览")
        # 筛选器区域
        c1, c2, c3 = st.columns(3)
        all_log_st = [LogisticsStatus.PENDING, LogisticsStatus.TRANSIT, LogisticsStatus.SIGNED, LogisticsStatus.FINISH]
        sel_log_st = c1.multiselect("物流状态", all_log_st, default=all_log_st)
        
        all_vc_types = [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT, VCType.MATERIAL_PROCUREMENT, VCType.MATERIAL_SUPPLY, VCType.RETURN]
        sel_vc_types = c2.multiselect("合同类型", all_vc_types, default=all_vc_types)
        
        search_log = c3.text_input("搜索关键词", placeholder="合同描述 / 快递单号")
        
        # 查询逻辑
        logs = get_logistics_list_for_ui(
            status_list=sel_log_st,
            vc_type_list=sel_vc_types,
            search_keyword=search_log
        )
        
        if logs:
            log_df_data = []
            for l in logs:
                eo_count = len(get_express_orders_by_logistics(l['id']))
                log_df_data.append({
                    "物流ID": l['id'],
                    "关联合同": l['vc_description'] if 'vc_description' in l else "N/A",
                    "合同类型": l['vc_type'] if 'vc_type' in l else "N/A",
                    "物流状态": l['status'],
                    "子单数量": eo_count,
                    "最后更新": l['timestamp'] # get_logistics_list_for_ui already formats timestamp as string or keeps as datetime? 
                    # Let's check logic/logistics/queries.py
                })
            
            log_df = pd.DataFrame(log_df_data)
            log_event = st.dataframe(
                log_df,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row",
                height=350,
                key="log_overview_table"
            )
            
            selected_log_rows = log_event.get("selection", {}).get("rows", [])
            if selected_log_rows:
                idx = selected_log_rows[0]
                target_log_id = int(log_df.iloc[idx]["物流ID"])
                sel_log = get_logistics_by_id(target_log_id)
                
                if sel_log:
                    st.divider()
                    l_vc = get_vc_by_id(sel_log['virtual_contract_id'])
                    
                    sel_l_tab = sac.tabs([
                        sac.TabsItem('任务详情', icon='info-circle'),
                        sac.TabsItem('规则管理', icon='shield-check'),
                    ], align='center', variant='outline', key=f'log_tabs_{sel_log["id"]}')
                    
                    if sel_l_tab == '任务详情':
                        # 1. 顶部摘要卡片
                        status_color = "#3498DB" if sel_log['status'] != LogisticsStatus.FINISH else "#2ECC71"
                        st.markdown(f"""
<div style='background: white; border-radius: 12px; border: 1px solid #edf2f7; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 20px;'>
    <div style='display: flex; justify-content: space-between; align-items: flex-start;'>
        <div style='flex: 1;'>
            <div style='color: #718096; font-size: 12px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 4px;'><i class='bi bi-box-seam'></i> 物流任务详情</div>
            <h3 style='margin: 0; color: #2d3436; font-size: 18px;'>{l_vc['description'] if l_vc else "未命名合同"}</h3>
            <div style='margin-top: 8px; font-size: 13px; color: #636e72;'>
                <span style='background: #f1f2f6; padding: 2px 8px; border-radius: 4px; margin-right: 10px;'>ID: {sel_log['id']}</span>
                <span style='background: #f1f2f6; padding: 2px 8px; border-radius: 4px;'>类型: {l_vc['type'] if l_vc else "N/A"}</span>
            </div>
        </div>
        <div style='text-align: right;'>
            <div style='background: {status_color}; color: white; padding: 6px 16px; border-radius: 20px; font-size: 14px; font-weight: bold; display: inline-block;'>
                {sel_log['status']}
            </div>
            <div style='color: #a0aec0; font-size: 11px; margin-top: 6px;'>更新于: {sel_log['timestamp'] if sel_log['timestamp'] else "-"}</div>
        </div>
    </div>
</div>
""".replace('\n', ' ').strip(), unsafe_allow_html=True)
                        
                        # 2. 快递子单展示
                        st.markdown("##### <i class='bi bi-link-45deg'></i> 关联物流子单", unsafe_allow_html=True)
                        eos = get_express_orders_by_logistics(sel_log['id'])
                        if eos:
                            for e in eos:
                                eo_status_cls = "status-transit" if e['status'] == LogisticsStatus.TRANSIT else ("status-signed" if e['status'] == LogisticsStatus.SIGNED else "status-ready")
                                items_summary = format_item_list_preview(e.get('items')) if e.get('items') else "无明细数据"
                                addr_info = e.get('address_info') or {}
                                
                                st.markdown(f"""
<div class='express-card' style='border-left: 5px solid {status_color}; padding: 15px; background: #fdfdfd; margin-bottom: 12px; position: relative;'>
    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;'>
        <div style='font-family: monospace; font-weight: bold; font-size: 15px; color: #2C3E50;'><i class='bi bi-file-earmark-text'></i> {e['tracking_number']}</div>
        <span class='status-badge {eo_status_cls}' style='margin: 0;'>{e['status']}</span>
    </div>
    <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 20px;'>
        <div>
            <div style='color: #a0aec0; font-size: 11px; font-weight: bold; text-transform: uppercase;'>送达点位</div>
            <div style='font-size: 13px; color: #2d3436; font-weight: 500;'>{addr_info.get("收货点位名称") or addr_info.get("发货点位名称") or "未知点位"}</div>
            <div style='font-size: 12px; color: #718096; margin-top: 2px; line-height: 1.4; max-width: 300px;'>{addr_info.get("收货地址") or addr_info.get("发货地址") or "无详细地址"}</div>
        </div>
        <div>
            <div style='color: #a0aec0; font-size: 11px; font-weight: bold; text-transform: uppercase;'>包含物品</div>
            <div style='font-size: 12px; color: #4a5568; line-height: 1.5; margin-top: 4px; overflow: hidden; text-overflow: ellipsis;'>{items_summary}</div>
        </div>
    </div>
</div>
""".replace('\n', ' ').strip(), unsafe_allow_html=True)
                        else:
                            st.info("该物流任务目前暂无具体的快递子单记录。")

                    elif sel_l_tab == '规则管理':
                        show_rule_manager_tab(sel_log['id'], TimeRuleRelatedType.LOGISTICS)
        else:
            st.info("未找到符合条件的物流单。")

    # Tab 3 (资金全局概览) removed
    pass


    # --- 全局弹窗触发器 (放在末尾确保始终执行，避免被收起的 Expander 隔离) ---
    for key in list(st.session_state.keys()):
        if key.startswith("show_inbound_confirm_") and st.session_state[key]:
            log_id = int(key.replace("show_inbound_confirm_", ""))
            confirm_inbound_dialog(session, log_id, st.session_state.get(f"temp_sn_list_{log_id}", []))
        if key.startswith("show_log_plan_confirm_") and st.session_state[key]:
            vc_id = int(key.replace("show_log_plan_confirm_", ""))
            confirm_logistics_plan_dialog(session, vc_id)
    
    session.close()

def show_cash_flow_page():
    st.markdown("<h1 style='font-size: 24px;'><i class='bi bi-coin'></i> 资金流管理</h1>", unsafe_allow_html=True)
    with st.container():
        sel_tab = sac.tabs([
            sac.TabsItem('资金流录入', icon='pencil-square'),
            sac.TabsItem('资金全局概览', icon='eye'),
        ], align='center', variant='outline', key='cash_flow_tabs')
    
    session = get_session()

    if sel_tab == '资金流录入':
        st.subheader("资金流列表")
        vcs = get_vc_list_for_overview(status_list=[VCStatus.EXE])
        # 排除 cash_status=FINISH 的VC（货款已结清，不需要再录入资金流）
        vcs = [v for v in vcs if v['cash_status'] != CashStatus.FINISH]
        if vcs:
            vc_options = {f"[{v['type']}] {v['description']} (ID:{v['id']})": v['id'] for v in vcs}
            selected_vc_desc = st.selectbox("1. 选择关联虚拟合同", list(vc_options.keys()))
            target_vc_id = vc_options[selected_vc_desc]
            target_vc = get_vc_by_id(target_vc_id)
            
            if target_vc:
                existing_cfs = get_cash_flow_list_for_ui(vc_id=target_vc_id)
                progress = calculate_cashflow_progress(session, target_vc, existing_cfs)
                
                is_return = progress['is_return']
                goods = progress['goods']
                deposit = progress['deposit']
                payment_terms = progress['payment_terms']

                c_hint1, c_hint2 = st.columns([2.5, 1])
                with c_hint1:
                    if is_return or goods['total'] > 0:
                        raw_payable = goods['net_payable'] - goods['pool'] if not is_return else goods['total']
                        display_payable = max(0.0, raw_payable)
                        
                        if not is_return:
                            payable_label = "应付金额 (池内余额充足)" if display_payable < 0.01 and goods['pool'] > 0 else "应付金额 (现金)"
                        else:
                            payable_label = goods['label']
                        
                        pool_html = f"<div><span style='color:#6D28D9; font-size:11px;'>可用冲抵池</span><br><b style='color:#6D28D9; font-size:16px;'>¥ {goods['pool']:,.2f}</b></div>" if goods['pool'] > 0.01 else ""
                        offset_hint_html = f"<div style='color:#6c757d; font-size:10px; margin-top:5px;'>&middot; 合同原始总额: ¥{goods['total']:,.2f} | 累计已冲抵: ¥{goods.get('applied_offsets', 0):,.2f}</div>" if goods.get('applied_offsets', 0) > 0.01 else ""

                        dashboard_html = f"""
<div style='background: #f8f9fa; border-left: 5px solid {"#E74C3C" if is_return else "#2ECC71"}; padding: 15px; border-radius: 8px; margin-bottom: 10px;'>
    <div style='color: #636e72; font-size: 13px; margin-bottom: 8px;'><i class='bi bi-currency-exchange'></i> { "退款进度统计" if is_return else "合同款项概览" } (类型: {target_vc['type']})</div>
    <div style='display: flex; gap: 30px;'>
        <div><span style='color:#636e72; font-size:11px;'>{payable_label}</span><br><b style='color:#2D3436; font-size:16px;'>¥ {display_payable:,.2f}</b></div>
        <div><span style='color:#636e72; font-size:11px;'>{goods['paid_label']}</span><br><b style='color:{"#E74C3C" if is_return else "#2ECC71"}; font-size:16px;'>¥ {goods['paid']:,.2f}</b></div>
        <div><span style='color:#636e72; font-size:11px;'>{goods['balance_label']}</span><br><b style='color:{"#E74C3C" if goods['balance']>0.01 else "#BDC3C7"}; font-size:16px;'>¥ {goods['balance']:,.2f}</b></div>
        {pool_html}
    </div>
    {offset_hint_html}
</div>
""".replace('\n', ' ').strip()
                        st.markdown(dashboard_html, unsafe_allow_html=True)
                    
                    if is_return or deposit['should'] > 0:
                        st.markdown(f"""
                        <div style='background: #f0f7ff; border-left: 5px solid #3498DB; padding: 12px; border-radius: 8px;'>
                            <div style='color: #2980B9; font-size: 12px; font-weight: bold; margin-bottom: 5px;'><i class='bi bi-shield-lock'></i> { "押金退还进度" if is_return else "押金财务看板" }</div>
                            <div style='display: flex; gap: 40px;'>
                                <div><span style='color:#7F8C8D; font-size:11px;'>{"应退押金" if is_return else "应收押金"}</span><br><b style='color:#2C3E50; font-size:14px;'>¥ {deposit['should']:,.2f}</b></div>
                                <div><span style='color:#7F8C8D; font-size:11px;'>{"已退押金" if is_return else "已收押金"}</span><br><b style='color:#27AE60; font-size:14px;'>¥ {deposit['received']:,.2f}</b></div>
                                <div><span style='color:#7F8C8D; font-size:11px;'>{"待退押金" if is_return else "待收押金"}</span><br><b style='color:{"#E67E22" if deposit['remaining'] > 0.01 else "#BDC3C7"}; font-size:14px;'>¥ {deposit['remaining']:,.2f}</b></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                with c_hint2:
                    if is_return:
                        st.markdown(f"""
                        <div style='background: #fff; border: 1px solid #eee; padding: 10px; border-radius: 8px; font-size: 12px; height: 100%;'>
                            <div style='font-weight:bold; color:#E74C3C; margin-bottom:5px;'><i class='bi bi-arrow-return-left'></i> 退货详情</div>
                            <div style='color: #2D3436; font-size:11px;'>原因: {target_vc.get('elements', {}).get('reason', '未注明')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style='background: #fff; border: 1px solid #eee; padding: 10px; border-radius: 8px; font-size: 12px; height: 100%;'>
                            <div style='font-weight:bold; color:#6D28D9; margin-bottom:5px;'><i class='bi bi-file-text'></i> 账期约定</div>
                            <div style='color: #2D3436; line-height: 1.6;'>
                            • 预付: {int(payment_terms.get('prepayment_ratio', 0)*100)}%<br>
                            • 账期: {payment_terms.get('balance_period', 'N/A')}<br>
                            • 起算: {payment_terms.get('start_trigger', 'N/A')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                st.write("") 

                type_options = []
                if is_return:
                    if goods['balance'] > 0.01: type_options.append(CashFlowType.REFUND)
                    if deposit['remaining'] > 0.01: type_options.append(CashFlowType.RETURN_DEPOSIT)
                    if not type_options: type_options = [CashFlowType.REFUND, CashFlowType.RETURN_DEPOSIT]
                else:
                    type_options = [CashFlowType.PREPAYMENT, CashFlowType.FULFILLMENT, CashFlowType.DEPOSIT, CashFlowType.RETURN_DEPOSIT, CashFlowType.PENALTY]
                    if target_vc.get('subject_status') == SubjectStatus.FINISH:
                        type_options = [t for t in type_options if t != CashFlowType.PREPAYMENT]
                    if payment_terms.get('prepayment_ratio', 0) <= 0:
                        type_options = [t for t in type_options if t != CashFlowType.PREPAYMENT]
                    if deposit['should'] <= 0:
                        type_options = [t for t in type_options if t not in [CashFlowType.DEPOSIT, CashFlowType.RETURN_DEPOSIT]]
                    if goods['balance'] <= 0.01:
                        type_options = [t for t in type_options if t not in [CashFlowType.PREPAYMENT, CashFlowType.FULFILLMENT]]
                    if deposit['remaining'] <= 0.01:
                        type_options = [t for t in type_options if t != CashFlowType.DEPOSIT]

                c_type_col1, c_type_col2 = st.columns([2, 1])
                cf_type = c_type_col1.selectbox("2. 选择资金款项性质", type_options)
                amount = c_type_col2.number_input("3. 本次操作金额", min_value=0.0, value=0.0, step=100.0)

                candidate_payer_type, candidate_payer_id, candidate_payee_type, candidate_payee_id = get_suggested_cashflow_parties(session, target_vc, cf_type=cf_type)

                payer_accounts = get_bank_account_list_for_ui(owner_type=candidate_payer_type, owner_id=candidate_payer_id if candidate_payer_type != AccountOwnerType.OURSELVES else None)
                payer_options = {f"{a['bank_name']} (*{str(a['account_no'])[-4:]})" : a['id'] for a in payer_accounts}
                payer_options["未指定/内部现金"] = None
                
                payee_accounts = get_bank_account_list_for_ui(owner_type=candidate_payee_type, owner_id=candidate_payee_id if candidate_payee_type != AccountOwnerType.OURSELVES else None)
                payee_options = {f"{a['bank_name']} (*{str(a['account_no'])[-4:]})" : a['id'] for a in payee_accounts}
                payee_options["未指定/内部现金"] = None
                
                def_payer_idx = 0
                for idx, a in enumerate(payer_accounts):
                    if a['is_default']: def_payer_idx = idx
                
                def_payee_idx = 0
                for idx, a in enumerate(payee_accounts):
                    if a['is_default']: def_payee_idx = idx

                with st.form("cash_flow_full_form"):
                    st.caption(f"确认收存账号 ({candidate_payer_type} ➡️ {candidate_payee_type})")
                    col_a1, col_a2 = st.columns(2)
                    payer_acc_label = col_a1.selectbox(f"付款账户", list(payer_options.keys()), index=min(def_payer_idx, len(payer_options)-1))
                    payee_acc_label = col_a2.selectbox(f"收款账户", list(payee_options.keys()), index=min(def_payee_idx, len(payee_options)-1))
                    
                    desc = st.text_input("备注说明", placeholder="例如：支付第一批货款尾款")
                    submit = st.form_submit_button("确认录入", type="primary")
                    
                    if submit:
                        if amount <= 0:
                            st.error("金额必须大于0")
                        else:
                            st.session_state["temp_cf_data"] = {
                                "vc_id": target_vc_id,
                                "type": cf_type,
                                "amount": amount,
                                "payer_id": payer_options[payer_acc_label],
                                "payee_id": payee_options[payee_acc_label],
                                "payer_label": payer_acc_label,
                                "payee_label": payee_acc_label,
                                "description": desc,
                                "date": pd.Timestamp.now().isoformat()
                            }
                            st.session_state["show_cf_confirm"] = True
                            st.rerun()
        else:
            st.info("当前没有执行中的虚拟合同。")

        st.divider()
        st.markdown("#### <i class='bi bi-clock-history'></i> 最近资金收付记录", unsafe_allow_html=True)
        all_cf = get_cash_flow_list_for_ui(limit=20)
        if all_cf:
            cf_data = []
            for cf in all_cf:
                cf_data.append({
                    "记录时间": cf['transaction_date'],
                    "流水ID": cf['id'],
                    "关联合同": cf['vc_description'],
                    "资金类型": cf['type'],
                    "金额(元)": cf['amount'],
                    "付款方": cf['payer_info']['label'],
                    "收款方": cf['payee_info']['label'],
                    "说明": cf['description']
                })
            st.dataframe(pd.DataFrame(cf_data), use_container_width=True)

    elif sel_tab == '资金全局概览':
        st.markdown("### <i class='bi bi-cash-coin'></i> 资金收付全局概览", unsafe_allow_html=True)
        f_c1, f_c2, f_c3 = st.columns(3)
        all_cf_types = [CashFlowType.PREPAYMENT, CashFlowType.FULFILLMENT, CashFlowType.DEPOSIT, CashFlowType.RETURN_DEPOSIT, CashFlowType.REFUND, CashFlowType.PENALTY]
        sel_cf_types = f_c1.multiselect("资金类型", all_cf_types, default=all_cf_types)
        search_cf = f_c2.text_input("搜索流水", placeholder="合同描述 / 备注 / 流水ID")
        
        cfs = get_cash_flow_list_for_ui(limit=100)
        
        if cfs:
            cf_df_data = [{"流水ID": cf['id'], "日期": cf['transaction_date'], "关联合同": cf['vc_description'], "类型": cf['type'], "金额": cf['amount'], "备注": cf['description']} for cf in cfs]
            cf_overview_df = pd.DataFrame(cf_df_data)
            cf_event = st.dataframe(cf_overview_df, use_container_width=True, on_select="rerun", selection_mode="single-row", height=350, key="cf_overview_table")
            
            selected_cf_rows = cf_event.get("selection", {}).get("rows", [])
            if selected_cf_rows:
                idx = selected_cf_rows[0]
                target_cf_id = int(cf_overview_df.iloc[idx]["流水ID"])
                sel_cf = next((c for c in cfs if c['id'] == target_cf_id), None)
                
                if sel_cf:
                    st.divider()
                    st.markdown(f"#### <i class='bi bi-info-circle'></i> 资金流水详情 (ID: {sel_cf['id']})", unsafe_allow_html=True)
                    sd_c1, sd_c2, sd_c3 = st.columns(3)
                    sd_c1.metric("交易金额", f"¥ {sel_cf['amount']:,.2f}")
                    sd_c2.metric("资金类型", sel_cf['type'])
                    sd_c3.metric("交易时间", sel_cf['transaction_date'])
                    
                    st.markdown(f"""
<div style='background: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #edf2f7; margin-top: 10px;'>
    <div style='color: #718096; font-size: 12px; margin-bottom: 10px; font-weight: 600; letter-spacing: 1px;'><i class='bi bi-bank'></i> 资金收付链路</div>
    <div style='display: flex; align-items: center; gap: 15px;'>
        {sel_cf['payer_info']['label']} <div style='color: #cbd5e0; font-size: 20px;'>➜</div> {sel_cf['payee_info']['label']}
    </div>
</div>
""".replace('\n', ' ').strip(), unsafe_allow_html=True)
                    
                    vd_c1, vd_c2 = st.columns(2)
                    with vd_c1:
                        st.write(f"- **关联合同**: {sel_cf['vc_description']}")
                    with vd_c2:
                        st.write(f"- **备注**: {sel_cf['description'] or '无'}")
        else:
            st.info("尚未发现资金流水记录。")

    if st.session_state.get("show_cf_confirm"):
        confirm_cash_flow_dialog(session, st.session_state.get("temp_cf_data"))

    session.close()
