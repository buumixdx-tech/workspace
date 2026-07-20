from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from api.deps import get_db, verify_token, api_success
from logic.api_queries import list_partner_relations
from logic.master.actions import create_partner_relation_action, delete_partner_relations_action
from logic.master.schemas import PartnerRelationSchema, DeleteMasterDataSchema

router = APIRouter(prefix="/api/v1/partner-relations", tags=["合作方关系"], dependencies=[Depends(verify_token)])


@router.post("/create", summary="创建合作方关系")
def create_partner_relation(payload: PartnerRelationSchema, session: Session = Depends(get_db)):
    return create_partner_relation_action(session, payload).model_dump()


@router.delete("/delete", summary="批量删除合作方关系")
def delete_partner_relations(payloads: list[DeleteMasterDataSchema], session: Session = Depends(get_db)):
    return delete_partner_relations_action(session, payloads).model_dump()


@router.get("/list", summary="合作方关系列表")
def get_partner_relations_list(
    partner_id: Optional[int] = None,
    owner_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    relation_type: Optional[str] = None,
    session: Session = Depends(get_db)
):
    """
    合作方关系列表查询
    - partner_id: 合作方ID
    - owner_type: 所有者类型 (business/supply_chain/ourselves)
    - owner_id: 所有者ID
    - relation_type: 合作模式
    """
    result = list_partner_relations(session, partner_id=partner_id, owner_type=owner_type,
                                     owner_id=owner_id, relation_type=relation_type)
    return api_success(result)
