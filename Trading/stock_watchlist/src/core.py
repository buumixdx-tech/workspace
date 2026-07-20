"""eltdx 客户端封装：单例 + 字段清洗 + normalize_code。
复用 eltdx_test 的 core.py 模式。
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


# —— 字段清洗 ————————————————————————————————————————

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
    "open_amount_yuan",
}


def _clean(obj: Any) -> Any:
    """递归清洗数据类 / 容器，剔除二进制噪音字段。"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, bytes):
        return None
    if isinstance(obj, dict):
        return {
            k: _clean(v)
            for k, v in obj.items()
            if k not in _NOISE_KEYS and not k.endswith("_raw")
        }
    if isinstance(obj, (list, tuple)):
        return [_clean(x) for x in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {
            k: _clean(getattr(obj, k))
            for k in obj.__dataclass_fields__
            if k not in _NOISE_KEYS and not k.endswith("_raw")
        }
    if hasattr(obj, "__dict__"):
        return {
            k: _clean(v)
            for k, v in obj.__dict__.items()
            if k not in _NOISE_KEYS and not k.endswith("_raw")
        }
    return str(obj)


def remap_quote(q: dict) -> dict:
    """将 eltdx 行情字段映射为 UI 期望的字段名。

    涨跌停价由 src/limit_price.calc_limit 本地按 2026-07-06 新规则计算
    (eltdx 不直接给普通 A 股的涨跌停价;只能拿到 pre_close + code).
    """
    if not q:
        return q
    last = q.get("last_price")
    prev = q.get("pre_close_price")
    volume = q.get("total_hand")

    # —— 停牌检测 ——
    # eltdx 对停牌股的 last_price 给 0(不是 None),配合 volume=0 / prev>0,
    # 不去识别就会在前端算出 change=-prev / change_pct=-100% 的假跌停。
    # 启发式: last == 0 且 prev > 0(且没有开盘价/最高价) → 停牌。
    is_suspended = (
        last == 0 and prev is not None and prev > 0 and (
            q.get("open_price") in (None, 0) or volume in (None, 0)
        )
    )
    if is_suspended:
        last = None
        change = None
        change_pct = None

    change = (last - prev) if (last is not None and prev is not None) else change
    change_pct = (change / prev) if (change is not None and prev and prev != 0) else (None if not is_suspended else None)

    # —— 计算涨跌停价 ——
    # eltdx QuoteSnapshot.code 是裸 6 位 ('300323'), 需用 normalize_code_ck 转 'sz.300323' 给 plate_of
    from src.limit_price import calc_limit
    raw_code = q.get("code") or q.get("full_code")
    code_ck = normalize_code_ck(raw_code) if raw_code else None
    limit_up, limit_down = calc_limit(prev, code_ck)

    return {
        "last_price": last,
        "change": change,
        "change_pct": change_pct,
        "open": q.get("open_price"),
        "high": q.get("high_price"),
        "low": q.get("low_price"),
        "volume": q.get("total_hand"),
        "amount": q.get("amount"),
        "limit_up": limit_up,
        "limit_down": limit_down,
        "code": code_ck or raw_code,
        "pre_close": prev,
        "is_suspended": is_suspended,
    }


# —— 工具函数 ————————————————————————————————————————

def normalize_code(code: str) -> str:
    """`000001` / `sz000001` / `SH600000` → `sz000001` / `sh600000`."""
    code = code.strip().lower()
    if code.startswith(("sz", "sh", "bj")):
        return code
    if code.startswith(("6", "9", "5", "8")):
        return "sh" + code
    if code.startswith(("0", "1", "2", "3", "4")):
        return "sz" + code
    return code


def normalize_code_ck(code: str) -> str:
    """统一 A 股代码为 CK 标准格式（带点号）。
    A 股：sz.000001 / sh.600000 / bj.430685
    港股：0700.HK（Yahoo Finance 格式）
    美股：AAPL（保持大写）
    """
    code = code.strip()

    # 港股 YF 格式：原样返回
    if code.endswith(".HK"):
        return code

    # 已是 CK 格式：纠正北交所（sz.920xxx / sh.920xxx → bj.920xxx）
    if "." in code:
        suffix = code.split(".")[-1]
        if suffix.startswith("92"):
            return "bj." + suffix
        return code

    # 纯数字（6位）
    digits = code.zfill(6)
    if digits.isdigit():
        if digits.startswith("92"):
            return f"bj.{digits}"
        if digits.startswith("9"):
            return f"sh.{digits}"
        normalized = normalize_code(digits)
        return f"{normalized[:2]}.{normalized[2:]}"

    # 美股（纯字母）：保持大写，不转换
    if code.isalpha():
        return code.upper()

    # 无点号标准格式（sz000001 / sh600000）
    normalized = normalize_code(code)
    if len(normalized) == 8:
        if normalized[2:].startswith("92"):
            return f"bj.{normalized[2:]}"
        return f"{normalized[:2]}.{normalized[2:]}"
    return code


def get_price_limit_pct(code: str) -> float:
    """根据股票代码前缀，返回单日涨跌停幅度（小数）。"""
    code = code.lower()
    pure = code[2:] if code.startswith(("sz", "sh", "bj")) else code

    if pure.startswith(("300", "301")):
        return 0.20
    if pure.startswith("688"):
        return 0.20
    if pure.startswith(("8", "43", "83", "87", "92")):
        return 0.30
    return 0.10


_BOARD_NAMES = {
    "sse_main_board": "沪主板",
    "sse_star_market": "科创板",
    "szse_main_board": "深主板",
    "szse_chinext": "创业板",
    "bj_main_board": "北交所",
    "bse_listed_stock": "北交所",
}


def board_display_name(board: str | None) -> str:
    """板块标识 → 中文显示名。"""
    if not board:
        return "未知"
    return _BOARD_NAMES.get(board, board)
