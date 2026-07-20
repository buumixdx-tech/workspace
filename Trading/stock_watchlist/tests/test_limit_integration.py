"""涨跌停价集成测试 — 覆盖 remap_quote 和 sector_aggregator."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import remap_quote
from src.limit_price import calc_limit, is_limit_up, is_limit_down


# —— remap_quote 集成 ——————————————————————————————

def test_remap_quote_chinext():
    """创业板 sz.300323, 昨收 20.69 → 涨停 24.83 / 跌停 16.55"""
    q = {"code": "300323", "last_price": 17.95, "pre_close_price": 20.69}
    r = remap_quote(q)
    assert r["limit_up"] == 24.83, f"got {r['limit_up']}"
    assert r["limit_down"] == 16.55, f"got {r['limit_down']}"
    assert r["code"] == "sz.300323"
    assert r["pre_close"] == 20.69
    print(f"remap_quote chinext: PASS (up={r['limit_up']}, dn={r['limit_down']})")


def test_remap_quote_main():
    """沪市主板 sh.600519, 昨收 1500 → 涨停 1650 / 跌停 1350"""
    q = {"code": "600519", "last_price": 1510, "pre_close_price": 1500}
    r = remap_quote(q)
    assert r["limit_up"] == 1650.0
    assert r["limit_down"] == 1350.0
    print(f"remap_quote main: PASS")


def test_remap_quote_star():
    """科创板 sh.688981, 昨收 500 → 涨停 600 / 跌停 400"""
    q = {"code": "688981", "last_price": 510, "pre_close_price": 500}
    r = remap_quote(q)
    assert r["limit_up"] == 600.0
    assert r["limit_down"] == 400.0
    print(f"remap_quote star: PASS")


def test_remap_quote_bse():
    """北交所 bj.830799, 昨收 20 → 涨停 26 / 跌停 14"""
    q = {"code": "830799", "last_price": 21, "pre_close_price": 20}
    r = remap_quote(q)
    assert r["limit_up"] == 26.0
    assert r["limit_down"] == 14.0
    print(f"remap_quote bse: PASS")


def test_remap_quote_hk_safe():
    """港股 0700.HK 不归 A 股规则, limit 字段为 None"""
    q = {"code": "0700.HK", "last_price": 300, "pre_close_price": 290}
    r = remap_quote(q)
    assert r["limit_up"] is None
    assert r["limit_down"] is None
    print(f"remap_quote HK safe: PASS (None)")


def test_remap_quote_missing_pre_close():
    """缺 pre_close → limit 字段为 None, 其他字段仍正常"""
    q = {"code": "300323", "last_price": 17.95}
    r = remap_quote(q)
    assert r["limit_up"] is None
    assert r["limit_down"] is None
    assert r["last_price"] == 17.95
    assert r["change"] is None
    assert r["change_pct"] is None
    print(f"remap_quote missing pre_close: PASS")


# —— sector_aggregator limit_flag 集成 ——————————————————

def test_sector_aggregator_limit_flag_up():
    """模拟 sz.300323 触涨停, top_gainers 应含 limit_flag='up'."""
    # 构造 SectorAggregator 实例 + mock caches
    from src.sector_aggregator import SectorAggregator

    # last_price 23.95, pre_close 19.96 (创业板 ±20%) → 涨停 23.95 (= 19.96 * 1.2)
    pre_close = 19.96
    up_limit = calc_limit(pre_close, "sz.300323")[0]  # 23.95
    # 容差集合竞价撮合 (-0.005 在 is_limit_up 默认 tol=1e-6 之外, 改用 tol=0.01)
    last = up_limit - 0.005
    assert is_limit_up(last, pre_close, "sz.300323", tol=0.01), f"last={last} up_limit={up_limit}"

    quote = {
        "sz.300323": {"last_price": last, "pre_close": pre_close, "change": last - pre_close,
                   "change_pct": (last - pre_close) / pre_close, "amount": 1e8}
    }
    profile = {
        "sz.300323": {"circulating_market_value": 50e8, "total_market_value": 100e8,
                   "turnover_rate": 0.01, "amount": 1e8}
    }

    class MockQC:
        def get_quote(self, code): return quote.get(code)
    class MockPC:
        def get(self, code): return profile.get(code)
    class MockDB:
        def get_stock_names(self_inner):
            return {"sz.300323": "华灿光电"}

    agg = SectorAggregator()
    agg._quote_cache = MockQC()
    agg._profile_cache = MockPC()
    res = agg._compute_sector(1, ["sz.300323"])

    assert res is not None
    # 涨幅 +20% 应该在 top_gainers 第 1 位
    assert any(g["limit_flag"] == "up" for g in res["top_gainers"])
    assert any(c["limit_flag"] == "up" for c in res["contributors"])
    print(f"sector_aggregator limit_flag up: PASS")


def test_sector_aggregator_limit_flag_down():
    """模拟 sz.300323 触跌停."""
    pre_close = 20.00
    dn_limit = calc_limit(pre_close, "sz.300323")[1]  # 16.00
    last = dn_limit + 0.005  # 16.005
    assert is_limit_down(last, pre_close, "sz.300323", tol=0.01)

    quote = {
        "sz.300323": {"last_price": last, "pre_close": pre_close, "change": last - pre_close,
                   "change_pct": (last - pre_close) / pre_close, "amount": 5e7}
    }
    profile = {"sz.300323": {"circulating_market_value": 50e8, "total_market_value": 100e8, "amount": 5e7}}

    class MockQC:
        def get_quote(self, code): return quote.get(code)
    class MockPC:
        def get(self, code): return profile.get(code)
    class MockDB:
        def get_stock_names(self_inner):
            return {"sz.300323": "华灿光电"}

    from src.sector_aggregator import SectorAggregator
    agg = SectorAggregator()
    agg._quote_cache = MockQC()
    agg._profile_cache = MockPC()
    res = agg._compute_sector(1, ["sz.300323"])

    assert res is not None
    assert any(l["limit_flag"] == "down" for l in res["top_losers"])
    assert any(c["limit_flag"] == "down" for c in res["contributors"])
    print(f"sector_aggregator limit_flag down: PASS")


def test_sector_aggregator_no_limit():
    """未触板时 limit_flag = None."""
    pre_close = 20.00
    last = 21.50  # 中间价

    quote = {"sz.300323": {"last_price": last, "pre_close": pre_close,
                         "change": last - pre_close, "change_pct": (last-pre_close)/pre_close, "amount": 1e8}}
    profile = {"sz.300323": {"circulating_market_value": 50e8, "total_market_value": 100e8, "amount": 1e8}}

    class MockQC:
        def get_quote(self, code): return quote.get(code)
    class MockPC:
        def get(self, code): return profile.get(code)
    class MockDB:
        def get_stock_names(self_inner):
            return {"sz.300323": "华灿光电"}

    from src.sector_aggregator import SectorAggregator
    agg = SectorAggregator()
    agg._quote_cache = MockQC()
    agg._profile_cache = MockPC()
    res = agg._compute_sector(1, ["sz.300323"])

    assert res is not None
    for g in res["top_gainers"]:
        assert g["limit_flag"] is None
    for c in res["contributors"]:
        assert c["limit_flag"] is None
    print(f"sector_aggregator no limit: PASS")


if __name__ == "__main__":
    test_remap_quote_chinext()
    test_remap_quote_main()
    test_remap_quote_star()
    test_remap_quote_bse()
    test_remap_quote_hk_safe()
    test_remap_quote_missing_pre_close()
    test_sector_aggregator_limit_flag_up()
    test_sector_aggregator_limit_flag_down()
    test_sector_aggregator_no_limit()
    print("\n=== ALL INTEGRATION TESTS PASS ===")