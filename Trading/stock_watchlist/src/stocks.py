"""股票管理：本地缓存 + eltdx 搜索/补全 + 实时行情。

复用 eltdx_test/stocks.py 的拼音搜索逻辑，但移除了对 watchlist 业务的直接
依赖（eltdx_test 依赖 eltdx_test/stocks.py 是可以的，但这里独立实现更干净）。
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Lock

from pypinyin import lazy_pinyin

from src.config_loader import (
    STOCKS_CACHE_FILE,
    STOCKS_FORCE_REFRESH,
    STOCKS_MAX_AGE_HOURS,
)
from src.core import (
    board_display_name,
    get_client,
    normalize_code,
    normalize_code_ck,
)


# —— 拼音首字母工具 ————————————————————————————————————————

_NON_CHINESE_PATTERN = re.compile(r"[^一-鿿]")


def _pinyin_abbr(name: str) -> str:
    """中文名 → 拼音首字母（小写）。"""
    if not name:
        return ""
    parts = lazy_pinyin(name)
    abbr = []
    for ch, py in zip(name, parts):
        if _NON_CHINESE_PATTERN.match(ch):
            abbr.append(ch.lower())
        elif py:
            abbr.append(py[0].lower())
    return "".join(abbr)


# —— 缓存 ————————————————————————————————————————

def _cache_path() -> Path:
    p = Path(STOCKS_CACHE_FILE)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _fetch_from_eltdx() -> list[dict]:
    """从 eltdx 拉取全市场 A 股。"""
    client = get_client()
    result: list[dict] = []
    for exchange in ("SZ", "SH"):
        start = 0
        while True:
            chunk = client.codes.list(exchange, start=start, limit=1600)
            if not chunk:
                break
            for x in chunk:
                if x.category != "a_share":
                    continue
                code = f"{x.exchange.lower()}{x.code}"
                name = x.name or ""
                result.append({
                    "code": code,
                    "exchange": x.exchange.lower(),
                    "market_id": x.market_id,
                    "name": name,
                    "name_pinyin": _pinyin_abbr(name),
                    "board": x.board,
                    "board_name": board_display_name(x.board),
                    "previous_close": x.previous_close_price,
                })
            if len(chunk) < 1600:
                break
            start += len(chunk)
    return result


def _load_cache() -> dict | None:
    p = _cache_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(stocks: list[dict]) -> None:
    p = _cache_path()
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(stocks),
        "source": "eltdx",
        "stocks": stocks,
    }
    p.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[stocks] 已保存 {len(stocks)} 只 A 股到 {p}", file=sys.stderr)


def _age_hours(cache: dict) -> float:
    try:
        ts = datetime.fromisoformat(cache["updated_at"])
        return (datetime.now() - ts).total_seconds() / 3600
    except Exception:
        return float("inf")


# —— 模块级缓存 ————————————————————————————————————————

_lock = Lock()
_cache: dict | None = None


def ensure_fresh() -> dict:
    """确保代码表缓存最新。"""
    global _cache
    with _lock:
        if _cache is not None:
            return _cache

        cache = _load_cache()
        need_refresh = (
            cache is None
            or STOCKS_FORCE_REFRESH
            or _age_hours(cache) > STOCKS_MAX_AGE_HOURS
        )

        if not need_refresh:
            _cache = cache
            print(
                f"[stocks] 使用缓存 ({cache['count']} 只, "
                f"更新于 {cache['updated_at']})",
                file=sys.stderr,
            )
            return _cache

        try:
            print("[stocks] 正在从 eltdx 拉取全市场 A 股代码表 ...", file=sys.stderr)
            t0 = time.time()
            stocks = _fetch_from_eltdx()
            _save_cache(stocks)
            print(
                f"[stocks] 拉取完成 {len(stocks)} 只, 耗时 {time.time()-t0:.1f}s",
                file=sys.stderr,
            )
            _cache = {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "count": len(stocks),
                "source": "eltdx",
                "stocks": stocks,
            }
            return _cache
        except Exception as e:
            print(f"[stocks] 拉取失败：{e}", file=sys.stderr)
            if cache is not None:
                _cache = cache
                return _cache
            raise


def get_all() -> list[dict]:
    data = ensure_fresh()
    return data["stocks"]


# —— 搜索 ————————————————————————————————————————

def search(query: str, limit: int = 20) -> list[dict]:
    """模糊搜索股票（本地缓存）。

    匹配：code / name / name_pinyin，支持子串。
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    stocks = get_all()
    is_pure_digits = q.isdigit() and len(q) >= 4
    results = []

    for s in stocks:
        code = s["code"].lower()
        name = s["name"]
        py = s.get("name_pinyin", "")

        score = 0
        matched_field = None

        if code == q:
            score, matched_field = 100, "code"
        elif is_pure_digits and code.lstrip("szshbj") == q:
            score, matched_field = 95, "code6"
        elif is_pure_digits and code.endswith(q):
            score, matched_field = 90, "code_suffix"
        elif score < 80 and name == q:
            score, matched_field = 80, "name"
        elif score < 70 and py.startswith(q):
            score, matched_field = 70, "pinyin_prefix"
        elif score < 60 and q in name:
            score, matched_field = 60, "name_sub"
        elif score < 50 and q in py:
            score, matched_field = 50, "pinyin_sub"
        elif score < 40 and len(q) == 1 and q in name:
            score, matched_field = 40, "char"

        if score > 0:
            r = dict(s)
            r["_score"] = score
            r["_match"] = matched_field
            results.append(r)

    results.sort(key=lambda x: (-x["_score"], x["code"]))
    return results[:limit]


