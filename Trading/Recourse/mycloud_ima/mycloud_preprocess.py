"""mycloud_preprocess: mycloud.db → LLM preprocessing → SQLite + IMA 知识库.

生产管道:
  1. 从 jcloud:9623 (mycloud_proxy) 同步 records 到 mycloud_preprocess.db
  2. 调 qwen3.5-flash 做 10 类分类 + 4 字段抽取
  3. UPSERT 写 extracted 3 表
  4. 每 10 条 msg 合并为一个笔记，推送到 IMA 二级市场 + Stock 两个知识库
  5. 写 4 个产物到 ./

msg_id = mycloud.records.id (SQLite INTEGER PRIMARY KEY, 8-73 当前范围, 永不复用).
笔记标题格式: "mycloud {date} #{batch_seq}" (如 "mycloud 2026-07-05 #1").

跟 feishu_preprocess 的差异:
  - DB 路径: data/mycloud_preprocess.db (独立)
  - 同步源: jcloud:9623 /sync/records/incremental (独立 proxy)
  - 过滤: 服务端限定 category='stock', type IN ('text','md')
  - 推送: IMA 知识库（二级市场 + Stock），每 10 条一个笔记
"""
from __future__ import annotations

import datetime
import json
import os
import sqlite3
import sys
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

HERE = Path(__file__).resolve().parent
FEISHU_PREPROCESS_DIR = HERE.parent / "feishu_preprocess"
sys.path.insert(0, str(FEISHU_PREPROCESS_DIR))

from prompts.schemas import (
    LLMInput, LLMOutput, InputItem,
)
from prompts.loader import load_prompt

# mycloud 自己的 db_writer (独立实现, 0 改 feishu db_writer.py)
sys.path.insert(0, str(HERE))
from mycloud_db_writer import (
    ensure_schema, upsert_extracted, mark_posted_to_ima, get_posted_msg_ids,
    sync_mycloud_records,
)

# ---------------------------------------------------------------------- #
# config                                                                  #
# ---------------------------------------------------------------------- #

DATA_DIR = HERE / "data"
DB = DATA_DIR / "mycloud_preprocess.db"

# jcloud 上的 mycloud_proxy HTTP 代理
REMOTE_MYCLOUD_URL = os.environ.get("REMOTE_MYCLOUD_URL", "").rstrip("/")
REMOTE_MYCLOUD_USER = os.environ.get("REMOTE_MYCLOUD_USER", "")
REMOTE_MYCLOUD_PASS = os.environ.get("REMOTE_MYCLOUD_PASS", "")

# mycloud 服务端过滤参数 (硬编码)
MYCLOUD_CATEGORY = "stock"
MYCLOUD_TYPES = "text,md"

# 产物路径
OUT_MD = HERE / "mycloud_preprocess_output.md"
OUT_RAW = HERE / "mycloud_preprocess_raw.json"
OUT_PROMPT = HERE / "mycloud_preprocess_prompt.md"
OUT_DB_WRITES = HERE / "mycloud_preprocess_db_writes.md"

DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_KEY = os.environ["DASHSCOPE_API_KEY"]
MAX_TOTAL_CHARS = int(os.environ.get("FEISHU_PREPROCESS_MAX_TOTAL_CHARS", "50000"))
SAFETY_MAX_ITEMS = int(os.environ.get("FEISHU_PREPROCESS_SAFETY_MAX_ITEMS", "500"))
MODE = os.environ.get("FEISHU_PREPROCESS_MODE", "historical")
TZ = datetime.timezone(datetime.timedelta(hours=8))

# IMA: 每 N 条 msg 合并为一个笔记
IMA_BATCH_SIZE = 10

# IMA 知识库 ID
IMA_KB_IDS = [
    "tW0oaPZ_VJLkOhiF1w3HnDkIBC2iq-KF30Ak5N3oZFk=",  # 二级市场
    "hCx6uC-_z2qJOV0ieth8TCLb5wbWT8gZoVh7UIAmnos=",  # Stock
]

DRY_RUN_IMA = os.environ.get("MYCLOUD_PREPROCESS_DRY_RUN_IMA", "0") == "1"


# ---------------------------------------------------------------------- #
# DB                                                                      #
# ---------------------------------------------------------------------- #


