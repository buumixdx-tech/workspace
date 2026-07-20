"""指数行情后台缓存 — 6 个固定指数,3s tick。

涵盖:
- A 股 3 个: 上证(sh000001) / 深成(sz399001) / 科创(sh000688) 走 eltdx
- 海外 3 个: 日经225(^N225) / 韩国 KOSPI(^KS11) / 台湾加权(^TWII) 走 yfinance

两路并行,失败互不影响;统一一个 dict 提供给前端,避免两条 GET 路径。
"""
from __future__ import annotations

import threading
import time

from src.core import get_client, remap_quote
from src.yf import get_quotes_batch

# —— 固定指数池 ————————————————————————————————————————
# 顺序就是前端显示顺序
INDICES: list[dict] = [
    # A 股 3 个 — 走 eltdx, code 用 eltdx 内部格式(无点号)
    {"key": "sh000001", "name": "上证",   "src": "eltdx"},
    {"key": "sz399001", "name": "深成",   "src": "eltdx"},
    {"key": "sh000688", "name": "科创",   "src": "eltdx"},
    # 海外 3 个 — 走 yfinance
    {"key": "^N225",    "name": "日经225", "src": "yf"},
    {"key": "^KS11",    "name": "韩国 KOSPI", "src": "yf"},
    {"key": "^TWII",    "name": "台湾加权",   "src": "yf"},
]

# 拆分给两个源,减少源内循环
ELTDX_CODES: list[str] = [it["key"] for it in INDICES if it["src"] == "eltdx"]
YF_CODES: list[str]    = [it["key"] for it in INDICES if it["src"] == "yf"]

POLL_INTERVAL_S = 3.0    # 和 QuoteCache 同 tick
COOLDOWN_S = 60.0        # 单源失败退避


class IndicesCache:
    def __init__(self) -> None:
        # key -> {"key": str, "name": str, "src": str, "quote": dict|None, "ts": float}
        self._data: dict[str, dict] = {
            it["key"]: {
                "key": it["key"],
                "name": it["name"],
                "src": it["src"],
                "quote": None,
                "ts": 0.0,
            }
            for it in INDICES
        }
        self._lock = threading.RLock()
        self._cooldown: dict[str, float] = {}   # src -> next_retry_ts
        self._stop = threading.Event()

    # —— 公开 API ————————————————————————————————————————

    def snapshot(self) -> list[dict]:
        """返回按 INDICES 顺序的指数快照列表 — 前端只读一次,直接渲染 6 列."""
        with self._lock:
            return [
                {
                    "key": d["key"],
                    "name": d["name"],
                    "src": d["src"],
                    "quote": d["quote"],
                }
                for d in (self._data[k] for k in [it["key"] for it in INDICES])
            ]

    def stats(self) -> dict:
        with self._lock:
            return {
                "tracked": len(self._data),
                "cached": sum(1 for d in self._data.values() if d["quote"] is not None),
            }

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self._run, daemon=True, name="IndicesCache")
        t.start()
        # 同步首次拉取 (cold start 不让前端看到空数据)
        try:
            self._refresh()
        except Exception as e:
            print(f"[indices_cache] initial refresh failed: {e}", flush=True)
        return t

    def stop(self) -> None:
        self._stop.set()

    # —— 内部 ——————————————————————————————————————————

    def _refresh_eltdx(self) -> None:
        now = time.time()
        with self._lock:
            if self._cooldown.get("eltdx", 0) > now:
                return

        try:
            client = get_client()
            snapshots = client.get_quote(ELTDX_CODES)
        except Exception as e:
            print(f"[indices_cache] eltdx batch failed: {e}", flush=True)
            with self._lock:
                self._cooldown["eltdx"] = time.time() + COOLDOWN_S
            return

        # 解析 — eltdx 返回 QuoteSnapshot dataclass,先 _clean 转 dict 再 remap
        from src.core import _clean
        now = time.time()
        with self._lock:
            self._cooldown.pop("eltdx", None)
            for snap in snapshots or []:
                clean = _clean(snap)
                if not clean:
                    continue
                # 索引快照同样走 remap_quote,字段一致 (last/change/change_pct/...)
                raw = (clean.get("exchange", "") + clean.get("code", "")).lower()
                target = next((k for k in ELTDX_CODES if k.lower() == raw), None)
                if not target:
                    continue
                q = remap_quote(clean)
                self._data[target]["quote"] = q
                self._data[target]["ts"] = now

    def _refresh_yf(self) -> None:
        now = time.time()
        with self._lock:
            if self._cooldown.get("yf", 0) > now:
                return

        try:
            results = get_quotes_batch(YF_CODES)  # dict[yf_sym -> dict|None]
        except Exception as e:
            print(f"[indices_cache] yf batch failed: {e}", flush=True)
            with self._lock:
                self._cooldown["yf"] = time.time() + COOLDOWN_S
            return

        now = time.time()
        with self._lock:
            self._cooldown.pop("yf", None)
            for code in YF_CODES:
                q = results.get(code)
                if q and q.get("last_price") is not None:
                    self._data[code]["quote"] = q
                    self._data[code]["ts"] = now

    def _refresh(self) -> None:
        # 两路并行 — 任一失败不影响另一路
        t1 = threading.Thread(target=self._refresh_eltdx, daemon=True)
        t2 = threading.Thread(target=self._refresh_yf, daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        s = self.stats()
        print(
            f"[indices_cache] refresh: tracked={s['tracked']} cached={s['cached']}",
            flush=True,
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._refresh()
            except Exception as e:
                print(f"[indices_cache] refresh error: {e}", flush=True)
            self._stop.wait(POLL_INTERVAL_S)


# 单例 — app.py 启动时 CACHE.start()
CACHE = IndicesCache()
