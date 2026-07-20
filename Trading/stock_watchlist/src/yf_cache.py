"""YF 行情缓存 — 后台线程定时拉取 watchlist, 内存缓存, 路由直接读。

设计目标:
- YF 限流约 100 req/min, 通过 batch endpoint 把 N 只股票压成 1-2 个请求
- 拉取范围: sector_stocks 中所有 HK/US 股票（去重）— 用户真正的 watchlist
- 失败 cooldown: 单只股票失败 60s 后才重试, 避免持续打 YF
- 新增股票: 下一次 tick 立即拉, 不等 30s
- 已删除股票: 立刻从 cache 清除

升级路径: 未来上多 worker / 多端时, 把 CACHE 拆成独立 daemon 进程,
       业务代码 (CACHE.get) 不动。
"""
from __future__ import annotations

import threading
import time

from src.db import get_watchlist_yf_codes
from src.yf import get_quotes_batch

# 配置常量
POLL_INTERVAL_S = 30  # 拉取间隔
COOLDOWN_S = 60       # 失败退避
BATCH_SIZE = 15       # 单次 batch 上限（YF spark 超过 15 会静默丢 symbol, 实测 n=20 丢 3 个）


class YfCache:
    def __init__(self) -> None:
        self._quotes: dict[str, dict] = {}      # yf_sym -> quote data
        self._ts: dict[str, float] = {}         # yf_sym -> last fetch ts
        self._cooldown: dict[str, float] = {}   # yf_sym -> next_retry_ts
        self._known_codes: set[str] = set()
        self._lock = threading.RLock()
        self._stop = threading.Event()

    # —— 公开 API ————————————————————————————————————————

    def get(self, yf_sym: str) -> dict | None:
        """路由调用: 直接拿 cache, < 1ms."""
        with self._lock:
            return self._quotes.get(yf_sym)

    def snapshot(self) -> dict[str, dict]:
        """一次性拿整张 _quotes 快照 — I6: enrich N 次 lock acquire → 1 次.

        返回 dict 的浅拷贝;调用方用完即弃。线程安全。
        """
        with self._lock:
            return dict(self._quotes)

    def get_age(self, yf_sym: str) -> float | None:
        """返回距上次拉取的秒数, None 表示没拉过."""
        with self._lock:
            ts = self._ts.get(yf_sym)
            return (time.time() - ts) if ts else None

    def stats(self) -> dict:
        with self._lock:
            return {
                "tracked": len(self._known_codes),
                "cached": len(self._quotes),
                "cooldown": len(self._cooldown),
            }

    def start(self) -> threading.Thread:
        """启动后台 refresh 线程（daemon=True, 主进程退出自动死）."""
        t = threading.Thread(target=self._run, daemon=True, name="YfCache")
        t.start()
        # 同步首次拉取（不等 30s, 避免路由 cold start 返回空）
        try:
            self._refresh()
        except Exception as e:
            print(f"[yf_cache] initial refresh failed: {e}", flush=True)
        return t

    def stop(self) -> None:
        self._stop.set()

    # —— 内部 ——————————————————————————————————————————

    def _scan_watchlist(self) -> list[str]:
        try:
            return get_watchlist_yf_codes()
        except Exception as e:
            print(f"[yf_cache] watchlist scan failed: {e}", flush=True)
            # scan 失败保留旧 known_codes, 不丢 cache
            return list(self._known_codes)

    def _refresh(self) -> None:
        codes = self._scan_watchlist()
        now = time.time()
        code_set = set(codes)

        # 1. 已删除的股票立刻从 cache 清除
        with self._lock:
            removed = self._known_codes - code_set
            for c in removed:
                self._quotes.pop(c, None)
                self._ts.pop(c, None)
                self._cooldown.pop(c, None)

        # 2. 决定要拉取的: 所有未在 cooldown 的
        with self._lock:
            to_fetch = [c for c in codes if self._cooldown.get(c, 0) < now]

        if not to_fetch:
            self._known_codes = code_set
            return

        # 3. 分批拉取
        new_quotes: dict[str, dict | None] = {}
        for i in range(0, len(to_fetch), BATCH_SIZE):
            batch = to_fetch[i:i + BATCH_SIZE]
            try:
                results = get_quotes_batch(batch)
                new_quotes.update(results)
            except Exception as e:
                print(f"[yf_cache] batch fetch failed: {e}", flush=True)
                with self._lock:
                    for c in batch:
                        self._cooldown[c] = now + COOLDOWN_S

        # 4. 写入 cache, 失败的进 cooldown
        with self._lock:
            for code, data in new_quotes.items():
                if data is None or data.get("last_price") is None:
                    self._cooldown[code] = now + COOLDOWN_S
                else:
                    self._quotes[code] = data
                    self._ts[code] = now
                    self._cooldown.pop(code, None)

        self._known_codes = code_set
        s = self.stats()
        print(
            f"[yf_cache] refresh: codes={s['tracked']} cached={s['cached']} "
            f"cooldown={s['cooldown']} fetched={len(new_quotes)}",
            flush=True,
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._refresh()
            except Exception as e:
                print(f"[yf_cache] refresh error: {e}", flush=True)
            self._stop.wait(POLL_INTERVAL_S)


# 单例 — app.py 启动时 CACHE.start()
CACHE = YfCache()
