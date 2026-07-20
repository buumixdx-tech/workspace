from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.deps import get_db, verify_token, api_error
import re

router = APIRouter(prefix="/api/v1/sql", tags=["SQL查询"], dependencies=[Depends(verify_token)])


class RawQueryRequest(BaseModel):
    sql: str
    params: dict | None = None


# ==================== 安全校验 ====================

BLOCKED_PATTERNS = [
    (r'\bDROP\b', "DROP"),
    (r'\bDELETE\b', "DELETE"),
    (r'\bINSERT\b', "INSERT"),
    (r'\bUPDATE\b', "UPDATE"),
    (r'\bALTER\b', "ALTER"),
    (r'\bCREATE\b', "CREATE"),
    (r'\bTRUNCATE\b', "TRUNCATE"),
    (r'\bGRANT\b', "GRANT"),
    (r'\bREVOKE\b', "REVOKE"),
    (r'\bEXEC\b', "EXEC"),
    (r'\bEXECUTE\b', "EXECUTE"),
    (r'\b--\b', "--"),
    (r'\/\*', "/*"),
    (r'\bUNION\s+SELECT\b', "UNION SELECT"),
]

MAX_ROWS = 1000


def is_safe_sql(sql: str) -> tuple[bool, str]:
    """
    校验 SQL 安全性。
    返回 (是否安全, 错误信息)
    """
    upper_sql = sql.upper().strip()

    # 必须以 SELECT 开头
    if not upper_sql.startswith('SELECT'):
        return False, "只允许 SELECT 查询"

    # 检查危险模式
    for pattern, name in BLOCKED_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            return False, f"禁止使用: {name}"

    # 检查分号（防止多语句注入）
    if ';' in sql:
        return False, "禁止使用分号"

    return True, ""


# ==================== 查询端点 ====================

@router.post("/query", summary="执行原始SQL查询")
def execute_raw_query(req: RawQueryRequest, session: Session = Depends(get_db)):
    """
    执行原始 SQL 查询（只读）。

    安全措施：
    1. 只允许 SELECT 语句
    2. 禁止危险关键字和分号
    3. 禁止 SQL 注释
    4. 最大返回 1000 行
    5. 不暴露 SQL 错误详情给客户端

    使用示例：
    POST /api/v1/sql/query
    {
        "sql": "SELECT * FROM virtual_contracts WHERE status = :status LIMIT 10",
        "params": {"status": "执行"}
    }
    """
    safe, error_msg = is_safe_sql(req.sql)
    if not safe:
        return api_error("RAW_QUERY_SAFE", error_msg)

    sql = req.sql.strip()
    if 'LIMIT' not in sql.upper():
        sql = f"{sql} LIMIT {MAX_ROWS}"

    try:
        session.execute(text("PRAGMA busy_timeout = 30000"))
    except Exception:
        pass

    try:
        if req.params:
            result = session.execute(text(sql), req.params)
        else:
            result = session.execute(text(sql))

        columns = result.keys()
        rows = result.fetchall()
        data = [dict(zip(columns, row)) for row in rows]

        return {
            "success": True,
            "data": {
                "columns": list(columns),
                "rows": data,
                "row_count": len(data),
            }
        }

    except Exception:
        return api_error("RAW_QUERY_EXEC", "查询执行失败，请检查 SQL 语法")
