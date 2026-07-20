import streamlit as st
import pandas as pd
from models import get_session
from logic.constants import (
    TimeRuleRelatedType, TimeRuleInherit, TimeRuleParty, 
    TimeRuleOffsetUnit, TimeRuleDirection, TimeRuleStatus, EventType
)
from datetime import datetime
from logic.time_rules import (
    save_rule_action, delete_rule_action, persist_draft_rules_action,
    get_rules_for_entity, get_rule_by_id,
    TimeRuleSchema
)

def _safe_get(obj, attr, default=None):
    if not obj: return default
    if hasattr(obj, attr): return getattr(obj, attr)
    if isinstance(obj, dict): return obj.get(attr, default)
    return default

@st.dialog("规则编辑器", width="large")
def rule_editor_dialog(related_type, related_id, rule_id=None):
    """
    通用的规则编辑器对话框 (独立调用模式)
    """
    _rule_editor_form_ui(related_type, related_id, rule_id)

def _rule_editor_form_ui(related_type, related_id, rule_id=None, on_close=None):
    """
    核心规则编辑表单 UI，可嵌入 Tab 或 Dialog
    """
    session = get_session()
    
    rule = None
    if rule_id is not None:
        rule = get_rule_by_id(session, rule_id)
        if not rule:
            st.warning(f"未找到 ID 为 {rule_id} 的规则，已切换为创建模式。")
    
    st.write(f"正在为 **{related_type} (ID: {related_id})** {'编辑' if rule else '创建'}时间规则")
    
    # 汇总所有事件类型
    all_events = [EventType.Special.ABSOLUTE_DATE] + \
                 EventType.ContractLevel.ALL_EVENTS + \
                 EventType.VCLevel.ALL_EVENTS + \
                 EventType.LogisticsLevel.ALL_EVENTS
    
    # === 事件类型与作用范围选择 (原本在表单外，现移入表单以修复 Streamlit Form 提交完整性) ===
    with st.form(f"rule_edit_form_{related_type}_{related_id}"):
        t_col1, t_col2 = st.columns([1, 1])
        
        with t_col1:
            st.markdown("#### <i class='bi bi-flag'></i> 触发与范围", unsafe_allow_html=True)
            # 辅助函数：模糊匹配索引
            def find_idx(event, lst):
                if not event or not lst: return 0
                if event in lst: return lst.index(event)
                # 兼容带有“合同”前缀或后缀的旧数据
                for i, e in enumerate(lst):
                    if event in e or e in event: return i
                return 0

            trigger_val = _safe_get(rule, 'trigger_event')
            trigger_event = st.selectbox("触发事件", all_events, 
                                             index=find_idx(trigger_val, all_events) if rule else 0)
        
        # 根据关联类型动态设置作用范围标签
        if related_type == TimeRuleRelatedType.BUSINESS or related_type == TimeRuleRelatedType.SUPPLY_CHAIN:
            inherit_map = {"本级定制 (项目级)": 0, "近继承 (至虚拟合同)": 1, "远继承 (至物流)": 2}
        elif related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT:
            inherit_map = {"本级定制 (合同级)": 0, "近继承 (至物流)": 1}
        else: # LOGISTICS
            inherit_map = {"本级定制 (物流级)": 0}
            
        inherit_labels = list(inherit_map.keys())
        # 安全获取索引
        def get_inherit_index(r):
            if not r: return 0
            val = r.inherit if hasattr(r, 'inherit') else r.get('inherit')
            if val is None: return 0
            return min(int(val), len(inherit_labels) - 1)

        inherit_val_label = st.selectbox("作用范围", inherit_labels,
                                             index=get_inherit_index(rule))
        inherit_idx = inherit_map[inherit_val_label]

        with t_col2:
            st.markdown("#### 🎯 目标事件")
            target_val = _safe_get(rule, 'target_event')
            target_event = st.selectbox("目标事件", all_events, 
                                             index=find_idx(target_val, all_events) if rule else 0)

        st.divider()
        
        # 1. 基础信息
        c1, c2 = st.columns(2)
        rule_party = _safe_get(rule, 'party')
        party = c1.selectbox("责任方", [TimeRuleParty.OURSELVES, TimeRuleParty.CUSTOMER, TimeRuleParty.SUPPLIER], 
                             index=[TimeRuleParty.OURSELVES, TimeRuleParty.CUSTOMER, TimeRuleParty.SUPPLIER].index(rule_party) if rule and rule_party in [TimeRuleParty.OURSELVES, TimeRuleParty.CUSTOMER, TimeRuleParty.SUPPLIER] else 0)
        
        # 状态自动确定
        status_hint = "将自动设为'生效'" if inherit_idx == 0 else "将自动设为'模板'"
        c2.markdown(f"**规则状态**  \n{status_hint}")
        
        st.divider()
        
        # 2. 触发事件参数 (根据外部选择动态显示)
        st.markdown("##### 触发事件参数")
        abs_date = None
        if trigger_event == EventType.Special.ABSOLUTE_DATE:
            # 绝对日期模式：显示日期选择器
            flag_time_val = _safe_get(rule, 'flag_time')
            if isinstance(flag_time_val, str):
                try:
                    current_date = datetime.strptime(flag_time_val, "%Y-%m-%d %H:%M").date()
                except:
                    current_date = datetime.now().date()
            elif isinstance(flag_time_val, datetime):
                current_date = flag_time_val.date()
            else:
                current_date = datetime.now().date()
                
            abs_date = st.date_input("设定标杆日期", value=current_date)
            t_p1 = str(abs_date)
            t_p2 = "固定日期"
        else:
            # 普通事件模式：显示参数输入框
            tp_col1, tp_col2 = st.columns(2)
            t_p1 = tp_col1.text_input("触发参数1", value=_safe_get(rule, 'tge_param1', ""), help="例如：付款比例 0.5")
            t_p2 = tp_col2.text_input("触发参数2", value=_safe_get(rule, 'tge_param2', ""))
        
        # 3. 目标事件参数
        st.markdown("##### 目标事件参数")
        tae_col1, tae_col2 = st.columns(2)
        ta_p1 = tae_col1.text_input("目标参数1", value=_safe_get(rule, 'tae_param1', ""))
        ta_p2 = tae_col2.text_input("目标参数2", value=_safe_get(rule, 'tae_param2', ""))
        
        st.divider()
        
        # 4. 时间约束
        st.markdown("#### <i class='bi bi-hourglass-split'></i> 时间约束", unsafe_allow_html=True)
        co_col1, co_col2, co_col3 = st.columns(3)
        offset = co_col1.number_input("偏移数值", value=_safe_get(rule, 'offset', 0), step=1)
        
        unit_options = [TimeRuleOffsetUnit.NATURAL_DAY, TimeRuleOffsetUnit.WORK_DAY]
        rule_unit = _safe_get(rule, 'unit')
        unit = co_col2.selectbox("单位", unit_options,
                                 index=unit_options.index(rule_unit) if rule and rule_unit in unit_options else 0)
        direction_map = {"之前": TimeRuleDirection.BEFORE, "之后": TimeRuleDirection.AFTER}
        rule_direction = _safe_get(rule, 'direction')
        direction_label = co_col3.selectbox("方向", list(direction_map.keys()), 
                                             index=0 if not rule or rule_direction == TimeRuleDirection.BEFORE else 1)
        
        submit = st.form_submit_button("保存规则", type="primary", use_container_width=True)
        
        if submit:
            # 构造 payload
            payload = TimeRuleSchema(
                id=_safe_get(rule, 'id'),
                related_id=related_id,
                related_type=related_type,
                party=party,
                trigger_event=trigger_event,
                target_event=target_event,
                tge_param1=t_p1,
                tge_param2=t_p2,
                tae_param1=ta_p1,
                tae_param2=ta_p2,
                offset=offset,
                unit=unit,
                direction=direction_map[direction_label],
                inherit=inherit_idx,
                status=TimeRuleStatus.ACTIVE if inherit_idx == 0 else TimeRuleStatus.TEMPLATE,
                flag_time=datetime.combine(abs_date, datetime.min.time()) if trigger_event == EventType.Special.ABSOLUTE_DATE and abs_date else None
            )
            
            result = save_rule_action(session, payload)
            if result.success:
                st.success(result.message)
                if on_close: on_close()
                st.rerun()
            else:
                st.error(result.error)