# —— 股票增删查 ————————————————————————————————————————

def add_stock(code: str) -> dict:
    """将股票添加到本地自选表（从 eltdx 补全 name/board）。
    存储格式：A 股为 CK 标准（sz.000001），港美股走 YF 格式。
    """
    from src.db import upsert_stock, get_stock

    # 转为 CK 标准格式（带点号）用于存储
    ck_code = normalize_code_ck(code)
    # eltdx API 需要无点号格式（如 sz000001）
    api_code = ck_code.replace(".", "")

    # 优先复用本地缓存
    stocks_cache = get_all()
    found = next((s for s in stocks_cache if s["code"] == ck_code), None)

    if found:
        stock = upsert_stock({
            "code": ck_code,
            "exchange": ck_code[:2],
            "name": found["name"],
            "board": found.get("board"),
            "board_name": found.get("board_name"),
        })
    else:
        # 缓存未命中，查 eltdx
        client = get_client()
        try:
            profiles = client.helpers.stock_profile_table([api_code])
        except Exception as e:
            raise ValueError(f"eltdx 查询失败：{e}")

        if not profiles.rows:
            raise ValueError(f"股票 {api_code} 不存在或不在支持范围内")

        profile = profiles.rows[0]
        stock = upsert_stock({
            "code": ck_code,
            "exchange": ck_code[:2],
            "name": profile.name,
            "board": getattr(profile, "board", None),
            "board_name": board_display_name(getattr(profile, "board", None)),
        })

    return stock


def get_stock_info(code: str, quote_override: dict | None = None) -> dict | None:
    """返回本地缓存的股票信息 + eltdx 实时行情快照。

    quote_override: 如果提供, 跳过 eltdx 调用, 直接使用 (已 remap 后的 dict)。
    用于路由层复用 _enrich_stocks 批量拉过的 quote, 避免重复 eltdx 单只调用。
    """
    from src.db import get_stock
    from src.core import _clean, get_price_limit_pct, remap_quote

    # 存储格式可能是 CK 标准（sz.000001），eltdx API 需要无点号
    ck_code = normalize_code_ck(code)
    api_code = ck_code.replace(".", "")  # eltdx 用 sz000001
    local = get_stock(ck_code)
    if not local:
        # 本地没有，尝试 upsert 后再查
        try:
            add_stock(ck_code)
        except Exception:
            pass
        local = get_stock(ck_code)
        if not local:
            return None

    # 尝试获取 eltdx 实时行情
    # 注意：bj 股票 get_quote 不支持，需用 stock_profile_table
    quote = None
    try:
        client = get_client()
        if ck_code.startswith("bj."):
            # bj 股票用 stock_profile_table
            profiles = client.helpers.stock_profile_table([api_code])
            if profiles.rows:
                p = profiles.rows[0]
                quote = _clean(p.quote) if hasattr(p, "quote") and p.quote else _clean(p)
        else:
            snapshots = client.get_quote([api_code])
            if snapshots:
                quote = _clean(snapshots[0])
    except Exception:
        pass

    # quote_override 命中 → 跳过 eltdx, 复用 _enrich_stocks 批量拉过的 quote
    if quote_override is not None:
        return {
            **local,
            "limit_pct": get_price_limit_pct(ck_code),
            "quote": quote_override,
        }

    return {
        **local,
        "limit_pct": get_price_limit_pct(ck_code),
        "quote": remap_quote(quote),
    }
