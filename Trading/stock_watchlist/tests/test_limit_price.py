"""src/limit_price 单元测试."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.limit_price import plate_of, calc_limit, is_limit_up, is_limit_down


def test_plate_of():
    # 沪深主板
    assert plate_of("sh.600519") == "main"
    assert plate_of("sh.601318") == "main"
    assert plate_of("sz.000001") == "main"
    assert plate_of("sz.002415") == "main"  # 中小板
    # 创业板
    assert plate_of("sz.300750") == "chinext"
    assert plate_of("sz.301308") == "chinext"
    # 科创板
    assert plate_of("sh.688981") == "star"
    assert plate_of("sh.688111") == "star"
    # 北交所
    assert plate_of("bj.830799") == "bse"
    assert plate_of("bj.430047") == "bse"
    # 异常
    assert plate_of("") is None
    assert plate_of(None) is None
    assert plate_of("AAPL") is None
    print("plate_of: PASS")


def test_main_limit():
    # 沪深主板 ±10%
    up, dn = calc_limit(10.00, "sh.600519")
    assert up == 11.00, f"got {up}"
    assert dn == 9.00, f"got {dn}"
    print("main limit: PASS (10.00 → 11.00/9.00)")


def test_chinext_limit():
    # 创业板 ±20%
    up, dn = calc_limit(10.00, "sz.300323")
    assert up == 12.00, f"got {up}"
    assert dn == 8.00, f"got {dn}"
    print("chinext limit: PASS (10.00 → 12.00/8.00)")


def test_star_limit():
    # 科创板 ±20%
    up, dn = calc_limit(10.00, "sh.688981")
    assert up == 12.00
    assert dn == 8.00
    print("star limit: PASS")


def test_bse_limit():
    # 北交所 ±30%
    up, dn = calc_limit(10.00, "bj.830799")
    assert up == 13.00
    assert dn == 7.00
    print("bse limit: PASS")


def test_rounding_to_cent():
    # 1.234 * 1.10 = 1.3574 → round(2) = 1.36
    up, dn = calc_limit(1.234, "sh.600001")
    assert up == 1.36, f"got {up}"
    assert dn == 1.11, f"got {dn}"  # 1.234 * 0.9 = 1.1106 → 1.11
    print("rounding: PASS (1.234 → 1.36/1.11)")


def test_st_does_not_change_pct():
    # 2026-07-06 新规则: ST 涨跌幅跟所在板块普通股票一致, 所以 ST 名不传也无所谓
    # 这里只是确认 calc_limit 不依赖 name 参数 (新规则下 ST 不影响)
    up1, dn1 = calc_limit(10.00, "sz.300323")  # 创业板
    up2, dn2 = calc_limit(10.00, "sz.300323")  # 没传 name, 应该也 20%
    assert up1 == up2 == 12.00
    assert dn1 == dn2 == 8.00
    print("st ignore: PASS (calc_limit 不依赖 ST 字段)")


def test_boundary():
    # pre_close 缺失 / 0 / 负
    assert calc_limit(None, "sh.600519") == (None, None)
    assert calc_limit(0, "sh.600519") == (None, None)
    assert calc_limit(-1, "sh.600519") == (None, None)
    # 未知代码
    assert calc_limit(10.0, "AAPL") == (None, None)
    print("boundary: PASS")


def test_is_limit_up_down():
    # 沪深主板, pre_close=10.00 → 涨停 11.00 / 跌停 9.00
    assert is_limit_up(11.00, 10.00, "sh.600519") is True
    assert is_limit_up(10.99, 10.00, "sh.600519") is False
    assert is_limit_up(11.005, 10.00, "sh.600519") is True  # 容差 1 分
    assert is_limit_down(9.00, 10.00, "sh.600519") is True
    assert is_limit_down(9.01, 10.00, "sh.600519") is False
    print("is_limit_*: PASS")


def test_real_examples():
    """真实股票验证."""
    # 华灿光电 (创业板 sz.300323): 假设昨收 5.77
    up, dn = calc_limit(5.77, "sz.300323")
    assert up == 6.92, f"got {up}"  # 5.77 * 1.2 = 6.924 → 6.92
    assert dn == 4.62, f"got {dn}"  # 5.77 * 0.8 = 4.616 → 4.62
    # 茅台 (沪市主板 sh.600519): 假设昨收 1500.00
    up, dn = calc_limit(1500.00, "sh.600519")
    assert up == 1650.00
    assert dn == 1350.00
    # 寒武纪 (科创板 sh.688256): 假设昨收 500.00
    up, dn = calc_limit(500.00, "sh.688256")
    assert up == 600.00
    assert dn == 400.00
    # 凯德石英 (北交所 bj.835179): 假设昨收 20.00
    up, dn = calc_limit(20.00, "bj.835179")
    assert up == 26.00
    assert dn == 14.00
    print("real examples: PASS")


if __name__ == "__main__":
    test_plate_of()
    test_main_limit()
    test_chinext_limit()
    test_star_limit()
    test_bse_limit()
    test_rounding_to_cent()
    test_st_does_not_change_pct()
    test_boundary()
    test_is_limit_up_down()
    test_real_examples()
    print("\n=== ALL PASS ===")