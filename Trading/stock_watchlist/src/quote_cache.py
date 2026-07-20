"""A 股 quote 后台拉取 daemon — 统一供个股详情 + 板块聚合。

职责:
- 3s tick 拉一次全 watchlist A 股 quote (eltdx 推流周期)
- 维护 _QUOTE_CACHE: {code: quote}        ← 板块聚合消费
- 维护 _RECENT_QUOTES: {code: (quote, ts)} ← api_stock_detail 消费 (5s TTL)
- 池子变更事件驱动: invalidate_pool() 后下次 refresh 重载
- 拉取后触发 on_refresh hooks (供 SectorAggregator 订阅)

与 YfCache 区别:
- YfCache 拉 HK/US, 30s tick (YF 限流)
- QuoteCache 拉 A 股, 3s tick (eltdx 推流周期)
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from src.core import _clean, get_client, normalize_code_ck, remap_quote
from src.db import get_watchlist_a_codes
from src.limit_price import is_limit_up, is_limit_down

# 配置常量
POLL_INTERVAL_S = 3.0       # eltdx 推流周期
RECENT_TTL_S = 5.0          # api_stock_detail 复用 quote 的窗口
COOLDOWN_S = 60.0           # 拉取失败退避
LIMIT_TOL = 0.01            # 触达涨跌停的容差(1 分)


class QuoteCache:
    def __init__(self) -> None:
        self._pool: set[str] = set()                     # 当前拉取的 A 股 code 池
        self._quotes: dict[str, dict] = {}               # code -> remap_quote dict
        self._recent: dict[str, tuple[dict, float]] = {} # code -> (quote, ts) 供 5s TTL 复用
        self._cooldown: dict[str, float] = {}            # code -> next_retry_ts
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._pool_event = threading.Event()             # 池子变更信号
        self._on_refresh_hooks: list[Callable[[], None]] = []

    # —— 公开 API ————————————————————————————————————————

    def get_quote(self, code: str) -> dict | None:
        """板块聚合 / 其他模块用: 拿最新 quote, 无 TTL 限制 (拉一次就用一次)."""
        ck = normalize_code_ck(code)
        with self._lock:
            return self._quotes.get(ck)

    def get_recent(self, code: str) -> dict | None:
        """api_stock_detail 用: 5s 内复用的 quote, 过期返回 None."""
        ck = normalize_code_ck(code)
        now = time.time()
        with self._lock:
            entry = self._recent.get(ck)
            if entry is None:
                return None
            q, ts = entry
            if (now - ts) >= RECENT_TTL_S:
                return None
            return q

    def put_recent(self, code: str, quote: dict) -> None:
        """api_stock_detail 在 CACHE MISS 拉完 eltdx 后, 写回 recent 供后续复用."""
        ck = normalize_code_ck(code)
        now = time.time()
        with self._lock:
            self._recent[ck] = (quote, now)

    def invalidate_pool(self) -> None:
        """sector_stocks 变更后调: 下次 refresh 重载池子."""
        self._pool_event.set()

    def on_refresh(self, hook: Callable[[], None]) -> None:
        """注册 refresh 完成后的回调 (SectorAggregator 订阅用)."""
        self._on_refresh_hooks.append(hook)

    def stats(self) -> dict:
        with self._lock:
            return {
                "tracked": len(self._pool),
                "cached": len(self._quotes),
                "cooldown": len(self._cooldown),
                "recent": len(self._recent),
            }

    def start(self) -> threading.Thread:
        """启动后台 refresh 线程 + 同步首次拉取 + 同步首次池子加载."""
        # 冷启动: 同步加载池子 + 同步首次拉取
        # 这样首屏 HTTP 请求不会拿到空数据
        self._reload_pool()
        try:
            self._refresh_quotes()
        except Exception as e:
            print(f"[quote_cache] initial refresh failed: {e}", flush=True)
        # 启动后台线程
        t = threading.Thread(target=self._run, daemon=True, name="QuoteCache")
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()

    # —— 内部 ——————————————————————————————————————————

    def _reload_pool(self) -> None:
        """从 DB 重载池子. 增量更新: 新增进池, 删除出池."""
        try:
            new_pool_list = get_watchlist_a_codes()
        except Exception as e:
            print(f"[quote_cache] pool reload failed: {e}", flush=True)
            return
        new_pool = set(new_pool_list)
        with self._lock:
            # 出池: 移除 quote / recent / cooldown
            removed = self._pool - new_pool
            for c in removed:
                self._quotes.pop(c, None)
                self._recent.pop(c, None)
                self._cooldown.pop(c, None)
            added = new_pool - self._pool
            self._pool = new_pool
        if added or removed:
            print(
                f"[quote_cache] pool reloaded: +{len(added)} -{len(removed)} "
                f"total={len(new_pool)}",
                flush=True,
            )

    def _refresh_quotes(self) -> None:
        """拉一次所有未在 cooldown 的股票."""
        with self._lock:
            now = time.time()
            pool_snapshot = list(self._pool)
            to_fetch = [c for c in pool_snapshot if self._cooldown.get(c, 0) < now]

        if not to_fetch:
            self._fire_hooks()
            return

        # 拆 eltdx 格式: sh600519
        api_codes = [c.replace(".", "") for c in to_fetch]
        try:
            client = get_client()
            snapshots = client.get_quote(api_codes)
        except Exception as e:
            print(f"[quote_cache] batch fetch failed: {e}", flush=True)
            with self._lock:
                for c in to_fetch:
                    self._cooldown[c] = time.time() + COOLDOWN_S
            self._fire_hooks()
            return

        # 解析 snapshots: 匹配回原 code
        fetched = 0
        now = time.time()
        with self._lock:
            for snap in snapshots:
                clean = _clean(snap)
                if not clean:
                    continue
                # eltdx 返回的 code 不带 exchange 前缀, 拼接匹配
                raw = (clean.get("exchange", "") + clean.get("code", "")).lower()
                for orig_code in to_fetch:
                    if orig_code.replace(".", "") == raw:
                        q = remap_quote(clean)
                        # 提前算 limit_flag — SectorAggregator 直接读,省 eltdx plate_of 调用
                        # 每 tick 100 板块 × 100 股 = 10000 is_limit_up/down 调用 → 0
                        q["limit_flag"] = _calc_limit_flag(q, orig_code)
                        self._quotes[orig_code] = q
                        self._recent[orig_code] = (q, now)
                        self._cooldown.pop(orig_code, None)
                        fetched += 1
                        break

        s = self.stats()
        print(
            f"[quote_cache] refresh: tracked={s['tracked']} cached={s['cached']} "
            f"cooldown={s['cooldown']} fetched={fetched}",
            flush=True,
        )
        self._fire_hooks()

    def _fire_hooks(self) -> None:
        for hook in self._on_refresh_hooks:
            try:
                hook()
            except Exception as e:
                print(f"[quote_cache] hook failed: {e}", flush=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            # 先检查池子变更
            if self._pool_event.is_set():
                self._pool_event.clear()
                self._reload_pool()
            # 再拉数据
            try:
                self._refresh_quotes()
            except Exception as e:
                print(f"[quote_cache] refresh error: {e}", flush=True)
            self._stop.wait(POLL_INTERVAL_S)


# —— 模块级 helper ——————————————————————————————————————————

def _calc_limit_flag(quote: dict, code: str) -> str | None:
    """基于 quote.last_price + change 计算触达涨跌停 — 在 quote 进 cache 时算好。

    SectorAggregator 直接读 quote.limit_flag,不再每 tick 调 is_limit_up/down,
    省掉 eltdx plate_of RPC(每次约 1ms × 100 股 = 100ms / tick)。

    返回: "up" / "down" / None
    """
    last = quote.get("last_price")
    change = quote.get("change")
    if last is None or change is None:
        return None
    prev = last - change
    if prev is None:
        return None
    if is_limit_up(last, prev, code, tol=LIMIT_TOL):
        return "up"
    if is_limit_down(last, prev, code, tol=LIMIT_TOL):
        return "down"
    return None


# 单例
CACHE = QuoteCache()
