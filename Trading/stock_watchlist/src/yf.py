"""Yahoo Finance 行情接口 — 港股、美股、货币。"""
from __future__ import annotations

import urllib.request
import json
from typing import Any

YF_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def _fetch_json(symbol: str) -> dict | None:
    url = YF_CHART_URL.format(symbol=symbol)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def get_quote(code: str) -> dict[str, Any] | None:
    """
    获取单只标的行情。
    代码格式（Yahoo Finance 标准）：
      A股：sz000001, sh600000, bj430685（eltdx 格式，不走这里）
      港股：0700.HK, 2577.HK
      美股：AAPL, MSFT, GOOG
      指数：^HSI, ^IXIC
    """
    yf_symbol = _to_yf_symbol(code)
    if not yf_symbol:
        return None

    data = _fetch_json(yf_symbol)
    if not data:
        return None

    try:
        meta = data["chart"]["result"][0]["meta"]
    except (KeyError, IndexError):
        return None

    price = meta.get("regularMarketPrice")
    prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
    change = (price - prev_close) if (price is not None and prev_close is not None) else None
    change_pct = (change / prev_close) if (price is not None and prev_close and prev_close != 0) else None

    return {
        "last_price": price,
        "change": change,
        "change_pct": change_pct,
        "open": meta.get("regularMarketOpen") or meta.get("open"),
        "high": meta.get("regularMarketDayHigh") or meta.get("dayHigh"),
        "low": meta.get("regularMarketDayLow") or meta.get("dayLow"),
        "volume": meta.get("regularMarketVolume") or meta.get("volume"),
        "amount": None,
        "limit_up": None,
        "limit_down": None,
        "currency": meta.get("currency", "USD"),
        "market_state": meta.get("marketState", "REGULAR"),
        "exchange": _detect_exchange(code),
        "yf_symbol": yf_symbol,
        "long_name": meta.get("shortName") or meta.get("longName"),
    }


def _to_yf_symbol(code: str) -> str | None:
    """
    将各种格式转为 Yahoo Finance 格式。
    已经是 YF 格式的直接返回。
    hk00700 → 0700.HK
    usAAPL  → AAPL
    0700.HK → 0700.HK  (已是 YF 格式)
    AAPL    → AAPL     (已是 YF 格式)
    """
    code = code.strip()

    # 已经是 .HK 格式（港股 YF 格式）
    if code.endswith('.HK'):
        return code
    # 已经是纯大写字母数字（美股 YF 格式，如 AAPL, GOOG, ^HSI）
    if code.startswith('^') or (code[0].isupper() and code[0].isalpha() and not any(c.isdigit() for c in code)):
        return code
    if code.isupper() and code.isalnum() and not code.endswith('.HK'):
        return code

    # 旧格式转换
    c_lower = code.lower()
    if c_lower.startswith('hk'):
        inner = code[2:]  # 如 "00700"
        num = str(int(inner))  # 700
        return f"{num.zfill(4)}.HK"  # 0700.HK
    if c_lower.startswith('us'):
        return code[2:].upper()

    return None


def enrich_yf_quote(yf_data: dict | None, code: str) -> dict | None:
    """
    用当日第一根 5m K 线补全 yf_data 中缺失的字段：
    - open_price（今日开盘价）
    - amount（成交额）
    - prev_close（如缺失则用 last - change 推导）
    返回新的 dict，不修改原始输入。
    """
    if not yf_data:
        return None

    # 复制一份，避免修改原始数据
    q = dict(yf_data)

    # 补 prev_close
    if q.get("prev_close") is None and q.get("last_price") is not None and q.get("change") is not None:
        q["prev_close"] = round(q["last_price"] - q["change"], 3)

    # 补今日开盘价和成交额：需要 5m bars
    kline = get_kline(code, "5m", 100)
    if kline and kline.get("bars"):
        bars = kline["bars"]
        first = bars[0]
        if q.get("open") is None and first.get("open") is not None:
            q["open"] = first["open"]
        # 成交额 = Σ(close × volume)
        amount = sum((b.get("close") or 0) * (b.get("volume") or 0) for b in bars)
        if amount > 0:
            q["amount"] = round(amount, 2)

    return q


