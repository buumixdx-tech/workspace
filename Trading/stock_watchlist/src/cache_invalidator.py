"""Cache 失效统一入口。

背景:routes.py 里 4 个 mutation path 之前不调 invalidate_pool(),
导致 QuoteCache / ProfileCache 的 A 股池子永远不刷新 — 新加的股 / 移动股 / 改 label
要 daemon 重启才生效(C1 审查)。

港美股池子由 YfCache 自己 30s tick 重载,不需在这里失效。
"""
from __future__ import annotations


def invalidate_a_share_pool() -> None:
    """A 股 quote / profile 池子变更后调。

    触发 QuoteCache + ProfileCache 在下一次 refresh tick 重载池子。
    """
    from src.quote_cache import CACHE as QUOTE_CACHE
    from src.profile_cache import CACHE as PROFILE_CACHE
    QUOTE_CACHE.invalidate_pool()
    PROFILE_CACHE.invalidate_pool()


def recompute_sector_aggregator() -> None:
    """板块结构 / label 变更后调,触发 SectorAggregator 立即重算。

    Aggregator 内有 30s TTL 兜底,但主动调可以避免用户立即看到陈旧指标。
    """
    from src.sector_aggregator import AGGREGATOR
    AGGREGATOR.recompute()


def on_sector_stocks_mutated() -> None:
    """加股 / 删股 / 移股 / 改 label 后的统一失效入口。

    池子变化 → invalidate;聚合可能受影响 → recompute。
    """
    invalidate_a_share_pool()
    recompute_sector_aggregator()