#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重写窗口内 v3 旧 summary → v4 (不再 30 字硬截断, 允许 50 字完整句).

用法:
    # dry-run: 输出 md + json, 不写 db
    python scripts/rewrite_summaries_v4.py --dry-run

    # 真实 UPSERT (只覆盖 extracted.summary, 不动 category/stocks/terms):
    python scripts/rewrite_summaries_v4.py --apply

    # 自定义窗口:
    python scripts/rewrite_summaries_v4.py --dry-run --since '2026-06-29 15:00:00' --until '2026-06-30 12:30:00'

    # 只看特定 msg (调试):
    python scripts/rewrite_summaries_v4.py --dry-run --msg-ids 49947,49998

产出:
    - feishu_summary_rewrite_v4_dryrun.md   人看: OLD vs NEW 对比表
    - feishu_summary_rewrite_v4_dryrun.json 机读: items[msg_id, ts, info_type, summary_old, summary_new]

设计:
    - 单条模式走 v4 prompt (1-by-1, 不用 batch) — 调试粒度细, 失败易定位
    - dry-run 落 md + json
    - apply 走 UPSERT, 只覆盖 summary. category/stocks/terms 仅在 md 展示, 不进 db.
    - 不动 info_type (分类没改, v4 prompt 出来的应该跟 v3 一致; 万一不一致保留 v3 旧值 + warn)
    - 失败处理: 任意一条 LLM 失败 → summary_new=null, 不中断整批
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
APP_DIR = HERE.parent  # D:\workspace\LightRAG\apps\feishu_preprocess
sys.path.insert(0, str(APP_DIR))

from prompts.schemas import LLMInput, InputItem  # noqa: E402
from prompts.loader import load_prompt  # noqa: E402
from prompts.schemas import CODE_TO_LABELS  # noqa: E402

# ---------------------------------------------------------------------- #
# config                                                                  #
# ---------------------------------------------------------------------- #

DB = APP_DIR / "data" / "preprocess.db"
OUT_MD = APP_DIR / "feishu_summary_rewrite_v4_dryrun.md"
OUT_JSON = APP_DIR / "feishu_summary_rewrite_v4_dryrun.json"

TZ = _dt.timezone(_dt.timedelta(hours=8))
DEFAULT_SINCE = _dt.datetime(2026, 6, 29, 15, 0, 0, tzinfo=TZ)
DEFAULT_UNTIL = _dt.datetime(2026, 6, 30, 12, 30, 0, tzinfo=TZ)

DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# 真 key 必须从环境变量读: DASHSCOPE_API_KEY=sk-c5a451bf49e14da4929a0fc722242e13
# 不能写默认值 (U+2026 占位符会爆 UnicodeEncodeError, 见 MEMORY 2026-06-22 教训).
# 真值在 D:\workspace\LightRAG\secrets\rag_preprocess.env
def _get_dashscope_key() -> str:
    k = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not k:
        raise SystemExit("FAIL: DASHSCOPE_API_KEY env not set (真 key 在 D:\\workspace\\LightRAG\\secrets\\rag_preprocess.env)")
    if "\u2026" in k or "..." in k:
        raise SystemExit("FAIL: DASHSCOPE_API_KEY 含 U+2026 (horiz ellipsis) 占位符, 不是真 key")
    return k

# 只重写这几类 (有意义的个股/行业/产业/周报点评; 盘前/盘后/盘中提示/时政/段子/其他原 summary 本就空, 跳过)
REWRITE_INFO_TYPES = (1, 2, 3, 6)

# 单条调用超时
LLM_TIMEOUT = 30
# 单条重试
LLM_MAX_RETRY = 2


# ---------------------------------------------------------------------- #
# DB helpers                                                              #
# ---------------------------------------------------------------------- #


def parse_ts(s: str) -> int:
    """'YYYY-MM-DD HH:MM:SS' (Asia/Shanghai) → unix ms."""
    dt = _dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    dt = dt.replace(tzinfo=TZ)
    return int(dt.timestamp() * 1000)


