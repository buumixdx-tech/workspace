from models import get_session, VirtualContract, EquipmentInventory, CashFlow
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime
from logic.constants import VCType, OperationalStatus, VCStatus, SubjectStatus, CashStatus, CashFlowType, EPSILON
import logging

logger = logging.getLogger(__name__)

def deposit_module(vc_id=None, cf_id=None, session=None):
    ext_session = session is not None
    if not ext_session:
        session = get_session()
    try:
        if cf_id:
            process_cf_deposit(session, cf_id)
        elif vc_id:
            process_vc_deposit(session, vc_id)
        
        if not ext_session:
            session.commit()
    finally:
        if not ext_session:
            session.close()

def process_cf_deposit(session, cf_id):
    cf = session.query(CashFlow).filter(CashFlow.id == cf_id).first()
    if not cf or cf.type not in [CashFlowType.DEPOSIT, CashFlowType.RETURN_DEPOSIT]:
        return
    
    vc = session.query(VirtualContract).filter(VirtualContract.id == cf.virtual_contract_id).first()
    if not vc: return
    
    # --- 核心深度逻辑：退货押金重定向 ---
    # 如果当前流水属于“退货”单，则其对应的押金变动应作用于“原采购合同”
    target_vc = vc
    if vc.type == VCType.RETURN and vc.related_vc_id:
        original_vc = session.query(VirtualContract).get(vc.related_vc_id)
        if original_vc:
            target_vc = original_vc
            logger.debug(f"Redirecting deposit adjustment from Return VC {vc.id} to Original VC {target_vc.id}")

    # 调整押金总额
    deposit_info = dict(target_vc.deposit_info) if target_vc.deposit_info else {}
    current_total = deposit_info.get('total_deposit', 0.0)
    
    if cf.type == CashFlowType.DEPOSIT:
        current_total += cf.amount
    else:
        # 退还押金 -> 减少总额
        current_total -= cf.amount
    
    deposit_info['total_deposit'] = current_total
    deposit_info['last_cf_id'] = cf.id
    target_vc.deposit_info = deposit_info
    
    # 显式标记 JSON 字段已修改
    flag_modified(target_vc, "deposit_info")
    session.flush() # 先刷入数据库，保证后续查询能查到最新状态
    
    # 触发均摊逻辑
    process_vc_deposit(session, target_vc.id)

