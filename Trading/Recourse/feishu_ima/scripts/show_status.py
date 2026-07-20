"""show_status.py - 读 feishu_to_ima.db 当前水位, 不跑 pipeline.

不依赖 aiohttp, 纯 sqlite, 立刻给数字:
  - watermark (last_ts, last_msg_id, bucket_seq)
  - txt_bucket rows + pending
  - uploaded msg_ids count
  - 上游 extracted 分布 + 应上传数 (扣 SKIP) - 跟踪数 = 进度
  - heartbeat 状态

Exit codes:
  0 = OK
  2 = db 不存在
"""
import sqlite3
import sys
from pathlib import Path

# 复用 db_writer 的 SKIP 规则 (env FEISHU_TO_IMA_SKIP_TYPES 可覆盖), 不再硬编码
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from feishu_to_ima_db_writer import SKIP_TYPE_CODES

IMA_DB = Path(r"D:\WorkSpace\Trading\Recourse\feishu_ima\data\feishu_to_ima.db")
PREP_DB = Path(r"D:\WorkSpace\Trading\Recourse\feishu_ext\data\preprocess.db")

if not IMA_DB.exists():
    print(f"[ERROR] db 不存在: {IMA_DB}")
    sys.exit(2)
if not PREP_DB.exists():
    print(f"[ERROR] 上游 db 不存在: {PREP_DB}")
    sys.exit(2)

con = sqlite3.connect(str(IMA_DB))
con.execute("ATTACH DATABASE ? AS feishu_src", (str(PREP_DB),))

print("== fsima 状态快照 ==")
print(f"  db: {IMA_DB}")
print(f"  上游: {PREP_DB}")
print()

# 水位
row = con.execute(
    "SELECT last_ts, last_msg_id, bucket_seq, last_post_track, "
    "datetime(updated_at, '+8 hours') FROM bucket_state"
).fetchone()
print(f"watermark:        ({row[0]}, {row[1]})")
print(f"bucket_seq:       {row[2]}")
print(f"last_post_track:  {row[3]}")
print(f"updated_at:       {row[4]} (Asia/Shanghai)")
print()

# txt_bucket
total, pending, oldest, newest = con.execute(
    "SELECT COUNT(*), "
    "SUM(CASE WHEN posted_at IS NULL OR posted_at='' THEN 1 ELSE 0 END), "
    "MIN(created_at), MAX(created_at) FROM txt_bucket"
).fetchone()
print(f"txt_bucket:       {total} 个文件 (pending: {pending or 0})")
print(f"  最早: {oldest}")
print(f"  最新: {newest}")
print()

# 上传统计 — v3 local + v2 backup 双源 union
# 2026-07-13 fix: v2 时代 (2026-06-22 前) 也在 IMA KB 里有 10k+ msg_ids,本地 db 不记得;
# 仅看 local 把它们算成 "未传" 会让 dashboard 看起来始终落后. 实际覆盖率需 union v2 history.
import json as _json

local_uploaded_ids: set[int] = set()
for r in con.execute(
    "SELECT msg_ids_json FROM txt_bucket "
    "WHERE posted_at IS NOT NULL AND posted_at != ''"
):
    try:
        local_uploaded_ids.update(_json.loads(r[0]))
    except _json.JSONDecodeError:
        pass

# 探测 v2-era backup db (data/feishu_to_ima.db.bak*),优先选 txt_bucket 行最多的
v2_uploaded_ids: set[int] = set()
v2_source: str | None = None
_bak_pool = sorted(IMA_DB.parent.glob("feishu_to_ima.db.bak*"))
_best_n, _best_bf = -1, None
for _bf in _bak_pool:
    try:
        _bcon = sqlite3.connect(f"file:{_bf}?mode=ro", uri=True)
        try:
            _n = _bcon.execute("SELECT COUNT(*) FROM txt_bucket").fetchone()[0]
            if _n > _best_n:
                _best_n, _best_bf = _n, _bf
        finally:
            _bcon.close()
    except sqlite3.DatabaseError:
        continue
if _best_bf is not None:
    _bcon = sqlite3.connect(f"file:{_best_bf}?mode=ro", uri=True)
    v2_source = _best_bf.name
    for r in _bcon.execute("SELECT msg_ids_json FROM txt_bucket WHERE msg_ids_json IS NOT NULL"):
        try:
            v2_uploaded_ids.update(_json.loads(r[0]))
        except _json.JSONDecodeError:
            pass
    _bcon.close()

ima_msg_ids: set[int] = local_uploaded_ids | v2_uploaded_ids

print(f"uploaded msg_ids (v3 local tracked): {len(local_uploaded_ids)}")
if v2_source:
    print(f"v2 history (source={v2_source}): {len(v2_uploaded_ids)}")
print(f"IMA 端累计 (local ∪ v2): {len(ima_msg_ids)}")
print()

# 上游
total_ext = con.execute("SELECT COUNT(*) FROM feishu_src.extracted").fetchone()[0]
print("== 上游 feishu_src.extracted ==")
keep_ids: set[int] = set(
    int(r[0]) for r in con.execute(
        f"SELECT msg_id FROM feishu_src.extracted "
        f"WHERE info_type NOT IN ({','.join('?' * len(sorted(SKIP_TYPE_CODES)))})",
        sorted(SKIP_TYPE_CODES),
    )
)
should_upload = len(keep_ids)
print("  info_type 分布:")
for code, count in con.execute(
    "SELECT info_type, COUNT(*) FROM feishu_src.extracted GROUP BY info_type ORDER BY info_type"
):
    skipped = code in SKIP_TYPE_CODES
    marker = "  [SKIP]" if skipped else "  [KEEP]"
    print(f"    {code:2d}: {count:5d}  {marker}")
print(f"  total: {total_ext}")
print(f"  应上传 (扣 SKIP): {should_upload}")

# 真实覆盖率 = (IMA 端 ∩ upstream KEEP) / 应上传
covered = ima_msg_ids & keep_ids
orphan = ima_msg_ids - keep_ids  # IMA 有但 extracted 没了 (理论上=0)
if should_upload > 0:
    pct = len(covered) * 100.0 / should_upload
    missing = should_upload - len(covered)
    print(f"  IMA 端覆盖率:    {pct:.2f}%  ({len(covered)}/{should_upload})")
    print(f"  真缺 (KEEP & IMA 未收): {missing} 条")
    if orphan:
        print(f"  孤儿 (IMA 有但 upstream 没了): {len(orphan)} 条")
print()

# heartbeat
hb = con.execute("SELECT status, last_run_at, note FROM heartbeat WHERE id=1").fetchone()
print(f"heartbeat: status={hb[0]}  last_run_at={hb[1]}")
print(f"           note={hb[2]}")
con.close()