def query_window(cur, since_ts: int, until_ts: int, msg_ids: list[int] | None) -> list[dict]:
    """拉窗口内 (since, until] 的 v3 已抽取行 (info_type 1/2/3/6, summary 非空)."""
    # extracted 表: msg_id/ts/info_type/category/summary/created_at
    # 没有 involved_stocks / core_tech_terms. 老 prompt 时期就不存这俩.
    # 本脚本只重写 summary, 不动 category. stocks/terms 仅在 md 里展示, 不进 db.
    if msg_ids:
        placeholders = ",".join("?" * len(msg_ids))
        rows = cur.execute(
            f"""
            SELECT m.id, m.ts, m.content, e.summary, e.info_type, e.category
            FROM messages m
            JOIN extracted e ON m.id = e.msg_id
            WHERE m.kind = 't' AND length(m.content) > 10
              AND e.info_type IN ({",".join(str(x) for x in REWRITE_INFO_TYPES)})
              AND m.id IN ({placeholders})
            ORDER BY m.ts ASC
            """,
            msg_ids,
        ).fetchall()
    else:
        rows = cur.execute(
            """
            SELECT m.id, m.ts, m.content, e.summary, e.info_type, e.category
            FROM messages m
            JOIN extracted e ON m.id = e.msg_id
            WHERE m.kind = 't' AND length(m.content) > 10
              AND e.info_type IN (1, 2, 3, 6)
              AND m.ts > ? AND m.ts <= ?
            ORDER BY m.ts ASC
            """,
            (since_ts, until_ts),
        ).fetchall()
    cols = ["id", "ts", "content", "summary", "info_type", "category"]
    return [dict(zip(cols, r)) for r in rows]


def upsert_one(con: sqlite3.Connection, row: dict, new_result: dict, info_type_v3: int) -> str:
    """UPSERT extracted — 只覆盖 summary (2026-06-30 buumi 不让补全 category/stocks/terms).
    info_type 保留 v3 旧值 (万一 v4 改了分类, warn 但不覆盖).
    返回 warn 字符串 (空表示无 warn)."""
    warn = ""
    new_it = int(new_result.get("info_type", info_type_v3))
    if new_it != info_type_v3:
        warn = f"info_type changed: v3={info_type_v3}({CODE_TO_LABELS.get(info_type_v3, '?')}) → v4={new_it}({CODE_TO_LABELS.get(new_it, '?')}) (KEEP v3)"

    summary = (new_result.get("summary") or "").strip()

    con.execute(
        """
        UPDATE extracted SET
            summary = ?
        WHERE msg_id = ?
        """,
        (summary, row["id"]),
    )
    return warn


# ---------------------------------------------------------------------- #
# LLM call (per-message, not batch — 调试粒度细)                          #
# ---------------------------------------------------------------------- #


def call_one(text: str, ts_ms: int) -> dict | None:
    """单条调 qwen3.5-flash 走 v4 prompt. 失败返回 None."""
    item = InputItem(idx=1, ts=ts_ms, text=text, orig_len=len(text))
    payload = LLMInput(count=1, items=[item])
    system, user, fm = load_prompt("historical", payload)

    if fm.get("version") != 4:
        print(f"  [WARN] prompt version={fm.get('version')} (expected 4), continue anyway")

    from openai import OpenAI
    client = OpenAI(api_key=_get_dashscope_key(), base_url=DASHSCOPE_BASE)

    last_err = None
    for attempt in range(1, LLM_MAX_RETRY + 1):
        try:
            resp = client.chat.completions.create(
                model="qwen3.5-flash",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                extra_body={"enable_thinking": False},
                timeout=LLM_TIMEOUT,
            )
            content = resp.choices[0].message.content
            data = json.loads(content)
            results = data.get("results") or []
            if not results:
                raise ValueError("empty results array")
            return results[0]
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"    [retry {attempt}/{LLM_MAX_RETRY}] {type(e).__name__}: {str(e)[:120]}")
            time.sleep(2 * attempt)
    print(f"  [FAIL] msg dropped after {LLM_MAX_RETRY} retries: {last_err}")
    return None


