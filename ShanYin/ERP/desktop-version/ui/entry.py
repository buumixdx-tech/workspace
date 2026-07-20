import streamlit as st
from models import get_session, ChannelCustomer, Point, Supplier, SKU, ExternalPartner, BankAccount
import pandas as pd
import streamlit_antd_components as sac
from logic.constants import PointType, SupplierCategory, SKUType, ExternalPartnerType, AccountOwnerType, BankInfoKey, PartnerRelationType
from logic.master import (
    create_customer_action, update_customers_action,
    create_point_action, update_points_action,
    create_supplier_action, update_suppliers_action,
    create_sku_action, update_skus_action,
    create_partner_action, update_partners_action, delete_partners_action,
    create_partner_relation_action, delete_partner_relations_action,
    CustomerSchema, PointSchema, SupplierSchema, SKUSchema, PartnerSchema,
    PartnerRelationSchema, DeleteMasterDataSchema, get_partner_detail_for_ui
)
from logic.finance import (
    create_bank_account_action, update_bank_accounts_action,
    CreateBankAccountSchema, UpdateBankAccountSchema
)
from logic.master.queries import (
    get_customers_for_ui, get_suppliers_for_ui, get_points_for_ui,
    get_skus_for_ui, get_partners_for_ui, get_bank_accounts_for_ui
)
from logic.file_mgmt import generate_master_data_excel, process_master_data_excel
from datetime import datetime

