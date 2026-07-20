"""板块聚合器 — 订阅 QuoteCache + ProfileCache, 实时算板块涨跌幅/换手率/排名。

职责:
- 纯算术, 无 IO (除读 sector_stocks 映射)
- 每次 QuoteCache refresh 后 (3s) 重算
- 维护 _SECTOR_METRICS: {sector_id: {change_pct, turnover, top_gainers, top_losers, contributors, ts}}

算法:
- 板块涨跌幅 = Σ(weight × change_pct) / Σ(weight)  (weight 由 weight_mode 决定)
  - total     → 总市值
  - circulating → 流通市值
  - equal     → 等权 (1/N)
- 板块换手率 = Σ(amount) / Σ(circulating_market_value)
- 贡献 = change_pct × weight

依赖: ProfileCache 已按 BATCH_SIZE=100 拆小批, 市值字段 100% 命中
      → 不再需要 weight_mode fallback 链

非交易日判定: 全部股票 pre_close == last_price (价格未变) → 视为非交易日, 返回 None
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from src.db import get_sector_stocks_map_with_labels, get_stock_names

# —— 板块配置 (用户可切换, 后续接前端) ——————————————
DEFAULT_WEIGHT_MODE = "total"     # "total" | "circulating" | "equal"
DEFAULT_TOP_N = 3
DEFAULT_PERIOD = "today"          # "today" | "5d" | "20d" (5d/20d 留接口, 计算待实现)
SECTOR_STOCKS_TTL_S = 30.0       # sector_stocks 映射缓存 (变动少)
STOCK_NAMES_TTL_S = 30.0         # stocks.name 缓存 (用户加股才变)


class SectorAggregator:
    def __init__(self) -> None:
        self._metrics: dict[int, dict] = {}
        self._sector_stocks: dict[int, list[tuple[str, str]]] = {}  # code, label
        self._sector_stocks_ts: float = 0.0
        self._stock_names: dict[str, str] = {}
        self._stock_names_ts: float = 0.0
        self._lock = threading.RLock()
        self._weight_mode = DEFAULT_WEIGHT_MODE
        self._top_n = DEFAULT_TOP_N
        self._period = DEFAULT_PERIOD
        self._label_filter: set[str] | None = None  # None = 不过滤全部显示

        # 引用: 由 app.py 注入
        self._quote_cache = None
        self._profile_cache = None

    # —— 公开 API ————————————————————————————————————————

    def attach(self, quote_cache, profile_cache) -> None:
        """app._bootstrap 中注入 cache 引用 + 注册 hook."""
        self._quote_cache = quote_cache
        self._profile_cache = profile_cache
        quote_cache.on_refresh(self.recompute)
        # ProfileCache 5min tick — profile 字段(市值/总股本)变了也要立即重算
        # 不然市值变化要等下一次 QuoteCache 3s tick 才反映,最坏 5min 延迟
        if hasattr(profile_cache, "on_refresh"):
            profile_cache.on_refresh(self.recompute)
        print("[aggregator] attached to QuoteCache + ProfileCache on_refresh", flush=True)

    def get_metrics(self, sector_id: int) -> dict | None:
        with self._lock:
            return self._metrics.get(sector_id)

    def get_all_metrics(self) -> dict[int, dict]:
        with self._lock:
            return dict(self._metrics)

    def get_sector_stocks(self) -> dict[int, list[tuple[str, str]]]:
        """带 TTL 的 sector_stocks 映射 (code, label)。"""
        now = time.time()
        with self._lock:
            if (now - self._sector_stocks_ts) < SECTOR_STOCKS_TTL_S and self._sector_stocks:
                return dict(self._sector_stocks)
        # 过期重读 (DB IO, 放锁外避免阻塞)
        fresh = get_sector_stocks_map_with_labels()
        with self._lock:
            self._sector_stocks = fresh
            self._sector_stocks_ts = now
            return dict(fresh)

    def get_stock_names(self) -> dict[str, str]:
        """带 TTL 的 code→name 映射. 给 top_gainers/losers/contributors 显示简称."""
        now = time.time()
        with self._lock:
            if (now - self._stock_names_ts) < STOCK_NAMES_TTL_S and self._stock_names:
                return dict(self._stock_names)
        fresh = get_stock_names()
        with self._lock:
            self._stock_names = fresh
            self._stock_names_ts = now
            return dict(fresh)

    def set_label_filter(self, labels: set[str] | None) -> None:
        """设置 label 过滤集合。None 表示不过滤（全部）。"""
        with self._lock:
            self._label_filter = labels
        self.recompute()

    def get_label_filter(self) -> set[str] | None:
        with self._lock:
            return self._label_filter

    def set_config(self, weight_mode: str = None, top_n: int = None, period: str = None) -> dict:
        if weight_mode and weight_mode in ("total", "circulating", "equal"):
            self._weight_mode = weight_mode
        if top_n is not None:
            try:
                t = int(top_n)
                if 1 <= t <= 20:
                    self._top_n = t
            except (TypeError, ValueError):
                pass
        if period and period in ("today", "5d", "20d"):
            self._period = period
        # 立即重算 (配置变了)
        self.recompute()
        return self.get_config()

    def get_config(self) -> dict:
        with self._lock:
            return {
                "weight_mode": self._weight_mode,
                "top_n": self._top_n,
                "period": self._period,
            }

    def recompute(self) -> None:
        """QuoteCache / ProfileCache refresh 后调. 重算所有板块 metrics.

        注意:ProfileCache 5min tick,QuoteCache 3s tick — 两次都会调到这里。
        """
        if self._quote_cache is None or self._profile_cache is None:
            return

        sector_stocks = self.get_sector_stocks()
        if not sector_stocks:
            return

        # name_map 提到 recompute 入口一次,避免每 sector 都查一次 stock_names 表
        # 100 板块 × 30s TTL = 之前可能 50 次 / 次 recompute;现在 1 次
        name_map = self.get_stock_names()

        with self._lock:
            label_filter = self._label_filter

        new_metrics: dict[int, dict] = {}
        now = time.time()

        for sector_id, stocks_with_labels in sector_stocks.items():
            # 按 label 过滤
            if label_filter is not None:
                codes = [code for code, label in stocks_with_labels if label in label_filter]
            else:
                codes = [code for code, label in stocks_with_labels]
            m = self._compute_sector(sector_id, codes, name_map)
            if m is not None:
                m["ts"] = now
                new_metrics[sector_id] = m

        with self._lock:
            self._metrics = new_metrics

    # —— 内部 ——————————————————————————————————————————

    def _compute_sector(self, sector_id: int, codes: list[str], name_map: dict[str, str] | None = None) -> dict | None:
        """算单个板块的所有 metrics."""
        # name_map 由 recompute() 一次性传入,避免每个 sector 重复查 stocks 表
        if name_map is None:
            name_map = self.get_stock_names()

        # 收集每只股票: change_pct, market_cap (权重), amount (换手率)
        rows = []
        total_circ_mv = 0.0
        total_amount = 0.0
        all_prices_unchanged = True  # 非交易日判定

        for code in codes:
            q = self._quote_cache.get_quote(code) if self._quote_cache else None
            p = self._profile_cache.get(code) if self._profile_cache else None
            if not q or not p:
                continue
            # 停牌股(eltdx 给 last=0): 不参与板块聚合,否则 -100% 假跌停拖死板块涨幅
            if q.get("is_suspended"):
                continue
            change_pct = q.get("change_pct")
            last = q.get("last_price")
            prev = last - (q.get("change") or 0) if last is not None and q.get("change") is not None else None
            if last is not None and prev is not None and last != prev:
                all_prices_unchanged = False

            # profile_cache 现在按 100 串行, total_mv/circ_mv 字段 100% 命中
            # 单只 None 是偶发 (网络抖动), 当作 0 处理即可, 不会整体崩
            circ_mv = p.get("circulating_market_value") or 0
            total_amount += q.get("amount") or 0

            # —— 一字板标记 ——
            # limit_flag 由 QuoteCache 在写入 quote 时已算好(避免 aggregator 内层
            # 重复调 is_limit_up/down + plate_of)。QuoteCache 还没拉到的股(q is None)
            # 不会进到这里。
            limit_flag = q.get("limit_flag")

            rows.append({
                "code": code,
                "name": name_map.get(code) or code,  # 缺名回退 code
                "change_pct": change_pct or 0.0,
                "total_mv": p.get("total_market_value") or 0,
                "circ_mv": circ_mv,
                "limit_flag": limit_flag,
            })
            total_circ_mv += circ_mv

        if not rows:
            return None

        # 非交易日: 全部价格不变 → 涨跌幅为 None
        if all_prices_unchanged:
            return {
                "change_pct": None,
                "turnover": None,
                "top_gainers": [],
                "top_losers": [],
                "contributors": [],
                "stock_count": len(rows),
                "total_count": len(codes),
            }

        # —— 权重模式 (固定 3 选 1, 不再有跨模式 fallback) ——
        # profile 100% 命中, 市值字段稳定; equal 是用户明确选择, 不再自动降级
        if self._weight_mode == "equal":
            weight_mode = "equal"
            weight_key = None
        elif self._weight_mode == "circulating":
            weight_mode = "weight"
            weight_key = "circ_mv"
        else:  # "total"
            weight_mode = "weight"
            weight_key = "total_mv"

        # —— 板块涨跌幅 ——
        if weight_mode == "equal":
            change_pct = sum(r["change_pct"] for r in rows) / len(rows)
        else:
            weight_sum = sum(r[weight_key] for r in rows) or 1
            change_pct = sum(r["change_pct"] * r[weight_key] for r in rows) / weight_sum

        # —— 板块换手率: 总成交额 / 总流通市值 ——
        turnover = (total_amount / total_circ_mv) if total_circ_mv > 0 else None

        # —— 算每个股的权重 (统一用, 给 contributors 用) ——
        if weight_mode == "equal":
            weight_lookup = {r["code"]: 1.0 / len(rows) for r in rows}
        else:
            weight_lookup = {r["code"]: r[weight_key] / weight_sum for r in rows}

        # —— Top N 涨/跌幅 (永远按 change_pct 排, 短线视角) ——
        # 永远是 top_n 条: 板块全跌时 "领涨" = 跌得最少的 N 只 (但仍叫领涨, 表示相对最强)
        sorted_by_chg = sorted(rows, key=lambda r: r["change_pct"], reverse=True)
        top_gainers = [
            {"code": r["code"], "name": r["name"], "change_pct": r["change_pct"], "limit_flag": r["limit_flag"]}
            for r in sorted_by_chg[:self._top_n]
        ]
        top_losers = [
            {"code": r["code"], "name": r["name"], "change_pct": r["change_pct"], "limit_flag": r["limit_flag"]}
            for r in sorted_by_chg[-self._top_n:][::-1]
        ]

        # —— 贡献排名 (按贡献 = change_pct × 权重, 板块诊断视角) ——
        # 永远前 3 名; 板块不满 3 只时有多少显示多少 (list[:3] 天然兼容)
        contributors = []
        for r in rows:
            w = weight_lookup[r["code"]]
            contributors.append({
                "code": r["code"],
                "name": r["name"],
                "change_pct": r["change_pct"],
                "weight": w,
                "contribution": r["change_pct"] * w,
                "limit_flag": r["limit_flag"],
            })
        contributors.sort(key=lambda c: c["contribution"], reverse=True)
        contributors = contributors[:3]

        return {
            "change_pct": change_pct,
            "turnover": turnover,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "contributors": contributors,
            "stock_count": len(rows),
            "total_count": len(codes),
        }


# 单例
AGGREGATOR = SectorAggregator()