# ---------------------------------------------------------------------- #
# md render                                                               #
# ---------------------------------------------------------------------- #

# 中文标点判定完整句
_END_PUNCT = set("。;!?…\"))）,;!?、…")


def _is_complete_sentence(s: str) -> bool:
    if not s:
        return False
    return s.rstrip()[-1] in _END_PUNCT


def _check_keyword_coverage(orig_text: str, new_summary: str, top_n: int = 3) -> tuple[list[str], list[str]]:
    """从原文里捞 top_n 个高频"实体感" token (2-6 字连续汉字), 看新 summary 保留了多少."""
    import re
    # 简单: 提取 2-6 字的连续汉字块 (>=2 字才像实体)
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,6}", orig_text)
    if not cjk_chunks:
        return [], []
    # 频次
    from collections import Counter
    freq = Counter(cjk_chunks)
    top = [w for w, _ in freq.most_common(top_n * 4)]
    # 过滤: 太通用的字 (公司/股份/股票/产品/业务/市场/行业/经济/中国/全球/龙头/订单/亿元/亿元/万亿/看好/受益/增长/提升/驱动/逻辑/机会/空间/催化/关注/标的/加速/拐点/确认/超预期/反转/首次/深度/重点/核心/重要/关键/显著/明显/持续/不断/大幅/全面/加快/深入/加强/推进/进一步/持续/继续/不断/升级/迭代) 跳过
    noise = set("公司股份股票产品业务市场行业经济中国全球龙头订单亿元亿元万亿看好受益增长提升驱动逻辑机会空间催化关注标的加速拐点确认超预期反转首次深度重点核心重要关键显著明显持续不断大幅全面加快深入加强推进进一步继续不断升级迭代")
    top_clean = [w for w in top if w not in noise][:top_n]
    kept = [w for w in top_clean if w in new_summary]
    missed = [w for w in top_clean if w not in new_summary]
    return kept, missed


