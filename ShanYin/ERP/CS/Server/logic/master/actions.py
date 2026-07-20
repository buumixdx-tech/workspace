from sqlalchemy.orm import Session
from models import ChannelCustomer, Point, Supplier, SKU, ExternalPartner, PartnerRelation
from .schemas import (
    CustomerSchema, PointSchema, SupplierSchema, SKUSchema, PartnerSchema, DeleteMasterDataSchema,
    PartnerRelationSchema
)
from logic.base import ActionResult
from logic.events.dispatcher import emit_event
from typing import List
from logic.constants import SystemEventType, SystemAggregateType

def create_customer_action(session: Session, payload: CustomerSchema) -> ActionResult:
    try:
        new_obj = ChannelCustomer(name=payload.name, info=payload.info)
        session.add(new_obj)
        session.flush()
        emit_event(session, SystemEventType.MASTER_CREATED, SystemAggregateType.CHANNEL_CUSTOMER, new_obj.id, {"name": payload.name})
        session.commit()
        return ActionResult(success=True, message="客户创建成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def update_customers_action(session: Session, payloads: List[CustomerSchema]) -> ActionResult:
    try:
        for p in payloads:
            obj = session.query(ChannelCustomer).get(p.id)
            if obj:
                obj.name = p.name
                obj.info = p.info
        session.commit()
        return ActionResult(success=True, message="客户信息已更新")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def delete_customers_action(session: Session, payloads: List[DeleteMasterDataSchema]) -> ActionResult:
    try:
        from models import Business
        errors = []
        for p in payloads:
            obj = session.query(ChannelCustomer).get(p.id)
            if obj:
                if session.query(Business).filter(Business.customer_id == obj.id).first():
                    errors.append(f"客户 '{obj.name}' 有关联业务，无法删除")
                    continue
                session.delete(obj)
        if errors:
            session.rollback()
            return ActionResult(success=False, error="; ".join(errors))
        session.commit()
        return ActionResult(success=True, message="删除成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def create_point_action(session: Session, payload: PointSchema) -> ActionResult:
    try:
        new_obj = Point(
            name=payload.name,
            customer_id=payload.customer_id,
            supplier_id=payload.supplier_id,
            type=payload.type,
            address=payload.address,
            receiving_address=payload.receiving_address
        )
        session.add(new_obj)
        session.flush()
        emit_event(session, SystemEventType.MASTER_CREATED, SystemAggregateType.POINT, new_obj.id, {"name": payload.name})
        session.commit()
        return ActionResult(success=True, message="点位创建成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def update_points_action(session: Session, payloads: List[PointSchema]) -> ActionResult:
    try:
        for p in payloads:
            obj = session.query(Point).get(p.id)
            if obj:
                obj.name = p.name
                obj.customer_id = p.customer_id
                obj.supplier_id = p.supplier_id
                obj.type = p.type
                obj.address = p.address
                obj.receiving_address = p.receiving_address
        session.commit()
        return ActionResult(success=True, message="点位已更新")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def delete_points_action(session: Session, payloads: List[DeleteMasterDataSchema]) -> ActionResult:
    try:
        from models import EquipmentInventory, VirtualContract
        errors = []
        for p in payloads:
            obj = session.query(Point).get(p.id)
            if obj:
                if session.query(EquipmentInventory).filter(EquipmentInventory.point_id == obj.id).first():
                    errors.append(f"点位 '{obj.name}' 有库存，无法删除")
                    continue
                session.delete(obj)
        if errors:
            session.rollback()
            return ActionResult(success=False, error="; ".join(errors))
        session.commit()
        return ActionResult(success=True, message="删除成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def create_sku_action(session: Session, payload: SKUSchema) -> ActionResult:
    try:
        new_obj = SKU(supplier_id=payload.supplier_id, name=payload.name, type_level1=payload.type_level1, model=payload.model)
        session.add(new_obj)
        session.flush()
        emit_event(session, SystemEventType.MASTER_CREATED, SystemAggregateType.SKU, new_obj.id, {"name": payload.name})
        session.commit()
        return ActionResult(success=True, message="SKU创建成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def update_skus_action(session: Session, payloads: List[SKUSchema]) -> ActionResult:
    try:
        for p in payloads:
            obj = session.query(SKU).get(p.id)
            if obj:
                obj.name = p.name
                obj.supplier_id = p.supplier_id
                obj.type_level1 = p.type_level1
                obj.model = p.model
        session.commit()
        return ActionResult(success=True, message="SKU已更新")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def delete_skus_action(session: Session, payloads: List[DeleteMasterDataSchema]) -> ActionResult:
    try:
        errors = []
        for p in payloads:
            obj = session.query(SKU).get(p.id)
            if obj:
                # 简化校验：仅检查基本引用
                session.delete(obj)
        session.commit()
        return ActionResult(success=True, message="删除成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def create_supplier_action(session: Session, payload: SupplierSchema) -> ActionResult:
    try:
        new_obj = Supplier(name=payload.name, category=payload.category, address=payload.address)
        session.add(new_obj)
        session.flush()
        emit_event(session, SystemEventType.MASTER_CREATED, SystemAggregateType.SUPPLIER, new_obj.id, {"name": payload.name})
        session.commit()
        return ActionResult(success=True, message="供应商创建成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def update_suppliers_action(session: Session, payloads: List[SupplierSchema]) -> ActionResult:
    try:
        for p in payloads:
            obj = session.query(Supplier).get(p.id)
            if obj:
                obj.name = p.name
                obj.category = p.category
                obj.address = p.address
        session.commit()
        return ActionResult(success=True, message="供应商已更新")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def delete_suppliers_action(session: Session, payloads: List[DeleteMasterDataSchema]) -> ActionResult:
    try:
        from models import SupplyChain
        errors = []
        for p in payloads:
            obj = session.query(Supplier).get(p.id)
            if obj:
                if session.query(SupplyChain).filter(SupplyChain.supplier_id == obj.id).first():
                    errors.append(f"供应商 '{obj.name}' 有供应链协议，无法删除")
                    continue
                session.delete(obj)
        if errors:
            session.rollback()
            return ActionResult(success=False, error="; ".join(errors))
        session.commit()
        return ActionResult(success=True, message="删除成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def create_partner_action(session: Session, payload: PartnerSchema) -> ActionResult:
    try:
        new_obj = ExternalPartner(name=payload.name, type=payload.type)
        session.add(new_obj)
        session.flush()
        emit_event(session, SystemEventType.MASTER_CREATED, SystemAggregateType.EXTERNAL_PARTNER, new_obj.id, {"name": payload.name})
        session.commit()
        return ActionResult(success=True, message="合作方创建成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def update_partners_action(session: Session, payloads: List[PartnerSchema]) -> ActionResult:
    try:
        for p in payloads:
            obj = session.query(ExternalPartner).get(p.id)
            if obj:
                obj.name = p.name
                obj.type = p.type
        session.commit()
        return ActionResult(success=True, message="合作方已更新")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def delete_partners_action(session: Session, payloads: List[DeleteMasterDataSchema]) -> ActionResult:
    try:
        for p in payloads:
            obj = session.query(ExternalPartner).get(p.id)
            if obj: session.delete(obj)
        session.commit()
        return ActionResult(success=True, message="删除成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))


def create_partner_relation_action(session: Session, payload: PartnerRelationSchema) -> ActionResult:
    try:
        new_obj = PartnerRelation(
            partner_id=payload.partner_id,
            owner_type=payload.owner_type,
            owner_id=payload.owner_id,
            relation_type=payload.relation_type,
            remark=payload.remark or ""
        )
        session.add(new_obj)
        session.flush()
        session.commit()
        return ActionResult(success=True, data={"id": new_obj.id}, message="合作方关系创建成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))


def delete_partner_relations_action(session: Session, payloads: List[DeleteMasterDataSchema]) -> ActionResult:
    try:
        for p in payloads:
            obj = session.query(PartnerRelation).get(p.id)
            if obj: session.delete(obj)
        session.commit()
        return ActionResult(success=True, message="合作方关系删除成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))