def show_entry_page():
    st.markdown("<h1 style='font-size: 24px;'><i class='bi bi-clipboard-data'></i> 信息录入与维护</h1>", unsafe_allow_html=True)
    st.info("提示：下方表格支持直接双击修改导出数据。修改后请点击下方的‘保存修改’按钮。")
    sel_tab = sac.tabs([
        sac.TabsItem('渠道客户', icon='people'),
        sac.TabsItem('点位', icon='geo-alt'),
        sac.TabsItem('供应商', icon='shop'),
        sac.TabsItem('SKU', icon='box-seam'),
        sac.TabsItem('外部合作方', icon='briefcase'),
        sac.TabsItem('银行账户', icon='bank'),
        sac.TabsItem('批量导入导出', icon='cloud-arrow-up'),
    ], align='center', variant='outline', key='entry_tabs')
    
    session = get_session()
    
    if sel_tab == '渠道客户':
        st.markdown("### <i class='bi bi-people'></i> 渠道客户维护", unsafe_allow_html=True)
        with st.expander("新增客户"):
            with st.form("customer_form"):
                name = st.text_input("客户名称")
                info = st.text_area("整体信息描述")
                submit = st.form_submit_button("提交保存")
                if submit and name:
                    result = create_customer_action(session, CustomerSchema(name=name, info=info))
                    if result.success:
                        st.success(result.message)
                        st.rerun()
                    else:
                        st.error(result.error)

        data = get_customers_for_ui()
        if data:
            df = pd.DataFrame([{"ID": c["id"], "名称": c["name"], "信息": c["info"]} for c in data])
            edited_df = st.data_editor(df, use_container_width=True, disabled=["ID"], key="edit_cust", hide_index=True)
            if st.button("保存客户信息修改"):
                payloads = [CustomerSchema(id=int(row["ID"]), name=row["名称"], info=row["信息"]) for _, row in edited_df.iterrows()]
                result = update_customers_action(session, payloads)
                if result.success:
                    st.success(result.message)
                    st.rerun()
                else:
                    st.error(result.error)

    elif sel_tab == '点位':
        st.markdown("### <i class='bi bi-geo-alt'></i> 点位维护", unsafe_allow_html=True)
        customers = get_customers_for_ui()
        suppliers = get_suppliers_for_ui()
        
        owner_options = {"[公司] 闪饮自身": (AccountOwnerType.OURSELVES, None)}
        for c in customers: owner_options[f"[客户] {c['name']}"] = (AccountOwnerType.CUSTOMER, c['id'])
        for s in suppliers: owner_options[f"[供应商] {s['name']}"] = (AccountOwnerType.SUPPLIER, s['id'])

        with st.expander("新增点位"):
            with st.form("point_form"):
                selection = st.selectbox("归属主体", list(owner_options.keys()))
                name = st.text_input("点位名称")
                addr = st.text_input("详细地址")
                p_type = st.selectbox("类型", PointType.ALL_TYPES)
                recv_addr = st.text_input("收货地址(通常同详细地址)", value=addr)
                
                if st.form_submit_button("保存点位"):
                    otype, oid = owner_options[selection]
                    payload = PointSchema(
                        name=name, type=p_type, address=addr, receiving_address=recv_addr or addr,
                        customer_id=oid if otype == AccountOwnerType.CUSTOMER else None,
                        supplier_id=oid if otype == AccountOwnerType.SUPPLIER else None
                    )
                    result = create_point_action(session, payload)
                    if result.success:
                        st.success(result.message)
                        st.rerun()
                    else:
                        st.error(result.error)

        data = get_points_for_ui()
        if data:
            df = pd.DataFrame([
                {"ID": p["id"], "名称": p["name"], "归属主体": p["owner_label"], "类型": p["type"], "地址": p["address"], "收货地址": p["receiving_address"]} 
                for p in data
            ])
            edited_df = st.data_editor(df, use_container_width=True, disabled=["ID"], key="edit_point", hide_index=True, column_config={
                "类型": st.column_config.SelectboxColumn("类型", options=PointType.ALL_TYPES),
                "归属主体": st.column_config.SelectboxColumn("归属主体", options=list(owner_options.keys()))
            })
            if st.button("保存点位修改"):
                payloads = []
                for _, row in edited_df.iterrows():
                    otype, oid = owner_options[row["归属主体"]]
                    payloads.append(PointSchema(
                        id=int(row["ID"]), name=row["名称"], type=row["类型"], address=row["地址"], receiving_address=row["收货地址"],
                        customer_id=oid if otype == AccountOwnerType.CUSTOMER else None,
                        supplier_id=oid if otype == AccountOwnerType.SUPPLIER else None
                    ))
                result = update_points_action(session, payloads)
                if result.success:
                    st.success(result.message)
                    st.rerun()
                else: st.error(result.error)

    elif sel_tab == '供应商':
        st.markdown("### <i class='bi bi-shop'></i> 供应商维护", unsafe_allow_html=True)
        with st.expander("新增供应商"):
            with st.form("supplier_form"):
                name = st.text_input("供应商名称")
                cat = st.selectbox("供应类别", SupplierCategory.ALL_TYPES)
                addr = st.text_input("地址信息")
                if st.form_submit_button("保存供应商"):
                    result = create_supplier_action(session, SupplierSchema(name=name, category=cat, address=addr))
                    if result.success: st.rerun()
                    else: st.error(result.error)

        data = get_suppliers_for_ui()
        if data:
            df = pd.DataFrame([{"ID": s["id"], "名称": s["name"], "类别": s["category"], "地址": s["address"]} for s in data])
            edited_df = st.data_editor(df, use_container_width=True, disabled=["ID"], key="edit_supp", hide_index=True, column_config={
                "类别": st.column_config.SelectboxColumn("类别", options=SupplierCategory.ALL_TYPES)
            })
            if st.button("保存供应商修改"):
                payloads = [SupplierSchema(id=int(row["ID"]), name=row["名称"], category=row["类别"], address=row["地址"]) for _, row in edited_df.iterrows()]
                result = update_suppliers_action(session, payloads)
                if result.success: st.rerun()
                else: st.error(result.error)

    elif sel_tab == 'SKU':
        st.markdown("### <i class='bi bi-box-seam'></i> SKU维护", unsafe_allow_html=True)
        suppliers = get_suppliers_for_ui()
        supp_options = {s["name"]: s["id"] for s in suppliers}
        with st.expander("新增SKU"):
            with st.form("sku_form"):
                s_name = st.selectbox("所属供应商", list(supp_options.keys()))
                name = st.text_input("SKU名称")
                t1 = st.selectbox("一级分类", SKUType.ALL_TYPES)
                model = st.text_input("型号")
                if st.form_submit_button("保存SKU"):
                    result = create_sku_action(session, SKUSchema(supplier_id=supp_options[s_name], name=name, type_level1=t1, model=model))
                    if result.success: st.rerun()
                    else: st.error(result.error)

        data = get_skus_for_ui()
        if data:
            df = pd.DataFrame([{"ID": k["id"], "名称": k["name"], "供应商": k["supplier_name"], "一级分类": k["type_level1"], "型号": k["model"]} for k in data])
            edited_df = st.data_editor(df, use_container_width=True, disabled=["ID"], key="edit_sku", hide_index=True, column_config={
                "供应商": st.column_config.SelectboxColumn("供应商", options=list(supp_options.keys())),
                "一级分类": st.column_config.SelectboxColumn("一级分类", options=SKUType.ALL_TYPES)
            })
            if st.button("保存SKU修改"):
                payloads = [SKUSchema(id=int(row["ID"]), name=row["名称"], supplier_id=supp_options.get(row["供应商"]), type_level1=row["一级分类"], model=row["型号"]) for _, row in edited_df.iterrows()]
                result = update_skus_action(session, payloads)
                if result.success: st.rerun()
                else: st.error(result.error)

    elif sel_tab == '外部合作方':
        st.markdown("### <i class='bi bi-briefcase'></i> 外部合作方维护", unsafe_allow_html=True)

        # ---- 新增合作方 ----
        with st.expander("➕ 新增合作方"):
            with st.form("ext_p_form"):
                name = st.text_input("名称", placeholder="请输入合作方名称")
                p_type = st.selectbox("类型", ExternalPartnerType.ALL_TYPES)
                address = st.text_input("地址", placeholder="请输入地址（可选）")
                content = st.text_area("备注", placeholder="请输入备注信息（可选）", height=80)
                if st.form_submit_button("💾 保存合作方"):
                    if not name:
                        st.error("请输入合作方名称")
                    else:
                        result = create_partner_action(session, PartnerSchema(
                            name=name, type=p_type, address=address, content=content
                        ))
                        if result.success:
                            st.success("合作方创建成功")
                            st.rerun()
                        else:
                            st.error(result.error)

        # ---- 搜索和筛选 ----
        col1, col2 = st.columns([3, 1])
        with col1:
            search_keyword = st.text_input("🔍 搜索", placeholder="搜索合作方名称...", key="partner_search")
        with col2:
            type_filter = st.selectbox("类型筛选", ["全部"] + ExternalPartnerType.ALL_TYPES, key="partner_type_filter")

        # ---- 合作方列表（单选）----
        data = get_partners_for_ui()
        if search_keyword:
            data = [p for p in data if search_keyword.lower() in p.get("name", "").lower()]
        if type_filter != "全部":
            data = [p for p in data if p.get("partner_type") == type_filter]

        if not data:
            st.info("暂无合作方数据，请点击上方「新增合作方」创建")
        else:
            # ---- 合作方列表（类似Excel风格，可单选）----
            st.write("**合作方列表：**")

            # 构建表格数据
            table_data = []
            for p in data:
                table_data.append({
                    "选择": False,
                    "ID": p["id"],
                    "名称": p["name"],
                    "类型": p.get("partner_type", "") or "",
                    "地址": (p.get("address", "") or "")[:25] + ("..." if len(p.get("address", "") or "") > 25 else ""),
                })

            df = pd.DataFrame(table_data)

            # 使用 data_editor 显示（只读，ID不可编辑）
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                hide_index=True,
                disabled=["ID", "名称", "类型", "地址"],
                key="partner_list",
                column_config={
                    "选择": st.column_config.CheckboxColumn("选择", default=False),
                    "ID": st.column_config.NumberColumn("ID", disabled=True),
                    "名称": st.column_config.TextColumn("名称"),
                    "类型": st.column_config.SelectboxColumn("类型", options=ExternalPartnerType.ALL_TYPES),
                },
                num_rows="fixed"
            )

            # 获取选中的行
            selected_rows = edited_df[edited_df["选择"] == True]
            selected_partner_id = int(selected_rows["ID"].iloc[0]) if len(selected_rows) > 0 else None

            # ---- 选中后的详情 ----
            if selected_partner_id:
                partner_id = selected_partner_id
                partner_detail = get_partner_detail_for_ui(partner_id)

                if partner_detail:
                    st.divider()
                    st.markdown(f"#### 📋 合作方详情: **{partner_detail['name']}**")

                    # Tabs for detail sections
                    det_tab = sac.tabs([
                        sac.TabsItem('基本信息', icon='info-circle'),
                        sac.TabsItem('银行账户', icon='bank'),
                        sac.TabsItem('合作关系', icon='link'),
                    ], align='left', variant='pill', key=f'partner_det_tabs_{partner_id}')

                    # ---- Tab 1: 基本信息 ----
                    if det_tab == '基本信息':
                        with st.form(f"partner_basic_{partner_id}", clear_on_submit=False):
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                edit_name = st.text_input("名称", value=partner_detail['name'])
                                edit_type = st.selectbox("类型", ExternalPartnerType.ALL_TYPES,
                                    index=ExternalPartnerType.ALL_TYPES.index(partner_detail['type']) if partner_detail['type'] in ExternalPartnerType.ALL_TYPES else 0)
                            with col2:
                                edit_address = st.text_input("地址", value=partner_detail.get('address', '') or "")
                            edit_content = st.text_area("备注", value=partner_detail.get('content', '') or "", height=100)

                            col_save, col_del = st.columns([1, 1])
                            with col_save:
                                if st.form_submit_button("💾 保存基本信息"):
                                    result = update_partners_action(session, [PartnerSchema(
                                        id=partner_id, name=edit_name, type=edit_type,
                                        address=edit_address, content=edit_content
                                    )])
                                    if result.success:
                                        st.success("已保存")
                                        st.rerun()
                                    else:
                                        st.error(result.error)
                            with col_del:
                                if st.form_submit_button("🗑️ 删除此合作方", type="primary"):
                                    result = delete_partners_action(session, [DeleteMasterDataSchema(id=partner_id)])
                                    if result.success:
                                        st.session_state.selected_partner_id = None
                                        st.success("已删除")
                                        st.rerun()
                                    else:
                                        st.error(result.error)

                    # ---- Tab 2: 银行账户 ----
                    elif det_tab == '银行账户':
                        banks = partner_detail.get('bank_accounts', [])

                        st.write(f"**已有银行账户 ({len(banks)} 个)**")
                        if banks:
                            for bank in banks:
                                with st.expander(f"🏦 {bank['bank_name']} - {bank['account_no'][:4]}****", expanded=False):
                                    with st.form(f"bank_edit_{bank['id']}", clear_on_submit=False):
                                        acc_name = st.text_input("开户名称", value=bank['holder_name'])
                                        bank_name = st.text_input("银行名称", value=bank['bank_name'])
                                        acc_num = st.text_input("账号", value=bank['account_no'])
                                        is_def = st.checkbox("默认账户", value=bank['is_default'])
                                        c1, c2 = st.columns(2)
                                        with c1:
                                            if st.form_submit_button("💾 保存"):
                                                payload = UpdateBankAccountSchema(
                                                    id=bank['id'],
                                                    owner_type=AccountOwnerType.PARTNER,
                                                    owner_id=partner_id,
                                                    account_info={BankInfoKey.HOLDER_NAME: acc_name, BankInfoKey.BANK_NAME: bank_name, BankInfoKey.ACCOUNT_NO: acc_num},
                                                    is_default=is_def
                                                )
                                                result = update_bank_accounts_action(session, [payload])
                                                if result.success:
                                                    st.success("已保存")
                                                    st.rerun()
                                                else:
                                                    st.error(result.error)
                                        with c2:
                                            if st.form_submit_button("🗑️ 删除"):
                                                from logic.master import delete_bank_accounts_action
                                                result = delete_bank_accounts_action(session, [DeleteMasterDataSchema(id=bank['id'])])
                                                if result.success:
                                                    st.success("已删除")
                                                    st.rerun()
                                                else:
                                                    st.error(result.error)
                        else:
                            st.info("暂无银行账户")

                        st.divider()
                        # 新增银行账户
                        with st.expander("➕ 新增银行账户"):
                            with st.form(f"bank_new_{partner_id}"):
                                acc_name = st.text_input("开户名称", placeholder="合作方公司名称")
                                bank_name = st.text_input("银行名称", placeholder="如：招商银行北京分行")
                                acc_num = st.text_input("银行账号", placeholder="请输入账号")
                                is_def = st.checkbox("设为默认账户", value=True)
                                if st.form_submit_button("💾 保存账户"):
                                    if not acc_name or not bank_name or not acc_num:
                                        st.error("请填写完整信息")
                                    else:
                                        payload = CreateBankAccountSchema(
                                            owner_type=AccountOwnerType.PARTNER,
                                            owner_id=partner_id,
                                            account_info={BankInfoKey.HOLDER_NAME: acc_name, BankInfoKey.BANK_NAME: bank_name, BankInfoKey.ACCOUNT_NO: acc_num},
                                            is_default=is_def
                                        )
                                        result = create_bank_account_action(session, payload)
                                        if result.success:
                                            st.success("账户已添加")
                                            st.rerun()
                                        else:
                                            st.error(result.error)

                    # ---- Tab 3: 合作关系 ----
                    elif det_tab == '合作关系':
                        relations = partner_detail.get('relations', [])

                        st.write(f"**已有合作关系 ({len(relations)} 个)**")
                        if relations:
                            for rel in relations:
                                status_label = "✅ 有效" if rel['is_active'] else "❌ 已终止"
                                with st.expander(f"{rel['relation_type']} → {rel.get('owner_name', rel['owner_type'])} ({status_label})", expanded=False):
                                    st.write(f"**合作模式**: {rel['relation_type']}")
                                    st.write(f"**归属主体**: {rel.get('owner_name', '未知')}")
                                    st.write(f"**建立时间**: {rel['established_at'] or '未知'}")
                                    st.write(f"**状态**: {status_label}")
                                    st.write(f"**备注**: {rel.get('remark', '') or '无'}")
                                    if st.button("🗑️ 删除此关系", key=f"del_rel_{rel['id']}"):
                                        result = delete_partner_relations_action(session, [DeleteMasterDataSchema(id=rel['id'])])
                                        if result.success:
                                            st.success("已删除")
                                            st.rerun()
                                        else:
                                            st.error(result.error)
                        else:
                            st.info("暂无合作关系")

                        st.divider()
                        # 新增合作关系
                        with st.expander("➕ 新增合作关系"):
                            # owner_type 在 form 外面，以便切换时能动态更新下属组件
                            owner_type = st.selectbox("归属主体类型",
                                ["business", "supply_chain", "ourselves"],
                                format_func=lambda x: {"business": "业务", "supply_chain": "供应链", "ourselves": "我方"}[x],
                                key=f"owner_type_{partner_id}"
                            )

                            # 根据 owner_type 动态加载下拉选项（在 form 外面）
                            if owner_type == "business":
                                from logic.business.queries import get_business_list
                                from logic.constants import BusinessStatus, PartnerRelationType
                                from models import PartnerRelation

                                businesses = get_business_list()

                                # 过滤掉已结束的业务
                                ended_statuses = [BusinessStatus.TERMINATED, BusinessStatus.FINISHED, BusinessStatus.PAUSED]
                                active_businesses = [b for b in businesses if b["status"] not in ended_statuses]

                                # 过滤掉已建立"采购执行"合作关系的业务
                                _session = get_session()
                                try:
                                    procurement_biz_ids = _session.query(PartnerRelation.owner_id).filter(
                                        PartnerRelation.owner_type == "business",
                                        PartnerRelation.relation_type == PartnerRelationType.PROCUREMENT,
                                        PartnerRelation.ended_at.is_(None)
                                    ).all()
                                    procurement_biz_ids = set([r[0] for r in procurement_biz_ids])
                                finally:
                                    _session.close()

                                available_businesses = [b for b in active_businesses if b["id"] not in procurement_biz_ids]
                                owner_options = {b["id"]: b["customer_name"] for b in available_businesses}

                                if not owner_options:
                                    st.warning("暂无可关联的业务数据")
                                    owner_id = None
                                else:
                                    owner_id = st.selectbox("选择业务", list(owner_options.keys()),
                                        format_func=lambda x: owner_options[x],
                                        key=f"owner_id_biz_{partner_id}")
                            elif owner_type == "supply_chain":
                                from logic.supply_chain.queries import get_supply_chains_for_ui
                                chains = get_supply_chains_for_ui()
                                owner_options = {c["id"]: c["supplier_name"] for c in chains}
                                if not owner_options:
                                    st.warning("暂无供应链协议，请先创建供应链")
                                    owner_id = None
                                else:
                                    owner_id = st.selectbox("选择供应链", list(owner_options.keys()),
                                        format_func=lambda x: owner_options[x],
                                        key=f"owner_id_sc_{partner_id}")
                            else:  # ourselves
                                st.write("**归属主体**: 闪饮业务中心（我方）")
                                owner_id = None

                            with st.form(f"rel_new_{partner_id}"):
                                relation_type = st.selectbox("合作模式", PartnerRelationType.ALL_TYPES)
                                remark = st.text_area("备注", placeholder="请输入备注信息（可选）")

                                if st.form_submit_button("💾 保存合作关系"):
                                    if owner_type != "ourselves" and not owner_id:
                                        st.error("请选择归属主体")
                                    else:
                                        payload = PartnerRelationSchema(
                                            partner_id=partner_id,
                                            owner_type=owner_type,
                                            owner_id=owner_id,
                                            relation_type=relation_type,
                                            remark=remark
                                        )
                                        result = create_partner_relation_action(session, payload)
                                        if result.success:
                                            st.success("合作关系已创建")
                                            st.rerun()
                                        else:
                                            st.error(result.error)
                
    elif sel_tab == '银行账户':
        st.markdown("### <i class='bi bi-bank'></i> 银行账户维护", unsafe_allow_html=True)
        customers = get_customers_for_ui()
        suppliers = get_suppliers_for_ui()
        partners = get_partners_for_ui()
        
        # Build owner options dict similarly to points
        owner_options = {"[公司] 闪饮自身": (AccountOwnerType.OURSELVES, None)}
        for c in customers: owner_options[f"[客户] {c['name']}"] = (AccountOwnerType.CUSTOMER, c["id"])
        for s in suppliers: owner_options[f"[供应商] {s['name']}"] = (AccountOwnerType.SUPPLIER, s["id"])
        for p in partners: owner_options[f"[合作方] {p['name']}"] = (AccountOwnerType.PARTNER, p["id"])
        
        with st.expander("新增银行账户"):
            with st.form("bank_acc_form"):
                selection = st.selectbox("归属方", list(owner_options.keys()))
                acc_name = st.text_input("开户名称", placeholder="例如：闪饮科技有限公司")
                bank_name = st.text_input("银行名称", placeholder="例如：招商银行北京分行")
                acc_num = st.text_input("银行账号", placeholder="例如：622202...")
                is_default = st.checkbox("设为默认账户", value=True)
                
                if st.form_submit_button("保存账户"):
                    otype, oid = owner_options[selection]
                    
                    payload = CreateBankAccountSchema(
                        owner_type=otype,
                        owner_id=oid,
                        account_info={BankInfoKey.HOLDER_NAME: acc_name, BankInfoKey.BANK_NAME: bank_name, BankInfoKey.ACCOUNT_NO: acc_num},
                        is_default=is_default
                    )
                    
                    result = create_bank_account_action(session, payload)
                    if result.success:
                        st.success(result.message)
                        st.rerun()
                    else:
                        st.error(result.error)

        data = get_bank_accounts_for_ui()
        if data:
            df = pd.DataFrame([
                {
                    "ID": acc["id"], 
                    "归属方": acc["owner_label"], 
                    "开户名称": acc["holder_name"],
                    "银行名称": acc["bank_name"],
                    "银行账号": acc["account_no"],
                    "默认": acc["is_default"]
                } for acc in data
            ])
            edited_df = st.data_editor(
                df, use_container_width=True, disabled=["ID", "归属方"], key="edit_bank", hide_index=True
            )
            
            if st.button("保存账户修改", key="save_bank"):
                payloads = []
                for _, row in edited_df.iterrows():
                    acc_id = int(row["ID"])
                    account_info = {
                        BankInfoKey.HOLDER_NAME: row["开户名称"],
                        BankInfoKey.BANK_NAME: row["银行名称"],
                        BankInfoKey.ACCOUNT_NO: row["银行账号"]
                    }
                    # Find the account to get owner info
                    acc_data = next((a for a in data if a["id"] == acc_id), None)
                    if acc_data:
                        payloads.append(UpdateBankAccountSchema(
                            id=acc_id,
                            owner_type=acc_data["owner_type"],
                            owner_id=acc_data["owner_id"],
                            account_info=account_info,
                            is_default=bool(row["默认"])
                        ))
                result = update_bank_accounts_action(session, payloads)
                if result.success: st.rerun()
                else: st.error(result.error)

    elif sel_tab == '批量导入导出':
        st.markdown("### <i class='bi bi-cloud-arrow-up'></i> 基础数据批量导入与导出", unsafe_allow_html=True)
        st.info("💡 强烈建议在导入前，先下载最新模板提取云端最新数据和关系。")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("#### 第一步：导出数据模板")
            st.markdown("模板内包含了最新的下拉框验证数据。你可以直接在模板上修改或新增数据。")
            
            with st.spinner("正在生成最新导出文件..."):
                excel_bytes = generate_master_data_excel(session)
                
            current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"master_data_{current_time_str}.xlsx"
            
            st.download_button(
                label="📥 下载最新主数据Excel",
                data=excel_bytes,
                file_name=export_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="下载包含数据库内部ID与下拉联动的安全模板"
            )
            
        with col2:
            st.markdown("#### 第二步：上传更新文件")
            st.markdown("强烈建议谨慎使用最后一列的 `[操作指令]` 标记删除。")
            uploaded_file = st.file_uploader("只接受生成的模板格式Excel", type=["xlsx", "xls"])
            
            if uploaded_file is not None:
                if st.button("🚀 确认上传并覆盖入库", type="primary"):
                    with st.spinner("系统正在进行数据关系预检与入库，请稍候..."):
                        # Read bytes from streamlit UploadedFile object
                        file_bytes = uploaded_file.getvalue()
                        report = process_master_data_excel(session, file_bytes)
                        
                        st.divider()
                        st.markdown("### 📊 导入处理报告")
                        if report["success"]:
                            st.success("✅ 数据校验通过，写入执行成功！")
                        else:
                            st.error("❌ 处理过程中遇到阻断性错误。部分或全部数据未保存。")
                            
                        # Display Stats
                        s = report["stats"]
                        st.info(f"**处理统计**: 新增 **{s['新增']}** 条 | 更新 **{s['更新']}** 条 | 成功删除 **{s['删除']}** 条")
                        
                        # Display specific row/relation errors if any
                        if report["logs"]:
                            for log in report["logs"]:
                                if log.startswith("❌"): st.error(log)
                                elif log.startswith("⚠️"): st.warning(log)
                                else: st.text(log)
                                
                        if report["success"] and sum(s.values()) > 0:
                            # Re-generate the state if something successfully changed
                            if st.button("刷新页面加载最新数据"):
                                st.rerun()

    session.close()
