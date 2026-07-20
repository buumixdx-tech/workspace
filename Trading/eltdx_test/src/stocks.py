"""A 股代码表管理：自动拉取、缓存、智能搜索。

设计要点：
1. 服务启动时检查 cache_file，超过 max_age_hours 则重新拉取
2. 拉取失败时降级用旧缓存（保证可用性）
3. 预计算每只股票的拼音首字母（pinyin_abbr），支持模糊搜索
4. 搜索匹配 4 个字段：code / name / pinyin_abbr / board，按相关性打分
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


# —— 拼音首字母工具 ——————————————————————————————————————

_NON_CHINESE_PATTERN = re.compile(r"[^一-鿿]")


def _pinyin_abbr(name: str) -> str:
    """中文名 → 拼音首字母（小写）。

    例: '平安银行' → 'payx'，'中国平安' → 'zgpa'，'浦发银行' → 'pfyh'
    非汉字（数字/字母）保留原字符。
    """
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


# —— 拉取 / 加载 / 保存 ————————————————————————————————

def _cache_path() -> Path:
    p = Path(STOCKS_CACHE_FILE)
    if not p.is_absolute():
        # 相对项目根
        p = Path(__file__).resolve().parent.parent / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _fetch_from_eltdx() -> list[dict]:
    """从 eltdx 拉取全市场 A 股（category == 'a_share'）。"""
    # 局部导入避免循环依赖
    from src.core import get_client

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
                code = f"{x.exchange}{x.code}"
                name = x.name or ""
                result.append({
                    "code": code,
                    "exchange": x.exchange,
                    "market_id": x.market_id,
                    "name": name,
                    "name_pinyin": _pinyin_abbr(name),
                    "board": x.board,
                    "previous_close": x.previous_close_price,
                })
            if len(chunk) < 1600:
                break
            start += len(chunk)
    return result


def _load_cache() -> dict | None:
    """从磁盘读缓存（含 updated_at）。"""
    p = _cache_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(stocks: list[dict]) -> None:
    """写缓存。"""
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


# —— 公开 API：ensure / list / search ——————————————————————

_lock = Lock()
_cache: dict | None = None


def ensure_fresh() -> dict:
    """服务启动时调用：保证缓存是最新的。

    触发刷新条件（满足任一）：
      1. 缓存不存在
      2. force_refresh_on_start = true
      3. 缓存年龄超过 max_age_hours

    刷新失败时降级返回旧缓存。
    """
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
                print(
                    f"[stocks] 降级使用旧缓存 ({cache.get('count', '?')} 只)",
                    file=sys.stderr,
                )
                _cache = cache
                return _cache
            raise


def get_meta() -> dict:
    """返回元信息：{updated_at, count, source}。"""
    data = ensure_fresh()
    return {
        "updated_at": data["updated_at"],
        "count": data["count"],
        "source": data["source"],
    }


def get_all() -> list[dict]:
    data = ensure_fresh()
    return data["stocks"]


# —— 智能搜索 ————————————————————————————————————————

def search(query: str, limit: int = 20) -> list[dict]:
    """模糊搜索股票。

    匹配字段：
      - code（完整代码 / 6位数字）
      - name（中文名 / 子串）
      - name_pinyin（拼音首字母 / 子串）

    打分：
      - 100: code 精确匹配（如 "sh600000"）
      - 90:  code 前缀匹配（如 "600000"）
      - 80:  name 完全匹配
      - 70:  pinyin 前缀匹配（如 "pay" 匹配 payx）
      - 60:  name 子串包含
      - 50:  pinyin 子串包含
      - 40:  中文名任意字包含
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
        py = s["name_pinyin"]

        score = 0
        matched_field = None

        # 1. code 匹配
        if code == q:
            score = 100
            matched_field = "code"
        elif is_pure_digits and code.lstrip("szsh") == q:
            score = 95
            matched_field = "code6"
        elif is_pure_digits and code.endswith(q):
            score = 90
            matched_field = "code_suffix"

        # 2. name 完全匹配
        if score < 80 and name == q:
            score = 80
            matched_field = "name"

        # 3. pinyin 前缀
        if score < 70 and py.startswith(q):
            score = 70
            matched_field = "pinyin_prefix"

        # 4. name 子串
        if score < 60 and q in name:
            score = 60
            matched_field = "name_sub"

        # 5. pinyin 子串
        if score < 50 and q in py:
            score = 50
            matched_field = "pinyin_sub"

        # 6. 汉字任意字
        if score < 40 and len(q) == 1 and q in name:
            score = 40
            matched_field = "char"

        if score > 0:
            r = dict(s)
            r["_score"] = score
            r["_match"] = matched_field
            results.append(r)

    # 排序：分数降序 → 代码升序
    results.sort(key=lambda x: (-x["_score"], x["code"]))
    return results[:limit]