def show_rule_manager_tab(related_id, related_type):
    """
    在 Tab 中显示规则管理列表
    """
    _show_rule_manager_content(related_id, related_type, inline=True)

@st.dialog("规则管理", width="large")
def rule_manager_dialog(related_type, related_id, allowed_inherit=None):
    """
    独立弹窗模式下的规则管理器
    """
    # 同步 operations.py 中的新 Key 格式，防止 ID 冲突
    trigger_key = f"trigger_rule_mgr_{related_type}_{related_id}"
    
    c1, c2 = st.columns([4, 1])
    c1.markdown(f"### <i class='bi bi-gear'></i> {related_type} 规则管理", unsafe_allow_html=True)
    if c2.button("退出管理", key=f"close_mgr_{related_id}", use_container_width=True, help="点击此按钮关闭窗口并返回业务表单。规则修改在保存时已生效。"):
        if trigger_key in st.session_state:
            del st.session_state[trigger_key] # 彻底删除触发键，不再使用 False
        st.rerun()
    _show_rule_manager_content(related_id, related_type, inline=False, allowed_inherit=allowed_inherit)

def _show_rule_manager_content(related_id, related_type, inline=True, allowed_inherit=None):
    """
    内部提取的规则管理内容渲染逻辑
    """
    # 使用 session_state 管理编辑器状态，避免弹窗嵌套
    edit_state_key = f"edit_rule_mode_{related_type}_{related_id}"
    target_rule_key = f"edit_rule_id_{related_type}_{related_id}"
    
    if st.session_state.get(edit_state_key):
        # 渲染编辑器模式
        st.markdown(f"### <i class='bi bi-pencil'></i> {'修改' if st.session_state.get(target_rule_key) else '新增'}规则", unsafe_allow_html=True)
        if st.button("返回列表", key=f"back_list_{related_type}_{related_id}"):
            st.session_state[edit_state_key] = False
            st.rerun()
        
        def _close_editor():
            st.session_state[edit_state_key] = False

        _rule_editor_form_ui(related_type, related_id, rule_id=st.session_state.get(target_rule_key), on_close=_close_editor)
        return

    # 渲染列表模式
    st.markdown(f"### <i class='bi bi-gear-wide-connected'></i> {related_type} 专有规则管理 (ID: {related_id})", unsafe_allow_html=True)
    st.caption("提示：此处仅显示该对象的物理规则实例。继承自父级的规则已物理同步至此列表中。")
    
    session = get_session()
    rules = get_rules_for_entity(session, related_id, related_type, allowed_inherit)
    
    data = []
    for r in rules:
        trigger_p1 = _safe_get(r, 'tge_param1')
        target_p1 = _safe_get(r, 'tae_param1')
        direction = _safe_get(r, 'direction')
        offset = _safe_get(r, 'offset')
        unit = _safe_get(r, 'unit')
        inherit = _safe_get(r, 'inherit')
        
        data.append({
            "ID": _safe_get(r, 'id'),
            "责任方": _safe_get(r, 'party'),
            "触发点": f"{_safe_get(r, 'trigger_event')} ({trigger_p1 if trigger_p1 else ''})",
            "目标点": f"{_safe_get(r, 'target_event')} ({target_p1 if target_p1 else ''})",
            "约束": f"{direction if direction else ''} {offset if offset is not None else ''} {unit if unit else ''}",
            "级别": ["自身", "近", "远"][inherit] if inherit is not None else "自身",
            "状态": _safe_get(r, 'status')
        })
    
    df_key = f"df_rules_{related_type}_{related_id}"
    selected_rule_id = None
    
    if data:
        if df_key in st.session_state:
            sel_state = st.session_state.get(df_key, {})
            if isinstance(sel_state, dict):
                sel_rows = sel_state.get("selection", {}).get("rows", [])
                if sel_rows:
                    selected_rule_id = data[sel_rows[0]]["ID"]
    
    btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 1])
    
    with btn_c1:
        if st.button("添加", key=f"add_rule_{related_type}_{related_id}", type="primary", use_container_width=True):
            st.session_state[edit_state_key] = True
            st.session_state[target_rule_key] = None
            st.rerun()
    
    with btn_c2:
        edit_disabled = selected_rule_id is None
        if st.button("修改", key=f"edit_rule_{related_type}_{related_id}", 
                     disabled=edit_disabled, use_container_width=True):
            st.session_state[edit_state_key] = True
            st.session_state[target_rule_key] = selected_rule_id
            st.rerun()
    
    with btn_c3:
        del_disabled = selected_rule_id is None
        if st.button("删除", key=f"del_rule_{related_type}_{related_id}", 
                     disabled=del_disabled, use_container_width=True):
            result = delete_rule_action(session, selected_rule_id)
            if result.success:
                st.success(result.message)
                st.rerun()
            else:
                st.error(result.error)
    
    if selected_rule_id:
        st.caption(f"已选中规则 ID: {selected_rule_id}")
            
    if not rules:
        st.info("当前暂无订制规则。")
    else:
        df = pd.DataFrame(data)
        st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=df_key
        )