def get_kline(code: str, period: str = "1d", count: int = 300) -> dict | None:
    """
    获取 K 线数据（港美股）。
    period: 1d=日K, 1wk=周K, 1mo=月K, 5m/15m/30m/1h=分时
    返回格式与 eltdx bars 一致：{code, exchange, period, bars:[{time,open,close,high,low,volume}]}
    """
    yf_symbol = _to_yf_symbol(code)
    if not yf_symbol:
        return None

    # interval 映射
    interval_map = {"1d": "1d", "1wk": "1wk", "1mo": "1mo", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h"}
    interval = interval_map.get(period, "1d")

    # intra-day (分时) 用 range=1d，日线以上用 range=1y
    intra_day = interval.endswith("m") or interval == "1h"
    yf_range = "1d" if intra_day else "1y"

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}?interval={interval}&range={yf_range}&includePrePost=false"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None

    try:
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        adj_close = result["indicators"]["adjclose"][0]["adjclose"] if "adjclose" in result["indicators"] else None
        closes = adj_close or quote["close"]
    except (KeyError, IndexError):
        return None

    bars = []
    for i, ts in enumerate(timestamps):
        from datetime import datetime, timezone, timedelta
        # timestamps from YF are Unix seconds in UTC
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        bars.append({
            "time": dt_utc.isoformat(),
            "open": round(quote["open"][i], 3) if quote["open"][i] is not None else None,
            "close": round(closes[i], 3) if closes[i] is not None else None,
            "high": round(quote["high"][i], 3) if quote["high"][i] is not None else None,
            "low": round(quote["low"][i], 3) if quote["low"][i] is not None else None,
            "volume": int(quote["volume"][i]) if quote["volume"][i] is not None else 0,
        })

    return {
        "code": code,
        "exchange": _detect_exchange(code),
        "period": period,
        "bars": bars,
    }


def _detect_exchange(code: str) -> str:
    code = code.strip()
    if code.endswith('.HK'):
        return "HK"
    if code.startswith('^'):
        return "INDEX"
    # 美股：全大写字母，无数字或带数字
    if code.isupper() and code.isalnum():
        return "US"
    # 旧格式
    c_lower = code.lower()
    if c_lower.startswith('hk'):
        return "HK"
    if c_lower.startswith('us'):
        return "US"
    return "CN"


def get_quotes_batch(codes: list[str]) -> dict[str, dict | None]:
    """批量拉取多只 quote, 返回 {yf_symbol: data | None}。

    用 v7/finance/spark 批量 endpoint: ?symbols=A,B,C 一次拉多只, 无需鉴权。
    YF chart endpoint 不支持批量 (404), v6/v7 quote 需要 crumb, spark 是唯一可行方案。
    50 只一次 batch 拉到 vs 50 req/min, 提升 ~50x。
    """
    if not codes:
        return {}

    yf_syms: list[str] = []
    for code in codes:
        ys = _to_yf_symbol(code)
        if ys and ys not in yf_syms:  # 去重
            yf_syms.append(ys)
    if not yf_syms:
        return {}

    url = (
        f"https://query1.finance.yahoo.com/v7/finance/spark"
        f"?symbols={','.join(yf_syms)}&range=1d&interval=1d"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return {ys: None for ys in yf_syms}

    # spark 响应: {"spark": {"result": [{"symbol": ..., "response": [{"meta": {...}}]}, ...]}}
    try:
        result_list = data["spark"]["result"]
    except (KeyError, TypeError):
        return {ys: None for ys in yf_syms}

    # 用 symbol 建索引, 因为 YF 返回顺序可能跟请求顺序不一致
    by_symbol: dict[str, dict] = {}
    for r in result_list:
        sym = r.get("symbol")
        responses = r.get("response") or []
        if sym and responses:
            meta = responses[0].get("meta") or {}
            if meta:
                by_symbol[sym] = meta

    results: dict[str, dict | None] = {}
    for ys in yf_syms:
        meta = by_symbol.get(ys)
        if not meta:
            results[ys] = None
            continue
        price = meta.get("regularMarketPrice")
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
        if price is None:
            results[ys] = None
            continue
        change = (price - prev_close) if (price is not None and prev_close is not None) else None
        change_pct = (change / prev_close) if (change is not None and prev_close) else None
        results[ys] = {
            "last_price": price,
            "change": change,
            "change_pct": change_pct,
            "open": meta.get("regularMarketOpen") or meta.get("open"),
            "high": meta.get("regularMarketDayHigh") or meta.get("dayHigh"),
            "low": meta.get("regularMarketDayLow") or meta.get("dayLow"),
            "volume": meta.get("regularMarketVolume") or meta.get("volume"),
            "amount": None,
            "limit_up": None,
            "limit_down": None,
            "currency": meta.get("currency", "USD"),
            "market_state": meta.get("marketState", "REGULAR"),
            "exchange": "HK" if ys.endswith(".HK") else "US",
            "yf_symbol": ys,
            "long_name": meta.get("shortName") or meta.get("longName"),
        }
    return results