def fetch_batch(
    db_path: Path,
    *,
    cursor_ts: int = 0,
    max_total_chars: int = MAX_TOTAL_CHARS,
    safety_max_items: int = SAFETY_MAX_ITEMS,
) -> tuple[list[tuple[int, int, str]], dict]:
    """按总原文字符数累加拉批, 直到 sum(len(content)) > max_total_chars 为止."""
    con = sqlite3.connect(str(db_path))
    try:
        ensure_schema(con)
        if cursor_ts == 0:
            row = con.execute(
                "SELECT COALESCE(MAX(last_push_ts), 0) FROM ima_push_batches WHERE posted = 1"
            ).fetchone()
            cursor_ts = int(row[0]) if row and row[0] else 0
        candidates = con.execute(
            "SELECT m.id, m.ts, m.content FROM messages m "
            "LEFT JOIN extracted e ON m.id = e.msg_id "
            "WHERE m.kind = 't' AND length(m.content) > 10 "
            "  AND m.ts > ? "
            "  AND (e.rowid IS NULL OR e.posted = 0) "
            "ORDER BY m.ts ASC LIMIT ?",
            (cursor_ts, safety_max_items),
        ).fetchall()
    finally:
        con.close()

    rows: list[tuple[int, int, str]] = []
    total = 0
    for msg_id, ts, text in candidates:
        if rows and total + len(text) > max_total_chars:
            break
        rows.append((int(msg_id), int(ts), text))
        total += len(text)

    stats = {
        "count": len(rows),
        "total_orig_chars": total,
        "max_total_chars": max_total_chars,
        "hit_budget": total >= max_total_chars,
        "cursor_ts": cursor_ts,
        "last_ts": rows[-1][1] if rows else cursor_ts,
    }
    return rows, stats


# ---------------------------------------------------------------------- #
# LLM call                                                               #
# ---------------------------------------------------------------------- #


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    retry=retry_if_exception_type((json.JSONDecodeError, ValueError, Exception)),
    reraise=True,
)
def call_and_validate(
    client: OpenAI,
    model: str,
    system: str,
    user: str,
) -> tuple[LLMOutput, dict]:
    """Call LLM, return (validated_output, usage_dict)."""
    extra_body = {"enable_thinking": False}
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            extra_body=extra_body,
        )
        fmt = "json_object"
    except Exception as e:  # noqa: BLE001
        print(f"[llm] response_format 不被支持({type(e).__name__})，退纯 prompt 模式")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            extra_body=extra_body,
        )
        fmt = "prompt_only"

    content = resp.choices[0].message.content or ""
    out = LLMOutput.model_validate_json(content)
    usage = {
        "format": fmt,
        "model": resp.model,
        "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
        "completion_tokens": getattr(resp.usage, "completion_tokens", None),
        "total_tokens": getattr(resp.usage, "total_tokens", None),
        "raw_content": content,
    }
    return out, usage


# ---------------------------------------------------------------------- #
# helpers                                                                #
# ---------------------------------------------------------------------- #


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    return obj


def _build_note_text(chunk: list[tuple[int, int, str, object]]) -> str:
    """把一个 chunk（≤10条）构建成 Markdown 笔记内容。"""
    lines = []
    info_type_map = {
        1: "盘前", 2: "盘后", 3: "周报", 4: "盘中", 5: "时政",
        6: "段子", 7: "公告", 8: "研报", 9: "新闻", 10: "其他"
    }
    for msg_id, ts, text, r in chunk:
        ts_str = datetime.datetime.fromtimestamp(ts / 1000, TZ).strftime("%Y-%m-%d %H:%M")
        info_label = info_type_map.get(r.info_type, str(r.info_type))
        stocks = ", ".join(r.involved_stocks) if r.involved_stocks else "-"
        category = r.category or "-"
        summary = r.summary or "-"
        lines.append(
            f"---\n"
            f"**[{info_label}]** {category}  |  关联股票: {stocks}\n"
            f"摘要: {summary}\n\n"
            f"**原文** ({ts_str}, id={msg_id}):\n{text}\n"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------- #
# IMA push                                                               #
# ---------------------------------------------------------------------- #

def _load_ima_creds():
    """加载 IMA API 凭证。"""
    import os as _os
    for _p in [Path(_os.path.expanduser("~/.config/ima/client_id")),
                Path(_os.path.expanduser("~/.config/ima/api_key"))]:
        if not _p.exists():
            return None, None
    with open(Path(_os.path.expanduser("~/.config/ima/client_id"))) as f:
        cid = f.read().strip()
    with open(Path(_os.path.expanduser("~/.config/ima/api_key"))) as f:
        ckey = f.read().strip()
    return cid, ckey


def _ima_api(api_path: str, body: dict) -> dict | None:
    """调 ima_api.cjs，返回解析后的 JSON 响应或 None。"""
    import subprocess, os as _os
    skill_dir = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "ima-skill"
    cid, ckey = _load_ima_creds()
    if cid is None:
        print(f"       [IMA] 凭证未配置 (~/.config/ima/)")
        return None
    opts = f'{{"clientId":"{cid}","apiKey":"{ckey}"}}'
    body_str = json.dumps(body, ensure_ascii=False)
    cmd = ["node", str(skill_dir / "ima_api.cjs"), api_path, body_str, opts]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            env={**_os.environ, "IMA_FORCE_UPDATE_CHECK": "0"},
        )
        if result.returncode != 0:
            try:
                err = json.loads(result.stderr)
                print(f"       [IMA] {api_path} error: {err.get('msg', result.stderr[:200])}")
            except Exception:
                print(f"       [IMA] {api_path} failed: {result.stderr[:200]}")
            return None
        resp = json.loads(result.stdout)
        if resp.get("code") != 0:
            print(f"       [IMA] {api_path} code={resp.get('code')}: {resp.get('msg')}")
            return None
        return resp
    except subprocess.TimeoutExpired:
        print(f"       [IMA] {api_path} timeout")
        return None
    except Exception as e:
        print(f"       [IMA] {api_path} exception: {e}")
        return None