# ========== 草稿规则管理器 (用于实体创建前的规则预定义) ==========

@st.dialog("虚拟合同规则配置", width="large")
def draft_rule_manager_dialog(draft_key: str, target_type: str = "虚拟合同"):
    """
    草稿规则管理弹窗 - 与正式规则管理器交互一致
    """
    trigger_key = f"trigger_draft_rule_mgr_{draft_key}"
    
    c1, c2 = st.columns([4, 1])
    c1.markdown(f"### <i class='bi bi-gear'></i> {target_type}专属规则配置", unsafe_allow_html=True)
    if c2.button("退出管理", key=f"close_draft_mgr_{draft_key}", use_container_width=True):
        if trigger_key in st.session_state:
            del st.session_state[trigger_key]
        st.rerun()
    
    st.caption("此处定义的规则将在提交后自动关联到新创建的合同。")
    show_draft_rule_manager(draft_key, target_type)


def show_draft_rule_manager(draft_key: str, target_type: str = "虚拟合同"):
    """
    草稿规则管理器 - 用于在实体（如 VC）创建前定义规则
    
    Args:
        draft_key: 唯一标识符，用于隔离不同表单的草稿规则 (如 f"proc_{business_id}")
        target_type: 目标实体类型描述，用于 UI 展示
    """
    # 初始化草稿存储
    storage_key = f"draft_rules_{draft_key}"
    if storage_key not in st.session_state:
        st.session_state[storage_key] = []
    
    edit_state_key = f"draft_edit_mode_{draft_key}"
    edit_idx_key = f"draft_edit_idx_{draft_key}"
    
    if st.session_state.get(edit_state_key):
        # 编辑模式
        edit_idx = st.session_state.get(edit_idx_key)
        is_edit = edit_idx is not None
        st.markdown(f"### <i class='bi bi-pencil'></i> {'修改' if is_edit else '新增'}规则 (待关联至新{target_type})", unsafe_allow_html=True)
        
        if st.button("返回列表", key=f"draft_back_{draft_key}"):
            st.session_state[edit_state_key] = False
            st.rerun()
        
        _draft_rule_editor_form_ui(draft_key, target_type, edit_idx)
        return
    
    draft_rules = st.session_state[storage_key]
    
    # 按钮区域
    btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 1])
    
    df_key = f"df_draft_{draft_key}"
    selected_idx = None
    
    # 检查选中状态
    if df_key in st.session_state:
        sel_state = st.session_state.get(df_key, {})
        if isinstance(sel_state, dict):
            sel_rows = sel_state.get("selection", {}).get("rows", [])
            if sel_rows:
                selected_idx = sel_rows[0]
    
    with btn_c1:
        if st.button("添加", key=f"draft_add_{draft_key}", type="primary", use_container_width=True):
            st.session_state[edit_state_key] = True
            st.session_state[edit_idx_key] = None
            st.rerun()
    
    with btn_c2:
        if st.button("修改", key=f"draft_edit_{draft_key}", 
                     disabled=selected_idx is None, use_container_width=True):
            st.session_state[edit_state_key] = True
            st.session_state[edit_idx_key] = selected_idx
            st.rerun()
    
    with btn_c3:
        if st.button("删除", key=f"draft_del_{draft_key}", 
                     disabled=selected_idx is None, use_container_width=True):
            del st.session_state[storage_key][selected_idx]
            st.success("规则已删除")
            st.rerun()
    
    if selected_idx is not None:
        st.caption(f"已选中第 {selected_idx + 1} 条规则")
    
    # 展示列表
    if not draft_rules:
        st.info("当前暂无预定义规则。点击'添加'创建新规则。")
    else:
        data = []
        for i, r in enumerate(draft_rules):
            data.append({
                "序号": i + 1,
                "责任方": r.get("party", ""),
                "触发事件": r.get("trigger_event", ""),
                "偏移": f"{r.get('offset', 0)} {r.get('unit', '')}",
                "方向": r.get("direction", ""),
                "目标事件": r.get("target_event", "")
            })
        st.dataframe(
            pd.DataFrame(data),
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=df_key
        )