def process_vc_deposit(session, vc_id):
    vc = session.query(VirtualContract).filter(VirtualContract.id == vc_id).first()
    if not vc: return
    
    deposit_info = dict(vc.deposit_info) if vc.deposit_info else {}
    elements = vc.elements or {}
    
    # --- 1. 动态重新核算应收押金金额 (should_receive) ---
    # 根据用户规则：应收金额 = 还在运营状态的设备数量 * 业务约定单台押金
    new_should_receive = 0.0
    
    if vc.type in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT]:
        items = elements.get("items") or []
        if not items:
            return

        # 建立 SKU 与约定押金的映射（确保 ID 为整数类型）
        sku_to_dep = {}
        for item in items:
            sid = item.get("sku_id")
            if sid:
                sku_to_dep[int(sid)] = float(item.get("deposit", 0.0))

        logger.debug(f"deposit: VC {vc_id} sku_to_dep = {sku_to_dep}")

        # 统计是否已经产生过实物档案（发货后的）
        inv_exists = session.query(EquipmentInventory).filter(EquipmentInventory.virtual_contract_id == vc_id).first() is not None
        logger.debug(f"deposit: VC {vc_id} inv_exists = {inv_exists}")

        if inv_exists:
            # 方案 A: 基于实物库存（处理后期退货变动）
            for sid, target_dep in sku_to_dep.items():
                count = session.query(EquipmentInventory).filter(
                    EquipmentInventory.virtual_contract_id == vc_id,
                    EquipmentInventory.sku_id == sid,
                    EquipmentInventory.operational_status == OperationalStatus.OPERATING
                ).count()
                logger.debug(f"deposit: SKU {sid} count={count} dep={target_dep}")
                new_should_receive += count * target_dep
        else:
            # 方案 B: 基于初始合同计划（处理刚创建尚未发货阶段）
            for item in items:
                new_should_receive += float(item.get("qty", 0)) * float(item.get("deposit", 0.0))
        
        logger.debug(f"deposit: VC {vc_id} new_should_receive = {new_should_receive}")
        
        # 更新 should_receive
        deposit_info["should_receive"] = new_should_receive
        vc.deposit_info = deposit_info
        flag_modified(vc, "deposit_info")
        session.flush()

    # --- 核心状态检查与自动完结逻辑 ---
    # 提前计算当前押金收支平衡状态，供后文使用
    all_cash = session.query(CashFlow).filter(CashFlow.virtual_contract_id == vc_id).all()
    paid_goods = sum(cf.amount for cf in all_cash if cf.type in [CashFlowType.PREPAYMENT, CashFlowType.FULFILLMENT, CashFlowType.REFUND, CashFlowType.OFFSET_PAY])
    paid_deposit = sum(cf.amount for cf in all_cash if cf.type == CashFlowType.DEPOSIT)
    
    # 查找关联退货 VC 的退押金
    related_return_vcs = session.query(VirtualContract).filter(
        VirtualContract.related_vc_id == vc_id
    ).all()
    paid_return_deposit = sum(cf.amount for cf in all_cash if cf.type == CashFlowType.RETURN_DEPOSIT)
    for ret_vc in related_return_vcs:
        ret_cfs = session.query(CashFlow).filter(
            CashFlow.virtual_contract_id == ret_vc.id,
            CashFlow.type == CashFlowType.RETURN_DEPOSIT
        ).all()
        paid_return_deposit += sum(cf.amount for cf in ret_cfs)
    
    # 最终计算
    actual_net_deposit = paid_deposit - paid_return_deposit
    total_due = elements.get('total_amount', 0.0)
    dep_due = new_should_receive
    
    is_goods_cleared = (paid_goods >= (total_due - EPSILON))
    is_deposit_cleared = (dep_due <= 0 or actual_net_deposit >= (dep_due - EPSILON))

    # --- 特殊处理：客户押金未付足时，自动完结不需要退押金的退货 VC ---
    if actual_net_deposit <= (dep_due + EPSILON):
        for ret_vc in related_return_vcs:
            if (ret_vc.status == VCStatus.EXE and 
                ret_vc.cash_status == CashStatus.EXE and 
                ret_vc.subject_status == SubjectStatus.FINISH):
                
                ret_cf_count = session.query(CashFlow).filter(
                    CashFlow.virtual_contract_id == ret_vc.id
                ).count()
                
                if ret_cf_count == 0:
                    ret_vc.update_cash_status(CashStatus.FINISH)
                    ret_vc.update_status(VCStatus.FINISH)
                    logger.debug(f"Return VC {ret_vc.id} auto-completed (no deposit refund needed)")
    
    if is_goods_cleared and is_deposit_cleared and vc.cash_status != CashStatus.FINISH:
        vc.update_cash_status(CashStatus.FINISH)
        logger.debug(f"VC {vc_id} cash_status updated to FINISH")
        
        # 调用状态机处理后续状态同步
        from logic.state_machine import check_vc_overall_status
        check_vc_overall_status(vc, session)

    # --- 2. 按 SKU 约定押金比例分摊实收押金 ---
    total_deposit = actual_net_deposit
    should_receive = dep_due
    
    # 获取名下所有在运营状态的设备
    inventories = session.query(EquipmentInventory).filter(
        EquipmentInventory.virtual_contract_id == vc_id,
        EquipmentInventory.operational_status == OperationalStatus.OPERATING
    ).all()
    
    if not inventories:
        # 如果没有运营设备了，不分摊
        return
    
    # 获取 SKU 与约定押金的映射
    sku_to_agreed_deposit = {}
    if vc.type in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT]:
        items = elements.get("items") or []
        for item in items:
            sid = item.get("sku_id")
            if sid:
                sku_to_agreed_deposit[sid] = float(item.get("deposit", 0.0))
    
    # 计算分摊比例（实收/应收）
    # 如果应收为0或负数，则比例为0（无需分摊）
    ratio = (total_deposit / should_receive) if should_receive > EPSILON else 0.0
    
    # 按 SKU 约定押金 × 比例 分摊到每台设备
    for inv in inventories:
        agreed_deposit = sku_to_agreed_deposit.get(inv.sku_id, 0.0)
        inv.deposit_amount = agreed_deposit * ratio
        inv.deposit_timestamp = datetime.now()
    
    logger.debug(f"VC {vc_id} proportionally distributed deposit (ratio={ratio:.4f}, total={total_deposit}, should={should_receive})")