def push_to_ima(
    aligned: list[tuple[int, int, str, object]],
    dry_run: bool = False,
) -> dict:
    """按 IMA_BATCH_SIZE 分批，每批创建一个笔记并添加到两个知识库。

    Returns: {
        "status": "success" | "dry_run" | "error",
        "batches": [{"msg_ids": [...], "note_id": str|None, "kb_results": {kb_id: bool}}],
        "posted_msg_ids": [all posted msg_ids],
    }
    """
    kb_names = {
        "tW0oaPZ_VJLkOhiF1w3HnDkIBC2iq-KF30Ak5N3oZFk=": "二级市场",
        "hCx6uC-_z2qJOV0ieth8TCLb5wbWT8gZoVh7UIAmnos=": "Stock",
    }
    n = IMA_BATCH_SIZE
    chunks = [aligned[i:i+n] for i in range(0, len(aligned), n)]
    today = datetime.datetime.now(TZ).strftime("%Y-%m-%d")
    batches_result = []
    all_posted_msg_ids = []

    for batch_idx, chunk in enumerate(chunks, 1):
        msg_ids = [mid for mid, _, _, _ in chunk]
        ts_list = [ts for _, ts, _, _ in chunk]
        title = f"mycloud {today} #{batch_idx}"
        note_text = _build_note_text(chunk)

        if dry_run:
            print(f"       [DRY RUN] batch {batch_idx}/{len(chunks)}: "
                  f"{len(chunk)} msgs, title={title}, msg_ids={msg_ids}")
            batches_result.append({
                "msg_ids": msg_ids,
                "note_id": None,
                "kb_results": {kb_id: False for kb_id in IMA_KB_IDS},
                "dry_run": True,
            })
            all_posted_msg_ids.extend(msg_ids)
            continue

        # 1. 创建笔记
        resp = _ima_api("openapi/note/v1/import_doc", {
            "content": note_text,
            "content_format": 1,
        })
        if not resp:
            batches_result.append({
                "msg_ids": msg_ids,
                "note_id": None,
                "kb_results": {kb_id: False for kb_id in IMA_KB_IDS},
            })
            continue

        note_id = resp.get("data", {}).get("note_id")
        if not note_id:
            print(f"       [WARN] batch {batch_idx}: no note_id in response")
            batches_result.append({
                "msg_ids": msg_ids,
                "note_id": None,
                "kb_results": {kb_id: False for kb_id in IMA_KB_IDS},
            })
            continue

        print(f"       [IMA] batch {batch_idx}/{len(chunks)}: "
              f"note_id={note_id}, msgs={msg_ids}")

        # 2. 添加到两个知识库
        kb_results = {}
        for kb_id in IMA_KB_IDS:
            r = _ima_api("openapi/wiki/v1/add_knowledge", {
                "media_type": 11,
                "note_info": {"content_id": note_id},
                "title": note_id,
                "knowledge_base_id": kb_id,
            })
            ok = r is not None
            kb_results[kb_id] = ok
            print(f"       [IMA]   → {kb_names.get(kb_id, kb_id[:16])}: {'OK' if ok else 'FAILED'}")

        batches_result.append({
            "msg_ids": msg_ids,
            "note_id": note_id,
            "kb_results": kb_results,
        })
        all_posted_msg_ids.extend(msg_ids)

    return {
        "status": "dry_run" if dry_run else "success",
        "batches": batches_result,
        "posted_msg_ids": all_posted_msg_ids,
    }


