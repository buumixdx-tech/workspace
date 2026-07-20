from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from api.deps import get_db, verify_api_key, api_success, parse_ids
from api.middleware.error_handler import raise_not_found_error
from logic.api_queries import list_rules, get_rule
from logic.time_rules import (
    save_rule_action, delete_rule_action,
    TimeRuleSchema
)

router = APIRouter(prefix="/api/v1/rules", tags=["时间规则"], dependencies=[Depends(verify_api_key)])


@router.post("/save", summary="保存/更新时间规则")
def save_rule(payload: TimeRuleSchema, session: Session = Depends(get_db)):
    return save_rule_action(session, payload).model_dump()


@router.delete("/delete", summary="删除时间规则")
def delete_rule(rule_id: int, session: Session = Depends(get_db)):
    return delete_rule_action(session, rule_id).model_dump()


# ==================== Query Endpoints ====================

@router.get("/list", summary="时间规则列表")
def get_rules(
    ids: Optional[str] = None,
    related_id: Optional[int] = None,
    related_type: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    result = list_rules(session, ids=id_list, related_id=related_id, related_type=related_type,
                        status=status, date_from=date_from, date_to=date_to, page=page, size=size)
    return api_success(result)


@router.get("/{rule_id}", summary="时间规则详情")
def get_rule_detail(rule_id: int, session: Session = Depends(get_db)):
    data = get_rule(session, rule_id)
    if data is None:
        raise_not_found_error("时间规则", str(rule_id))
    return api_success(data)
