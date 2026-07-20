"""eltdx 客户端封装：单例、数据类 → dict 序列化。

设计要点：
1. 单例 `TdxClient` —— 模块加载时创建一次，复用连接与心跳
2. 序列化时剔除 `_raw` / `raw_payload` / `tail_raw` / `hex` 等二进制噪音字段
3. 保留所有人类可读字段，让 UI 完整呈现实时行情
"""

from __future__ import annotations

import sys
import threading
from typing import Any

from eltdx import TdxClient

from src.config_loader import (
    TDX_HEARTBEAT,
    TDX_HOSTS,
    TDX_PROBE_HOSTS,
    TDX_TIMEOUT,
)


# —— 单例（线程安全） ——————————————————————————————————————

_client: TdxClient | None = None
_lock = threading.Lock()


def get_client() -> TdxClient:
    """获取全局唯一的 TdxClient。第一次调用时构造（含心跳）。"""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = TdxClient(
                    hosts=TDX_HOSTS,
                    timeout=TDX_TIMEOUT,
                    heartbeat_interval=TDX_HEARTBEAT,
                    probe_hosts=TDX_PROBE_HOSTS,
                )
                _client.connect()
                print(
                    f"[core] TdxClient 已连接 (hosts={TDX_HOSTS}, "
                    f"timeout={TDX_TIMEOUT}s)",
                    file=sys.stderr,
                )
    return _client


# —— 字段清洗：剔除二进制 / 调试噪音 ————————————————————

# 已知不应暴露给前端的字段（bytes、长二进制 hex 等）
_NOISE_KEYS = {
    "tail_raw",
    "raw_payload",
    "decoded_payload",
    "record_hex",
    "reserved_zero",
    "date_selector_raw",
    "open_amount_raw",
    "amount_raw",
    "unknown_after_time_raw",
    "unknown_after_outer_raw",
    "price_field",
    "avg_field",
    "price_raw",
    "avg_raw",
    "price_delta_raw",
    "aux_delta_raw",
    "open_amount_yuan",  # 与 amount 重复
}


def _clean(obj: Any) -> Any:
    """递归清洗数据类 / 容器。"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, bytes):
        return None  # 丢弃二进制
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if k not in _NOISE_KEYS and not k.endswith("_raw")}
    if isinstance(obj, (list, tuple)):
        return [_clean(x) for x in obj]
    # dataclass（带 __slots__ 或 __dict__）
    if hasattr(obj, "__dataclass_fields__"):
        return {
            k: _clean(getattr(obj, k))
            for k in obj.__dataclass_fields__
            if k not in _NOISE_KEYS and not k.endswith("_raw")
        }
    # 普通对象
    if hasattr(obj, "__dict__"):
        return {
            k: _clean(v)
            for k, v in obj.__dict__.items()
            if k not in _NOISE_KEYS and not k.endswith("_raw")
        }
    return str(obj)


# —— 业务封装：行情 / 分时 / 五档 ————————————————————————

def normalize_code(code: str) -> str:
    """`000001` / `sz000001` / `SH600000` → `sz000001`."""
    code = code.strip().lower()
    if code.startswith(("sz", "sh")):
        return code
    if code.startswith(("6", "9", "5")):
        return "sh" + code
    if code.startswith(("0", "1", "2", "3")):
        return "sz" + code
    return code


def get_price_limit_pct(code: str) -> float:
    """根据股票代码前缀，返回单日涨跌停幅度（小数，0.10 表示 ±10%）。

    A 股规则（不考虑 ST 个股）：
      - 主板 (60xxxx / 000xxx / 001xxx / 002xxx)：±10%
      - 创业板 (300xxx / 301xxx)：±20%
      - 科创板 (688xxx)：±20%
      - 北交所 (8xxxxx / 4xxxxx / 92xxxx)：±30%
    """
    code = code.lower()
    pure = code[2:] if code.startswith(("sz", "sh")) else code

    if pure.startswith(("300", "301")):
        return 0.20  # 创业板
    if pure.startswith("688"):
        return 0.20  # 科创板
    if pure.startswith(("8", "43", "83", "87", "92")):
        return 0.30  # 北交所
    return 0.10      # 主板默认


def fetch_quote(code: str) -> dict:
    """实时报价。"""
    client = get_client()
    snapshots = client.get_quote([normalize_code(code)])
    if not snapshots:
        return {"ok": False, "error": f"未取到 {code} 的报价"}
    q = snapshots[0]
    return {
        "ok": True,
        "data": _clean(q),
    }


def fetch_minute(code: str) -> dict:
    """当日分时。"""
    client = get_client()
    series = client.get_minute(normalize_code(code))
    # MinuteSeries 自带 code / prev_close / points[]
    data = _clean(series)
    # 字段重命名，UI 友好
    data["ok"] = True
    return data


def fetch_depth(code: str) -> dict:
    """五档盘口。"""
    client = get_client()
    depth = client.get_quote_depth(normalize_code(code))
    data = _clean(depth)
    data["ok"] = True
    return data


def fetch_kline(code: str, period: str = "day", count: int = 500, adjust: str = "qfq") -> dict:
    """K 线（服务端复权，推荐）。"""
    client = get_client()
    # 使用服务端复权（adjust_mode_raw 写到协议帧里）
    series = client.bars.get(
        normalize_code(code),
        period=period,
        count=count,
        adjust=adjust,
    )
    bars = []
    for b in series.bars:
        bars.append({
            "time": b.time.isoformat() if b.time else None,
            "open": b.open,
            "close": b.close,
            "high": b.high,
            "low": b.low,
            "volume": b.volume_lots,  # 单位「手」
            "amount": b.amount,       # 单位「元」
        })
    return {
        "ok": True,
        "data": {
            "code": series.code,
            "exchange": series.exchange,
            "period": series.period_name,
            "adjust_mode": series.adjust_mode,
            "count": series.count,
            "bars": bars,
        },
    }


def fetch_all(code: str) -> dict:
    """一次拉取报价+分时+五档。前端轮询主入口。"""
    normalized = normalize_code(code)
    out = {
        "code": normalized,
        "ok": True,
        "errors": [],
        "limit_pct": get_price_limit_pct(normalized),  # 涨跌停幅度（用于图表 Y 轴）
    }

    try:
        q = fetch_quote(normalized)
        if q["ok"]:
            out["quote"] = q["data"]
        else:
            out["errors"].append(f"quote: {q['error']}")
    except Exception as e:
        out["errors"].append(f"quote: {e}")

    try:
        m = fetch_minute(normalized)
        if m.get("ok"):
            out["minute"] = {
                "code": m.get("code"),
                "exchange": m.get("exchange"),
                "trading_date": m.get("trading_date"),
                "prev_close": m.get("prev_close"),
                "open_price": m.get("open_price"),
                "volume_sum": m.get("volume_sum"),
                "count": m.get("count"),
                "points": m.get("points", []),
            }
        else:
            out["errors"].append("minute: 无数据")
    except Exception as e:
        out["errors"].append(f"minute: {e}")

    try:
        d = fetch_depth(normalized)
        if d.get("ok"):
            out["depth"] = {
                "requested_codes": d.get("requested_codes"),
                "count": d.get("count"),
                "records": d.get("records", []),
            }
        else:
            out["errors"].append("depth: 无数据")
    except Exception as e:
        out["errors"].append(f"depth: {e}")

    out["ok"] = len(out["errors"]) == 0
    return out