# ---------------------------------------------------------------------- #
# main                                                                   #
# ---------------------------------------------------------------------- #

def main() -> int:
    import time
    start_ts = time.time()
    if not REMOTE_MYCLOUD_URL:
        print("ERROR: REMOTE_MYCLOUD_URL not set.")
        print("       export REMOTE_MYCLOUD_URL=https://buumicloud.com.cn/mycloud-api")
        return 2

    # 0. 同步
    print(f"[0/7] init {DB} + sync from REMOTE {REMOTE_MYCLOUD_URL} …")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sync_con = sqlite3.connect(str(DB))
    try:
        ensure_schema(sync_con)
        sync_stats = sync_mycloud_records(
            sync_con,
            base_url=REMOTE_MYCLOUD_URL,
            username=REMOTE_MYCLOUD_USER,
            password=REMOTE_MYCLOUD_PASS,
            category=MYCLOUD_CATEGORY,
            types=MYCLOUD_TYPES,
        )
        print(f"       schema OK, sync: +{sync_stats['synced']} new rows")
    finally:
        sync_con.close()

    if sync_stats["synced"] == 0 and not fetch_batch(DB)[0]:
        print("       no new mycloud records and no unprocessed rows, exit 0")
        return 0

    # 1. 读批次
    print(f"[1/7] reading {DB} (budget={MAX_TOTAL_CHARS:,} chars) …")
    batch, batch_stats = fetch_batch(DB)
    print(f"       got {batch_stats['count']} rows, total {batch_stats['total_orig_chars']:,} chars")
    if not batch:
        print("ERROR: empty batch")
        return 1

    # 2. LLM Input
    print(f"[2/7] constructing LLMInput …")
    payload_items = [
        InputItem(idx=i, ts=ts, text=text, orig_len=len(text))
        for i, (_mid, ts, text) in enumerate(batch, 1)
    ]
    input_payload = LLMInput(count=len(batch), items=payload_items)

    # 3. LLM
    print(f"[3/7] loading prompt (mode={MODE}) …")
    system, user, fm = load_prompt(MODE, input_payload)
    print(f"       system={len(system)} chars, user={len(user)} chars")

    print(f"[4/7] calling LLM ({fm.get('model')}) …")
    client = OpenAI(api_key=DASHSCOPE_KEY, base_url=DASHSCOPE_BASE)
    out, usage = call_and_validate(client, fm["model"], system, user)
    print(f"       got {len(out.results)} results, tokens={usage['prompt_tokens']}/{usage['completion_tokens']}/{usage['total_tokens']}")

    # 守恒校验
    in_idx_set = {it.idx for it in input_payload.items}
    out_idx_set = {r.task_id for r in out.results}
    if len(out.results) != input_payload.count or in_idx_set != out_idx_set:
        raise ValueError(f"task_id/count mismatch")
    print(f"       conservation OK")

    # 4. 写 DB
    print(f"[5/7] writing extracted …")
    by_task = {r.task_id: r for r in out.results}
    aligned = [
        (msg_id, ts, text, by_task[i + 1])
        for i, (msg_id, ts, text) in enumerate(batch)
    ]
    db_con = sqlite3.connect(str(DB))
    try:
        ensure_schema(db_con)
        for msg_id, ts, _text, result in aligned:
            upsert_extracted(db_con, msg_id=msg_id, ts=ts, result=result)
        db_con.commit()
    finally:
        db_con.close()
    print(f"       wrote {len(aligned)} rows")

    # 5. IMA push
    print(f"[6/7] push to IMA (batch_size={IMA_BATCH_SIZE}, KBs=2) …")
    push_result = push_to_ima(aligned, dry_run=DRY_RUN_IMA)

    # 6. 标记 posted + 写产物
    print(f"[7/7] marking posted + writing artifacts …")
    if push_result["posted_msg_ids"] and not DRY_RUN_IMA:
        db_con2 = sqlite3.connect(str(DB))
        try:
            ts_list = [ts for mid, ts, _, _ in aligned for _m in push_result["posted_msg_ids"] if _m == mid]
            max_ts = max(ts for mid, ts, _, _ in aligned if mid in push_result["posted_msg_ids"]) if ts_list else 0
            mark_posted_to_ima(db_con2, push_result["posted_msg_ids"], max_ts)
            db_con2.commit()
        finally:
            db_con2.close()

    OUT_PROMPT.write_text(_render_prompt_md(system, user, fm), encoding="utf-8")
    OUT_MD.write_text(_render_decisions_md(batch, out, usage, fm), encoding="utf-8")
    raw_obj = {
        "run_at": datetime.datetime.now(TZ).isoformat(),
        "db": {"path": str(DB), "size": DB.stat().st_size},
        "frontmatter": _json_safe(fm),
        "input_payload": input_payload.model_dump(),
        "raw_response": usage["raw_content"],
        "parsed": out.model_dump(),
        "usage": {k: v for k, v in usage.items() if k != "raw_content"},
        "ima_push": push_result,
        "ima_batch_size": IMA_BATCH_SIZE,
        "ima_kb_ids": IMA_KB_IDS,
    }
    OUT_RAW.write_text(json.dumps(raw_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_DB_WRITES.write_text(_render_db_writes_md(aligned), encoding="utf-8")
    print(f"       wrote 4 artifacts")

    # heartbeat
    try:
        batches = push_result.get("batches", [])
        successful = [b for b in batches if b.get("note_id")]
        note_ids = [b["note_id"] for b in successful if b.get("note_id")]
        hb = {
            "source": "mycloud",
            "mode": MODE,
            "dry_run": DRY_RUN_IMA,
            "last_run_at": datetime.datetime.now(TZ).isoformat(timespec="seconds"),
            "last_status": push_result.get("status", "unknown"),
            "last_duration_s": round(time.time() - start_ts),
            "last_batch_size": len(batch),
            "ima_batches": len(batches),
            "ima_successful_batches": len(successful),
            "ima_note_ids": note_ids,
            "last_posted_count": len(push_result.get("posted_msg_ids") or []),
        }
        (DATA_DIR / "heartbeat.json").write_text(json.dumps(hb, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"       WARN: heartbeat write failed: {e}")

    print(f"\nDONE. {len(successful)}/{len(batches)} batches OK, {len(push_result.get('posted_msg_ids', []))} msg_ids posted")
    return 0


def _render_prompt_md(system: str, user: str, fm: dict) -> str:
    return "\n".join([
        "# mycloud_preprocess Prompt Render",
        f"- Mode: `{MODE}`",
        f"- Frontmatter: {json.dumps(_json_safe(fm), ensure_ascii=False)}",
        "",
        "## System prompt",
        "````markdown",
        system,
        "````",
        "",
        "## User prompt",
        "````markdown",
        user,
        "````",
        "",
    ])


def _render_decisions_md(batch, out: LLMOutput, usage: dict, fm: dict) -> str:
    by_task = {r.task_id: r for r in out.results}
    lines = [
        "# mycloud_preprocess Output",
        "",
        f"- Run at: {datetime.datetime.now(TZ).isoformat()}",
        f"- DB: `{DB}`",
        f"- Mode: `{MODE}`",
        f"- response_format: `{usage['format']}`",
        f"- Tokens: {usage['prompt_tokens']}/{usage['completion_tokens']}/{usage['total_tokens']}",
        f"- IMA push: 每 {IMA_BATCH_SIZE} 条一个笔记 → 二级市场 + Stock",
        "",
        "## Per-task",
        "",
    ]
    for i, (msg_id, ts, text) in enumerate(batch, 1):
        ts_str = datetime.datetime.fromtimestamp(ts / 1000, TZ).strftime("%Y-%m-%d %H:%M:%S")
        r = by_task.get(i)
        tag = f"IMA batch (info_type={r.info_type})" if r else "MISSING"
        lines.append(f"- task_id={i} msg_id={msg_id} ts={ts_str} → {tag}")
    return "\n".join(lines)


def _render_db_writes_md(aligned) -> str:
    info_type_map = {
        1: "盘前", 2: "盘后", 3: "周报", 4: "盘中", 5: "时政",
        6: "段子", 7: "公告", 8: "研报", 9: "新闻", 10: "其他"
    }
    lines = [
        "# mycloud_preprocess DB Writes",
        f"- Run at: {datetime.datetime.now(TZ).isoformat()}",
        f"- rows: {len(aligned)}",
        "",
        "| msg_id | ts | info_type | category | stocks | summary |",
        "|---:|---:|---|---|---|---|---|",
    ]
    for msg_id, ts, _text, r in aligned:
        ts_str = datetime.datetime.fromtimestamp(ts / 1000, TZ).strftime("%Y-%m-%d %H:%M")
        stocks = ", ".join(r.involved_stocks) if r.involved_stocks else ""
        summary = (r.summary or "").replace("|", "\\|")
        category = (r.category or "").replace("|", "\\|")
        lines.append(f"| {msg_id} | {ts_str} | {info_type_map.get(r.info_type, r.info_type)} | {category} | {stocks} | {summary} |")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
