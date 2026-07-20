"""mycloud_proxy: HTTP 只读代理 mycloud.db records 表.

部署位置: jcloud /opt/mycloud_proxy/mycloud_proxy.py
启动: nohup python3 -m uvicorn mycloud_proxy:app --host 127.0.0.1 --port 9623 &

设计: 仿 feishu messages_proxy (FastAPI 0.115), 单进程 1 端口.
- /health: 健康检查 + 当前数据规模
- /sync/records/incremental: 增量同步 (since_id + category + types 过滤)

安全: 不直连外网, 由 nginx 反代到 /mycloud-api/ 加 htpasswd 认证.

Dependencies (jcloud):
  pip install fastapi==0.115.* uvicorn==0.30.*
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException

MYCLOUD_DB_PATH = "/opt/mycloud/mycloud.db"

app = FastAPI(title="mycloud_proxy", version="1.0.0")


@app.get("/health")
def health():
    """健康检查 + 当前数据规模.

    Returns:
      {
        "ok": True,
        "total_records": int,         # records 总数 (含所有 type/category)
        "stock_text_md_count": int,  # category='stock' AND type IN ('text','md') 的条数
        "max_id": int,               # records.id 当前最大值
      }
    """
    con = sqlite3.connect(MYCLOUD_DB_PATH, timeout=10)
    try:
        total = con.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        max_id = con.execute("SELECT COALESCE(MAX(id), 0) FROM records").fetchone()[0]
        stock_cnt = con.execute(
            "SELECT COUNT(*) FROM records WHERE category='stock' AND type IN ('text','md')"
        ).fetchone()[0]
    finally:
        con.close()
    return {
        "ok": True,
        "total_records": total,
        "stock_text_md_count": stock_cnt,
        "max_id": max_id,
    }


@app.get("/sync/records/incremental")
def incremental(since_id: int = 0, limit: int = 5000,
                category: str = "stock",
                types: str = "text,md"):
    """增量同步 mycloud.records, 服务端做 category + type 过滤.

    Query params:
      since_id:  本地 preprocess 已同步的最大 rowid (默认 0 = 全量拉)
      limit:     最多返回多少行, 默认 5000, 硬上限 50000
      category:  默认 'stock' (mycloud 95% 都是 stock)
      types:     逗号分隔, 默认 'text,md'

    Returns:
      {
        "rows": [
          {
            "id": int,           # records.id (= rowid)
            "ts": int,           # unix ms (从 'YYYY-MM-DD HH:MM:SS' 转换, Asia/Shanghai)
            "kind": "t",         # 固定, 跟 feishu 共用下游
            "content": str,      # 原文
            "type": "text"|"md", # 原始类型
            "title": str|null,   # 标题 (当前都为空)
            "category": "stock", # 类目
          },
          ...
        ],
        "max_id_in_batch": int,
        "returned": int,
      }
    """
    if limit > 50000:
        raise HTTPException(400, "limit too large (max 50000)")
    type_list = [t.strip() for t in types.split(",") if t.strip()]
    if not type_list:
        raise HTTPException(400, "types empty")

    con = sqlite3.connect(MYCLOUD_DB_PATH, timeout=30)
    try:
        placeholders = ",".join("?" * len(type_list))
        rows = con.execute(
            f"SELECT id, created_at, type, category, title, content "
            f"FROM records WHERE id > ? AND category = ? AND type IN ({placeholders}) "
            f"ORDER BY id ASC LIMIT ?",
            (since_id, category, *type_list, limit),
        ).fetchall()
    finally:
        con.close()

    tz_sh = timezone(timedelta(hours=8))
    out = []
    for rowid, created_at, rtype, rcat, title, content in rows:
        if not created_at:
            continue
        try:
            dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        ts_ms = int(dt.replace(tzinfo=tz_sh).timestamp() * 1000)
        out.append({
            "id": int(rowid),
            "ts": ts_ms,
            "kind": "t",
            "content": content or "",
            "type": rtype,
            "title": title,
            "category": rcat,
        })

    return {
        "rows": out,
        "max_id_in_batch": out[-1]["id"] if out else since_id,
        "returned": len(out),
    }


# uvicorn 入口: uvicorn mycloud_proxy:app --host 127.0.0.1 --port 9623
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9623)