def _draft_rule_editor_form_ui(draft_key: str, target_type: str, edit_idx=None):
    """
    草稿规则编辑器表单 UI
    """
    storage_key = f"draft_rules_{draft_key}"
    edit_state_key = f"draft_edit_mode_{draft_key}"
    
    existing = None
    if edit_idx is not None and edit_idx < len(st.session_state[storage_key]):
        existing = st.session_state[storage_key][edit_idx]
    
    # 汇总所有事件类型
    all_events = [EventType.Special.ABSOLUTE_DATE] + \
                 EventType.ContractLevel.ALL_EVENTS + \
                 EventType.VCLevel.ALL_EVENTS + \
                 EventType.LogisticsLevel.ALL_EVENTS
    
    def find_idx(event, lst):
        if not event or not lst: return 0
        if event in lst: return lst.index(event)
        for i, e in enumerate(lst):
            if event in e or e in event: return i
        return 0
    
    with st.form(f"draft_rule_form_{draft_key}"):
        t_col1, t_col2 = st.columns([1, 1])
        
        with t_col1:
            st.markdown("#### <i class='bi bi-flag'></i> 触发事件", unsafe_allow_html=True)
            trigger_event = st.selectbox("触发事件", all_events, 
                                         index=find_idx(_safe_get(existing, "trigger_event"), all_events),
                                         key=f"draft_tge_{draft_key}")
        
        with t_col2:
            st.markdown("#### <i class='bi bi-geo'></i> 目标事件", unsafe_allow_html=True)
            target_event = st.selectbox("目标事件", all_events, 
                                        index=find_idx(_safe_get(existing, "target_event"), all_events),
                                        key=f"draft_tae_{draft_key}")
        
        st.divider()
        existing_party = _safe_get(existing, "party")
        party = c1.selectbox("责任方", [TimeRuleParty.OURSELVES, TimeRuleParty.CUSTOMER, TimeRuleParty.SUPPLIER],
                             index=[TimeRuleParty.OURSELVES, TimeRuleParty.CUSTOMER, TimeRuleParty.SUPPLIER].index(
                                 existing_party) if existing and existing_party in [TimeRuleParty.OURSELVES, TimeRuleParty.CUSTOMER, TimeRuleParty.SUPPLIER] else 0)
        c2.markdown(f"**目标实体**  \n将关联至新建的{target_type}")
        
        st.divider()
        
        # 时间约束
        st.markdown("#### <i class='bi bi-hourglass-split'></i> 时间约束", unsafe_allow_html=True)
        co_col1, co_col2, co_col3 = st.columns(3)
        offset = co_col1.number_input("偏移数值", value=_safe_get(existing, "offset", 0), step=1)
        
        unit_options = [TimeRuleOffsetUnit.NATURAL_DAY, TimeRuleOffsetUnit.WORK_DAY]
        existing_unit = _safe_get(existing, "unit")
        unit = co_col2.selectbox("单位", unit_options,
                                 index=unit_options.index(existing_unit) if existing and existing_unit in unit_options else 0)
        
        direction_map = {"之前": TimeRuleDirection.BEFORE, "之后": TimeRuleDirection.AFTER}
        existing_direction = _safe_get(existing, "direction")
        direction_label = co_col3.selectbox("方向", list(direction_map.keys()),
                                            index=0 if not existing or existing_direction == TimeRuleDirection.BEFORE else 1)
        
        submit = st.form_submit_button("保存规则", type="primary", use_container_width=True)
        
        if submit:
            rule_data = {
                "party": party,
                "trigger_event": trigger_event,
                "target_event": target_event,
                "offset": offset,
                "unit": unit,
                "direction": direction_map[direction_label],
                "inherit": 0,  # 自身定制
                "status": TimeRuleStatus.ACTIVE
            }
            
            if edit_idx is not None and edit_idx < len(st.session_state[storage_key]):
                st.session_state[storage_key][edit_idx] = rule_data
            else:
                st.session_state[storage_key].append(rule_data)
            
            st.session_state[edit_state_key] = False
            st.success("规则已保存！")
            st.rerun()


def persist_draft_rules(session, draft_key: str, related_type: str, related_id: int):
    """
    将草稿规则持久化到数据库 (调用 Logic Action)
    """
    storage_key = f"draft_rules_{draft_key}"
    draft_rules = st.session_state.get(storage_key, [])
    
    if not draft_rules:
        return 0
        
    result = persist_draft_rules_action(session, draft_rules, related_type, related_id)
    if not result.success:
        st.error(f"持久化规则失败: {result.error}")
        return 0
    
    # 清理草稿
    if storage_key in st.session_state:
        del st.session_state[storage_key]
    
    # 清理编辑状态
    for k in list(st.session_state.keys()):
        if k.startswith(f"draft_") and draft_key in k:
            del st.session_state[k]
    
    return len(draft_rules)


def get_draft_rules_count(draft_key: str) -> int:
    """获取草稿规则数量"""
    storage_key = f"draft_rules_{draft_key}"
    return len(st.session_state.get(storage_key, []))
