"""feishu_preprocess: messages.db -> LLM preprocessing -> SQLite.

生产管道:
  1. 读 messages.db (软链到 feishu_sync 主 DB), 按 id ASC + 水位过滤
  2. 调 qwen3.5-flash 做 10 类分类 + 4 字段抽取
  3. UPSERT 写 extracted 3 表 (水位自然形成: 跳过 msg_id 已在 extracted 里的)
  4. 写 4 个产物到 ./

msg_id = messages.id（显式 INTEGER PRIMARY KEY AUTOINCREMENT，永不复用），
与历史隐式 rowid 数值一致。30w 滚动上限下不会被 prune_oldest 删除后复用，
下游 IMA 模块读取 extracted 表进行推送。

Schema: {results: [{task_id, info_type, category, involved_stocks,
                    core_tech_terms, summary}]}
Each input gets exactly one TaskResult; task_id ↔ input idx 1-to-1.
"""
from __future__ import annotations

import datetime
import json
import os
import sqlite3
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from prompts.schemas import (
    LLMInput, LLMOutput, InputItem, truncate_text,
)
from prompts.loader import load_prompt
from feishu_db_writer import (
    ensure_schema, migrate_messages_id_column, upsert_extracted,
    sync_messages_from, sync_messages_from_remote,
)
# 2026-06-23 拍板: SKIP_TYPES 中文仍存在 (back-compat), 但过滤判断统一用 SKIP_TYPE_CODES (整数).
# TaskResult.info_type 是整数 1-10, 中文 label 通过 CODE_TO_LABELS 拿.
from prompts.schemas import CODE_TO_LABELS, SKIP_TYPE_CODES

# ---------------------------------------------------------------------- #
# config                                                                  #
# ---------------------------------------------------------------------- #

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
DB = DATA_DIR / "preprocess.db"
# messages.db 来源 (二选一):
#   - REMOTE_FEISHU_MESSAGES_URL  有 → 走 jcloud HTTP proxy (推荐, 本机不持有 messages.db)
#   - REMOTE_FEISHU_MESSAGES_URL  空 → 走本地 sqlite ATTACH (SYNC_MESSAGES_DB 路径)
REMOTE_FEISHU_MESSAGES_URL = os.environ.get("REMOTE_FEISHU_MESSAGES_URL", "").rstrip("/")
REMOTE_FEISHU_MESSAGES_USER = os.environ.get("REMOTE_FEISHU_MESSAGES_USER", "")
REMOTE_FEISHU_MESSAGES_PASS = os.environ.get("REMOTE_FEISHU_MESSAGES_PASS", "")
USE_REMOTE = bool(REMOTE_FEISHU_MESSAGES_URL)
# 本地 sqlite 路径 (仅 USE_REMOTE=False 时使用)
SYNC_MESSAGES_DB = os.environ.get(
    "SYNC_MESSAGES_DB",
    "/root/feishu/data/oc_8121f1662983563a46a6b3c818631ddc/messages.db",
)
OUT_MD = HERE / "feishu_preprocess_output.md"
OUT_RAW = HERE / "feishu_preprocess_raw.json"
OUT_PROMPT = HERE / "feishu_preprocess_prompt.md"
OUT_DB_WRITES = HERE / "feishu_preprocess_db_writes.md"

DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_KEY = os.environ["DASHSCOPE_API_KEY"]   # env 缺失直接 KeyError, fail-fast
# 批次总原文字符上限（原 DB 内容长度之和,不含 JSON 包装/truncate）
MAX_TOTAL_CHARS = int(os.environ.get("FEISHU_PREPROCESS_MAX_TOTAL_CHARS", "50000"))
# 兜底:单批最多取多少条,防 runaway
SAFETY_MAX_ITEMS = int(os.environ.get("FEISHU_PREPROCESS_SAFETY_MAX_ITEMS", "500"))
MODE = os.environ.get("FEISHU_PREPROCESS_MODE", "historical")
TZ = datetime.timezone(datetime.timedelta(hours=8))


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
    """按总原文字符数累加拉批, 直到 sum(len(content)) > max_total_chars 为止.

    水位定义 (ts 语义):
      - 主水位: cursor_ts (默认 0 时自动从 extracted.max(ts) 取, 即"已处理最新一条信息的 ts")
      - 次保护: LEFT JOIN extracted 跳过已抽取的 msg_id (防 ts 撞 + 防重复)

    排序按 m.ts ASC (跟业务时间线一致).

    至少保证返回 1 条(即使单条 > max_total_chars, 也不卡死).
    返回 (rows, stats) where rows = [(msg_id, ts, text), ...] -- msg_id = messages.id
    """
    con = sqlite3.connect(str(db_path))
    try:
        # ensure_schema: idempotent, 首次跑无 extracted 表时也能工作
        ensure_schema(con)
        # 自动水位: cursor_ts=0 时取 max(extracted.ts), 即"已处理最新一条信息的 ts"
        if cursor_ts == 0:
            row = con.execute("SELECT COALESCE(MAX(ts), 0) FROM extracted").fetchone()
            cursor_ts = int(row[0])
        # 主水位 (ts): 只 fetch ts > cursor_ts 的消息
        # 次保护: LEFT JOIN 跳过已抽取 msg_id (防 ts 撞)
        candidates = con.execute(
            "SELECT m.id, m.ts, m.content FROM messages m "
            "LEFT JOIN extracted e ON m.id = e.msg_id "
            "WHERE m.kind = 't' AND length(m.content) > 10 "
            "  AND m.ts > ? "
            "  AND e.rowid IS NULL "
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
# LLM call (with Pydantic validation + tenacity retry)                   #
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
    """Call LLM, return (validated_output, usage_dict). Retries on parse/validation errors."""
    # 关掉 qwen3 系列的 thinking mode,避免 4500+ token 内部推理被算进 completion_tokens
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
    out = LLMOutput.model_validate_json(content)  # raises on bad JSON / schema
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
# MD renderers                                                            #
# ---------------------------------------------------------------------- #


def _json_safe(obj):
    """Recursively cast date/datetime to ISO strings (yaml auto-parses ISO dates).

    json.dumps requires dict keys to be str/int/float/bool/None — YAML frontmatter
    like `- 2026-06-23: foo` parses to {datetime.date(2026,6,23): "foo"} and would
    crash. Handle keys too. (2026-06-23 feishu_preprocess frontmatter changelog.)
    """
    if isinstance(obj, dict):
        return {_json_safe_key(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    return obj


def _json_safe_key(k):
    """Coerce date/datetime dict keys to ISO strings (json.dumps rejects them)."""
    if isinstance(k, (datetime.date, datetime.datetime)):
        return k.isoformat()
    return k


# SKIP_TYPE_CODES 在 prompts.schemas 中定义, 由顶部 import 独占使用



def render_decisions_md(batch, out: LLMOutput, usage: dict, fm: dict) -> str:
    """每个 task 的 LLM 提取结果."""
    by_task = {r.task_id: r for r in out.results}
    in_idx_set = set(range(1, len(batch) + 1))
    out_idx_set = set(by_task.keys())

    lines = [
        "# feishu_preprocess Output", "",
        f"- Run at: {datetime.datetime.now(TZ).isoformat()}",
        f"- DB: `{DB}`  ({DB.stat().st_size:,} bytes)",
        f"- Mode: `{MODE}`  (prompt version {fm.get('version')}, model `{fm.get('model')}`)",
        f"- response_format: `{usage['format']}`",
        f"- Tokens: in={usage['prompt_tokens']}  out={usage['completion_tokens']}  total={usage['total_tokens']}",
        f"- count: in={len(batch)}  out={len(out.results)}  match={len(batch) == len(out.results)}",
        f"- task_id set match: {in_idx_set == out_idx_set}",
        "",
        "## Per-task trace", "",
    ]
    for i, (msg_id, ts, text) in enumerate(batch, 1):
        ts_str = datetime.datetime.fromtimestamp(ts / 1000, TZ).strftime("%Y-%m-%d %H:%M:%S")
        r = by_task.get(i)
        if r is None:
            lines += [f"### task_id={i}  (msg_id={msg_id}, ts={ts}, {ts_str})  [MISSING]", ""]
            continue
        lines += [
            f"### task_id={i}  (msg_id={msg_id}, ts={ts}, {ts_str})  {r.info_type} ({CODE_TO_LABELS[int(r.info_type)]})",
            "",
            f"- info_type: {r.info_type} ({CODE_TO_LABELS[int(r.info_type)]})",
            f"- category: {r.category or '(无)'}",
            f"- stocks: {', '.join(r.involved_stocks) if r.involved_stocks else '(无)'}",
            f"- terms: {', '.join(r.core_tech_terms) if r.core_tech_terms else '(无)'}",
            f"- summary: {r.summary or '(无)'}",
            "",
        ]
    return "\n".join(lines)


def render_prompt_md(system: str, user: str, fm: dict) -> str:
    lines = [
        "# feishu_preprocess Prompt Render",
        "",
        f"- Mode: `{MODE}`",
        f"- Frontmatter: {json.dumps(_json_safe(fm), ensure_ascii=False)}",
        "",
        "## System prompt (the actual text sent to the LLM)",
        "",
        "````markdown",
        system,
        "````",
        "",
        "## User prompt (the actual text sent to the LLM)",
        "",
        "````markdown",
        user,
        "````",
        "",
    ]
    return "\n".join(lines)


def render_db_writes_md(aligned: list[tuple[int, int, str, object]]) -> str:
    """第 4 个产物:DB 写入摘要. 一行 = 一条 extracted 表行.

    aligned: [(msg_id, ts, text, TaskResult), ...]
    """
    lines = [
        "# feishu_preprocess DB Writes",
        "",
        f"- Run at: {datetime.datetime.now(TZ).isoformat()}",
        f"- rows written: {len(aligned)}",
        "",
        "| msg_id | ts | info_type | category | stocks | terms | summary |",
        "|---:|---:|---|---|---|---|---|",
    ]
    for msg_id, ts, _text, r in aligned:
        ts_str = datetime.datetime.fromtimestamp(ts / 1000, TZ).strftime("%Y-%m-%d %H:%M")
        stocks = ", ".join(r.involved_stocks) if r.involved_stocks else ""
        terms = ", ".join(r.core_tech_terms) if r.core_tech_terms else ""
        summary = r.summary.replace("|", "\\|") if r.summary else ""
        category = r.category.replace("|", "\\|") if r.category else ""
        lines.append(
            f"| {msg_id} | {ts_str} | {r.info_type}({CODE_TO_LABELS[int(r.info_type)]}) | {category} | {stocks} | {terms} | {summary} |"
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------- #
# main                                                                    #
# ---------------------------------------------------------------------- #


def main() -> int:
    import time
    start_ts = time.time()
    # 0. 初始化 preprocess.db + 同步 sync.messages
    if USE_REMOTE:
        print(f"[0/7] init preprocess.db + sync from REMOTE {REMOTE_FEISHU_MESSAGES_URL} …")
    else:
        print(f"[0/7] init preprocess.db + sync from {SYNC_MESSAGES_DB} …")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sync_con = sqlite3.connect(str(DB))
    try:
        ensure_schema(sync_con)
        # 老库（messages 无 id 列）迁移: 建新表 + 倒数据 + 改名, 保证 extracted.msg_id 引用有效
        migrated = migrate_messages_id_column(sync_con)
        if migrated:
            print(f"       messages 表迁移完成: id 列已加 (AUTOINCREMENT)")
        if USE_REMOTE:
            sync_stats = sync_messages_from_remote(
                sync_con,
                base_url=REMOTE_FEISHU_MESSAGES_URL,
                username=REMOTE_FEISHU_MESSAGES_USER,
                password=REMOTE_FEISHU_MESSAGES_PASS,
            )
        else:
            sync_stats = sync_messages_from(sync_con, SYNC_MESSAGES_DB)
        print(f"       schema OK, sync: +{sync_stats['synced']} new rows "
              f"(preprocess={sync_stats['preprocess_total']:,}, sync={sync_stats['sync_total']:,})")
    finally:
        sync_con.close()

    if sync_stats["synced"] == 0 and not fetch_batch(DB)[0]:
        # 没新消息 + 没未抽取 = 直接退出, 不浪费 LLM
        print("       no new messages and no unprocessed rows, exit 0")
        return 0

    print(f"[1/6] reading {DB} (budget={MAX_TOTAL_CHARS:,} chars) …")
    batch, batch_stats = fetch_batch(DB)
    print(f"       got {batch_stats['count']} rows, total {batch_stats['total_orig_chars']:,} chars, "
          f"hit_budget={batch_stats['hit_budget']}")
    if not batch:
        # sync 拉到的新行可能全是 kind='i' (图片) 或 kind='t' 但 length ≤ 10 ——
        # 都是合法状态,没有可抽取文本就直接 return 0,不要污染仪表板。
        print(f"       no eligible kind='t' rows (sync may have only pulled images or short text), exit 0")
        return 0

    print(f"[2/6] constructing LLMInput (no truncation) …")
    payload_items = []
    for i, (_msg_id, ts, text) in enumerate(batch, 1):
        # msg_id 不进 LLMInput -- LLM 不需要
        # 不截断,LLM 看到完整原文
        payload_items.append(InputItem(
            idx=i, ts=ts,
            text=text,
            orig_len=len(text),
        ))
    input_payload = LLMInput(count=len(batch), items=payload_items)
    print(f"       {len(payload_items)} items, total {sum(it.orig_len for it in payload_items):,} chars")

    print(f"[3/6] loading prompt (mode={MODE}) …")
    system, user, fm = load_prompt(MODE, input_payload)
    print(f"       system={len(system)} chars, user={len(user)} chars")

    print(f"[4/6] calling LLM ({fm.get('model')}) …")
    client = OpenAI(api_key=DASHSCOPE_KEY, base_url=DASHSCOPE_BASE)
    out, usage = call_and_validate(client, fm["model"], system, user)
    print(f"       got {len(out.results)} results, tokens in/out/total = "
          f"{usage['prompt_tokens']}/{usage['completion_tokens']}/{usage['total_tokens']}")

    # 数量守恒 + task_id 守恒硬断言
    in_idx_set = {it.idx for it in input_payload.items}
    out_idx_set = {r.task_id for r in out.results}
    if len(out.results) != input_payload.count:
        raise ValueError(f"count mismatch: out={len(out.results)} != in={input_payload.count}")
    if in_idx_set != out_idx_set:
        raise ValueError(f"task_id set mismatch: missing={in_idx_set - out_idx_set}, extra={out_idx_set - in_idx_set}")
    print(f"       conservation: count OK, task_id set OK")

    # 5. 把 msg_id 对齐回 TaskResult,准备写 SQLite
    print(f"[5/7] aligning msg_id + writing to extracted …")
    by_task = {r.task_id: r for r in out.results}
    aligned = [
        (msg_id, ts, text, by_task[i + 1])
        for i, (msg_id, ts, text) in enumerate(batch)
    ]
    # aligned: [(msg_id, ts, text, TaskResult), ...]

    db_con = sqlite3.connect(str(DB))
    try:
        ensure_schema(db_con)  # idempotent
        for msg_id, ts, _text, result in aligned:
            upsert_extracted(db_con, msg_id=msg_id, ts=ts, result=result)
        db_con.commit()
    finally:
        db_con.close()
    print(f"       wrote {len(aligned)} rows to extracted")

    # 6. 写 4 个产物
    print(f"[6/7] writing artifacts …")
    OUT_PROMPT.write_text(render_prompt_md(system, user, fm), encoding="utf-8")
    print(f"       wrote {OUT_PROMPT}  ({OUT_PROMPT.stat().st_size:,} bytes)")
    OUT_MD.write_text(render_decisions_md(batch, out, usage, fm), encoding="utf-8")
    print(f"       wrote {OUT_MD}  ({OUT_MD.stat().st_size:,} bytes)")
    raw_obj = {
        "run_at": datetime.datetime.now(TZ).isoformat(),
        "db": {"path": str(DB), "size": DB.stat().st_size},
        "frontmatter": _json_safe(fm),
        "input_payload": input_payload.model_dump(),
        "raw_response": usage["raw_content"],
        "parsed": out.model_dump(),
        "usage": {k: v for k, v in usage.items() if k != "raw_content"},
    }
    OUT_RAW.write_text(json.dumps(raw_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"       wrote {OUT_RAW}  ({OUT_RAW.stat().st_size:,} bytes)")
    db_writes_md = render_db_writes_md(aligned)
    OUT_DB_WRITES.write_text(db_writes_md, encoding="utf-8")
    print(f"       wrote {OUT_DB_WRITES}  ({OUT_DB_WRITES.stat().st_size:,} bytes)")

    print(f"\nDONE. 四个产物: prompt_render.md / output.md / raw.json / db_writes.md")
    print(f"      DB 写入: {len(aligned)} rows in extracted")

    # 7. heartbeat.json (本机 push_state.ps1 读)
    try:
        hb = {
            "source": "feishu",
            "mode": MODE,
            "last_run_at": datetime.datetime.now(TZ).isoformat(timespec="seconds"),
            "last_status": "success",
            "last_duration_s": round(time.time() - start_ts),
            "last_batch_size": len(batch),
            "last_input_chars": sum(len(t) for _, _, t in batch),
            "last_tokens": {
                "in": usage.get("prompt_tokens", 0),
                "out": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            },
            "last_extracted_count": len(aligned),
        }
        hb_path = DATA_DIR / "heartbeat.json"
        hb_path.write_text(json.dumps(hb, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"       wrote {hb_path} (heartbeat)")
    except Exception as e:
        print(f"       WARN: heartbeat write failed: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
