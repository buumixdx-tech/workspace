from sqlalchemy.orm import Session
from models import Supplier, SupplyChain, SupplyChainItem
from .schemas import CreateSupplyChainSchema, DeleteSupplyChainSchema, UpdateSupplyChainSchema
from logic.base import ActionResult
from logic.events.dispatcher import emit_event
from logic.constants import SystemEventType, SystemAggregateType, TimeRuleRelatedType
from logic.time_rules.rule_manager import RuleManager
from datetime import datetime


def _sync_supply_chain_items(session: Session, sc: SupplyChain, items_data: list):
    """全量同步 SupplyChainItem 记录：先删后插（利用 cascade）"""
    sc.items.clear()
    session.flush()
    for item in items_data:
        sci = SupplyChainItem(
            supply_chain_id=sc.id,
            sku_id=item.sku_id,
            price=item.price,
            is_floating=item.is_floating
        )
        session.add(sci)


def create_supply_chain_action(session: Session, payload: CreateSupplyChainSchema, template_rules: list = None) -> ActionResult:
    """创建或更新供应链协议 Action"""
    try:
        s = session.query(Supplier).get(payload.supplier_id)
        if not s: return ActionResult(success=False, error="未找到供应商")

        existing_sc = session.query(SupplyChain).filter(
            SupplyChain.supplier_id == payload.supplier_id,
            SupplyChain.type == payload.type
        ).first()

        c_num = payload.contract_num or f"SC-{payload.supplier_id}-{payload.type}-{datetime.now().strftime('%Y%m%d')}"

        if existing_sc:
            existing_sc.payment_terms = payload.payment_terms
            _sync_supply_chain_items(session, existing_sc, payload.items)
            sc_id = existing_sc.id
            msg = f"已更新供应商 {payload.supplier_name} 的 {payload.type} 协议"
            emit_event(session, SystemEventType.SUPPLY_CHAIN_UPDATED, SystemAggregateType.SUPPLY_CHAIN, sc_id, {
                "supplier_id": payload.supplier_id, "type": payload.type
            })
        else:
            new_sc = SupplyChain(
                supplier_id=payload.supplier_id,
                type=payload.type,
                payment_terms=payload.payment_terms
            )
            session.add(new_sc)
            session.flush()
            _sync_supply_chain_items(session, new_sc, payload.items)
            sc_id = new_sc.id
            msg = f"已为供应商 {payload.supplier_name} 创建新的 {payload.type} 协议"
            emit_event(session, SystemEventType.SUPPLY_CHAIN_CREATED, SystemAggregateType.SUPPLY_CHAIN, sc_id, {
                "supplier_id": payload.supplier_id, "type": payload.type
            })

        # 生成付款条款时间规则
        if payload.payment_terms:
            RuleManager(session).generate_rules_from_payment_terms(
                related_id=sc_id,
                related_type=TimeRuleRelatedType.SUPPLY_CHAIN,
                payment_terms=payload.payment_terms,
                entity_type=TimeRuleRelatedType.SUPPLY_CHAIN
            )

        # 保存初始模板规则
        if template_rules:
            RuleManager(session).save_template_rules(
                related_id=sc_id,
                related_type=TimeRuleRelatedType.SUPPLY_CHAIN,
                rules=template_rules
            )

        session.commit()
        return ActionResult(success=True, data={"sc_id": sc_id}, message=msg)
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))


def delete_supply_chain_action(session: Session, payload: DeleteSupplyChainSchema) -> ActionResult:
    """物理删除供应链协议 Action"""
    try:
        sc = session.query(SupplyChain).get(payload.id)
        if not sc: return ActionResult(success=False, error="协议不存在")

        from models import VirtualContract
        if session.query(VirtualContract).filter(VirtualContract.supply_chain_id == sc.id).count() > 0:
            return ActionResult(success=False, error="该协议已有对应合同执行，无法删除")

        session.delete(sc)
        emit_event(session, SystemEventType.SUPPLY_CHAIN_DELETED, SystemAggregateType.SUPPLY_CHAIN, sc.id)
        session.commit()
        return ActionResult(success=True, message="供应链协议已删除")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))


def update_supply_chain_action(session: Session, payload: UpdateSupplyChainSchema) -> ActionResult:
    """更新供应链协议 Action"""
    try:
        sc = session.query(SupplyChain).get(payload.id)
        if not sc: return ActionResult(success=False, error="协议不存在")

        sc.type = payload.type
        sc.payment_terms = payload.payment_terms
        _sync_supply_chain_items(session, sc, payload.items)

        # 更新付款条款时间规则
        if payload.payment_terms:
            RuleManager(session).generate_rules_from_payment_terms(
                related_id=sc.id,
                related_type=TimeRuleRelatedType.SUPPLY_CHAIN,
                payment_terms=payload.payment_terms,
                entity_type=TimeRuleRelatedType.SUPPLY_CHAIN
            )

        emit_event(session, SystemEventType.SUPPLY_CHAIN_UPDATED, SystemAggregateType.SUPPLY_CHAIN, sc.id, {
            "supplier_id": sc.supplier_id, "type": sc.type
        })
        session.commit()
        return ActionResult(success=True, data={"sc_id": sc.id}, message=f"已更新供应商 {payload.supplier_name} 的 {payload.type} 协议")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))
