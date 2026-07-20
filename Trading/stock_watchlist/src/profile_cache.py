"""A 股 profile 后台拉取 daemon — 供 SectorAggregator 算市值加权 / 换手率。

职责:
- 5min tick 拉一次全 watchlist A 股 stock_profile_table
- 维护 _PROFILE_CACHE: {code: profile_dict}  ← 板块聚合消费
- 池子变更事件驱动: invalidate_pool() 后下次 refresh 重载并拉新池
- 失败 60s cooldown

与 QuoteCache 区别:
- QuoteCache 拉 quote, 3s tick (eltdx 推流周期)
- ProfileCache 拉 profile, 5min tick (市值/换手率不频繁变)

eltdx 协议层硬限制: stock_profile_table 单次 RPC 上限约 100 只, 超过部分字段
会被服务端填为 None. 因此拆小批串行调用, 每批 ≤ BATCH_SIZE.
359 只 / 100 = 4 批 ≈ 0.8s (实测).
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from src.core import _clean, get_client, normalize_code_ck
from src.db import get_watchlist_a_codes

POLL_INTERVAL_S = 300.0  # 5 min
COOLDOWN_S = 60.0
BATCH_SIZE = 100         # eltdx 服务端单次 stock_profile_table 上限


class ProfileCache:
    def __init__(self) -> None:
        self._pool: set[str] = set()
        self._profiles: dict[str, dict] = {}     # code -> profile dict
        self._cooldown: dict[str, float] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._pool_event = threading.Event()
        self._on_refresh_hooks: list[Callable[[], None]] = []

    # —— 公开 API ————————————————————————————————————————

    def get(self, code: str) -> dict | None:
        ck = normalize_code_ck(code)
        with self._lock:
            return self._profiles.get(ck)

    def invalidate_pool(self) -> None:
        self._pool_event.set()

    def on_refresh(self, hook: Callable[[], None]) -> None:
        self._on_refresh_hooks.append(hook)

    def stats(self) -> dict:
        with self._lock:
            return {
                "tracked": len(self._pool),
                "cached": len(self._profiles),
                "cooldown": len(self._cooldown),
            }

    def start(self) -> threading.Thread:
        self._reload_pool()
        try:
            self._refresh()
        except Exception as e:
            print(f"[profile_cache] initial refresh failed: {e}", flush=True)
        t = threading.Thread(target=self._run, daemon=True, name="ProfileCache")
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()

    # —— 内部 ——————————————————————————————————————————

    def _reload_pool(self) -> None:
        try:
            new_pool_list = get_watchlist_a_codes()
        except Exception as e:
            print(f"[profile_cache] pool reload failed: {e}", flush=True)
            return
        new_pool = set(new_pool_list)
        with self._lock:
            removed = self._pool - new_pool
            for c in removed:
                self._profiles.pop(c, None)
                self._cooldown.pop(c, None)
            added = new_pool - self._pool
            self._pool = new_pool
        if added or removed:
            print(
                f"[profile_cache] pool reloaded: +{len(added)} -{len(removed)} "
                f"total={len(new_pool)}",
                flush=True,
            )

    def _refresh(self) -> None:
        with self._lock:
            now = time.time()
            pool_snapshot = list(self._pool)
            to_fetch = [c for c in pool_snapshot if self._cooldown.get(c, 0) < now]

        if not to_fetch:
            self._fire_hooks()
            return

        client = get_client()
        fetched = 0
        failed_codes: list[str] = []

        # 串行拆小批 (≤ BATCH_SIZE 只/批), 避开 eltdx 100 截断
        # 任一批失败 → 该批内所有股都进 cooldown, 其余批继续
        for i in range(0, len(to_fetch), BATCH_SIZE):
            batch_codes = to_fetch[i:i + BATCH_SIZE]
            api_batch = [c.replace(".", "") for c in batch_codes]
            try:
                profiles = client.helpers.stock_profile_table(api_batch)
            except Exception as e:
                print(f"[profile_cache] batch fetch failed (size={len(batch_codes)}): {e}", flush=True)
                failed_codes.extend(batch_codes)
                continue
            fetched += self._ingest(profiles, batch_codes)

        if failed_codes:
            with self._lock:
                for c in failed_codes:
                    self._cooldown[c] = time.time() + COOLDOWN_S

        s = self.stats()
        print(
            f"[profile_cache] refresh: tracked={s['tracked']} cached={s['cached']} "
            f"cooldown={s['cooldown']} fetched={fetched} batches={len(range(0, len(to_fetch), BATCH_SIZE))}",
            flush=True,
        )
        self._fire_hooks()

    def _ingest(self, profiles, batch_codes: list[str]) -> int:
        """把 profiles.rows 写入 self._profiles. 返回成功写入条数."""
        fetched = 0
        rows = list(profiles.rows or [])
        with self._lock:
            for p in rows:
                if not p.code:
                    continue
                raw = (p.exchange + p.code).lower()
                for orig_code in batch_codes:
                    if orig_code.replace(".", "") == raw:
                        self._profiles[orig_code] = {
                            "circulating_market_value": getattr(p, "circulating_market_value", None),
                            "total_market_value": getattr(p, "total_market_value", None),
                            "turnover_rate": getattr(p, "turnover_rate", None),
                            "circulating_shares": getattr(p, "circulating_shares", None),
                            "total_shares": getattr(p, "total_shares", None),
                            "change_pct": getattr(p, "change_pct", None),
                            "amount": getattr(p, "amount", None),
                        }
                        self._cooldown.pop(orig_code, None)
                        fetched += 1
                        break
        return fetched

    def _fire_hooks(self) -> None:
        for hook in self._on_refresh_hooks:
            try:
                hook()
            except Exception as e:
                print(f"[profile_cache] hook failed: {e}", flush=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._pool_event.is_set():
                self._pool_event.clear()
                self._reload_pool()
            try:
                self._refresh()
            except Exception as e:
                print(f"[profile_cache] refresh error: {e}", flush=True)
            self._stop.wait(POLL_INTERVAL_S)


CACHE = ProfileCache()