def render_md(plan: list[dict], since_str: str, until_str: str) -> str:
    """plan: [{"row", "new_result"|None, "warn", "applied"}]"""
    lines = [
        "# feishu_preprocess Summary Rewrite v3 → v4 (DRY RUN)",
        "",
        f"- Run at: {_dt.datetime.now(TZ).isoformat(timespec='seconds')}",
        f"- Window: {since_str} → {until_str} (Asia/Shanghai)",
        f"- DB: `{DB}`",
        f"- Prompt: `prompts/historical.md` v4 (summary 取消 30 字硬截断, 软上限 50)",
        f"- Mode: DRY RUN (no DB writes, this md only)",
        f"- Items: {len(plan)}",
        f"- LLM failures: {sum(1 for p in plan if p['new_result'] is None)}",
        "",
    ]

    # 汇总: 长度分布对比
    old_lens = [len(p["row"]["summary"]) for p in plan if p["new_result"] is not None]
    new_lens = [len(p["new_result"]["summary"]) for p in plan if p["new_result"] is not None]
    old_complete = sum(1 for p in plan if p["new_result"] is not None and _is_complete_sentence(p["row"]["summary"]))
    new_complete = sum(1 for p in plan if p["new_result"] is not None and _is_complete_sentence(p["new_result"]["summary"]))
    old_cap30 = sum(1 for p in plan if p["new_result"] is not None and len(p["row"]["summary"]) == 30)
    new_cap30 = sum(1 for p in plan if p["new_result"] is not None and len(p["new_result"]["summary"]) == 30)
    if old_lens:
        avg_old = sum(old_lens) / len(old_lens)
        avg_new = sum(new_lens) / len(new_lens)
        lines += [
            "## Aggregate",
            "",
            f"- 平均长度: v3={avg_old:.1f} → v4={avg_new:.1f}  (Δ={avg_new - avg_old:+.1f})",
            f"- 命中 30 字上限: v3={old_cap30} ({100*old_cap30/len(old_lens):.1f}%) → v4={new_cap30} ({100*new_cap30/len(new_lens):.1f}%)",
            f"- 完整句 (末尾中文标点): v3={old_complete} ({100*old_complete/len(old_lens):.1f}%) → v4={new_complete} ({100*new_complete/len(new_lens):.1f}%)",
            "",
        ]

    # Per-row trace
    lines += ["## Per-message trace", ""]
    for idx, p in enumerate(plan, 1):
        row = p["row"]
        new = p["new_result"]
        ts_str = _dt.datetime.fromtimestamp(row["ts"] / 1000, TZ).strftime("%Y-%m-%d %H:%M:%S")
        info_label = CODE_TO_LABELS.get(row["info_type"], str(row["info_type"]))

        lines.append(f"### [{idx}/{len(plan)}] msg_id={row['id']}  {ts_str}  info_type={row['info_type']}({info_label})")
        lines.append("")

        if new is None:
            lines.append(f"- [LLM FAIL] 跳过, 保留 v3 旧值")
            lines.append(f"- **OLD**: `{row['summary']}`  (len={len(row['summary'])})")
            lines.append("")
            continue

        new_sum = new["summary"]
        kept, missed = _check_keyword_coverage(row["content"], new_sum, top_n=3)

        lines += [
            f"- **OLD (v3)**: `{row['summary']}`  (len={len(row['summary'])}, 完整句={'Y' if _is_complete_sentence(row['summary']) else 'N 断头'})",
            f"- **NEW (v4)**: `{new_sum}`  (len={len(new_sum)}, 完整句={'Y' if _is_complete_sentence(new_sum) else 'N 断头'})",
            f"- **Δ len**: {len(new_sum) - len(row['summary']):+d}",
            f"- **category**: `{row['category'] or '(空)'}` → `{new.get('category') or '(空)'}`",
            f"- **stocks (v4 only)**: `{new.get('involved_stocks') or '[]'}`  (extracted 表无此列, 仅 md 展示)",
            f"- **terms (v4 only)**:  `{new.get('core_tech_terms') or '[]'}`  (extracted 表无此列, 仅 md 展示)",
            f"- **实体保留**: kept={kept}  missed={missed}",
        ]
        if p["warn"]:
            lines.append(f"- ⚠ {p['warn']}")
        lines.append("")

    return "\n".join(lines)


def render_json(plan: list[dict], since_str: str, until_str: str) -> dict:
    """极简 json — items 只含 msg_id/ts/info_type/summary (老 + 新)."""
    items = []
    for p in plan:
        row = p["row"]
        new = p["new_result"]
        item = {
            "msg_id": int(row["id"]),
            "ts": int(row["ts"]),
            "info_type": int(row["info_type"]),
            "summary_old": row["summary"],
            "summary_new": (new["summary"] if new else None),
        }
        items.append(item)
    return {
        "mode": "dry-run-or-apply",  # 上层 main() 会改这个
        "since": since_str,
        "until": until_str,
        "items": items,
    }


# ---------------------------------------------------------------------- #
# main                                                                    #
# ---------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(description="Rewrite v3 summaries in [since, until] window using v4 prompt")
    parser.add_argument("--dry-run", action="store_true", help="只输出 md, 不写 db (默认)")
    parser.add_argument("--apply", action="store_true", help="真实 UPSERT 到 db")
    parser.add_argument("--since", default=DEFAULT_SINCE.strftime("%Y-%m-%d %H:%M:%S"),
                        help="ISO 格式 'YYYY-MM-DD HH:MM:SS' (Asia/Shanghai)")
    parser.add_argument("--until", default=DEFAULT_UNTIL.strftime("%Y-%m-%d %H:%M:%S"),
                        help="ISO 格式 'YYYY-MM-DD HH:MM:SS' (Asia/Shanghai)")
    parser.add_argument("--msg-ids", default="", help="逗号分隔的 msg_id 列表 (调试用, 优先级高于 since/until)")
    parser.add_argument("--limit", type=int, default=0, help="最多处理多少条 (0=全部)")
    parser.add_argument("--out", default=str(OUT_MD), help="dry-run md 输出路径")
    parser.add_argument("--out-json", default=str(OUT_JSON), help="json 输出路径 (items 只含 msg_id/ts/info_type/summary)")
    args = parser.parse_args()

    if args.apply and args.dry_run:
        print("FAIL: --apply 和 --dry-run 不能同时给"); return 2
    apply = args.apply

    msg_ids = [int(x) for x in args.msg_ids.split(",") if x.strip()] if args.msg_ids else None

    since_ts = parse_ts(args.since)
    until_ts = parse_ts(args.until)
    print(f"[plan] window {args.since} → {args.until} (Asia/Shanghai)")
    print(f"[plan] mode={'APPLY (写 db)' if apply else 'DRY RUN (只出 md)'}")
    print(f"[plan] msg_ids={msg_ids or '(window scan)'}")
    print(f"[plan] limit={args.limit or '(all)'}")

    con = sqlite3.connect(str(DB))
    try:
        rows = query_window(con, since_ts, until_ts, msg_ids)
        if args.limit:
            rows = rows[: args.limit]
        print(f"[plan] rows to rewrite: {len(rows)}")
        if not rows:
            print("no rows in window, exit 0"); return 0

        plan: list[dict] = []
        started = time.time()
        for idx, row in enumerate(rows, 1):
            ts_str = _dt.datetime.fromtimestamp(row["ts"] / 1000, TZ).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{idx}/{len(rows)}] msg_id={row['id']}  {ts_str}  orig_len={len(row['content'])}  "
                  f"old_summary_len={len(row['summary'])}  ", end="", flush=True)

            t0 = time.time()
            new_result = call_one(row["content"], row["ts"])
            dt = time.time() - t0

            if new_result is None:
                print(f"[FAIL {dt:.1f}s]")
                plan.append({"row": row, "new_result": None, "warn": "LLM failed", "applied": False})
                continue

            new_summary = new_result.get("summary", "")
            print(f"[OK {dt:.1f}s]  new_len={len(new_summary)}  "
                  f"完整={'Y' if _is_complete_sentence(new_summary) else 'N'}")

            warn = ""
            applied = False
            if apply:
                warn = upsert_one(con, row, new_result, row["info_type"])
                if warn:
                    print(f"    [WARN] {warn}")
                applied = True

            plan.append({"row": row, "new_result": new_result, "warn": warn, "applied": applied})

        # dry-run 出 md / apply 也出 md 留痕 (md 加标记)
        md = render_md(plan, args.since, args.until)
        if apply:
            md = md.replace("# feishu_preprocess Summary Rewrite v3 → v4 (DRY RUN)",
                            "# feishu_preprocess Summary Rewrite v3 → v4 (APPLIED)")
            md = md.replace("- Mode: DRY RUN (no DB writes, this md only)",
                            f"- Mode: APPLIED — UPSERT 已写入 db ({len([p for p in plan if p['applied']])} 行)")
        out_path = Path(args.out)
        out_path.write_text(md, encoding="utf-8")
        print(f"\n[done] wrote {out_path} ({out_path.stat().st_size:,} bytes)")
        print(f"[done] elapsed: {time.time() - started:.1f}s")

        # 极简 json (items 只含 msg_id/ts/info_type/summary_old/summary_new)
        json_obj = render_json(plan, args.since, args.until)
        json_obj["mode"] = "apply" if apply else "dry-run"
        json_path = Path(args.out_json)
        json_path.write_text(
            json.dumps(json_obj, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[done] wrote {json_path} ({json_path.stat().st_size:,} bytes)")

        if apply:
            con.commit()
            print(f"[done] committed {sum(1 for p in plan if p['applied'])} UPSERTs to extracted")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())