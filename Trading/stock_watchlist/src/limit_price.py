"""A 股个股日涨跌停价计算.

规则来源 (2026-07-06 起):
- 沪深主板 (sh.6, sz.000/002): ±10%
- 创业板 (sz.300/301): ±20%
- 科创板 (sh.688): ±20%
- 北交所 (bj.8/4): ±30%

**ST 状态在新规则下不影响涨跌停价** (沪深主板风险警示股 2026-07-06 起从 5% 调到 10%,
与同板块普通股票一致;科创板/创业板/北交所 ST 一直与普通同幅度).

价格四舍五入到 0.01 元 (精确到分).

不在本函数覆盖范围 (需另算):
- 新股上市首日 (不设涨跌幅)
- 退市整理期 (按规则)
- 重组停牌复牌首日
"""

# 板块 → 涨跌幅
_PLATE_PCT = {
    "main": 0.10,    # 沪深主板
    "chinext": 0.20, # 创业板
    "star": 0.20,    # 科创板
    "bse": 0.30,     # 北交所
}


def plate_of(code: str) -> str | None:
    """根据代码前缀判断所属板块.

    支持两种输入:
    - CK 标准格式: sz.300323 / sh.688981 / bj.830799
    - 裸 6 位: 300323 / 688981 / 830799 (常见于 eltdx QuoteSnapshot.code)

    >>> plate_of("sh.600519")
    'main'
    >>> plate_of("sz.000001")
    'main'
    >>> plate_of("sz.002415")
    'main'
    >>> plate_of("sz.300750")
    'chinext'
    >>> plate_of("sz.301308")
    'chinext'
    >>> plate_of("sh.688981")
    'star'
    >>> plate_of("bj.830799")
    'bse'
    >>> plate_of("300323")  # 裸 6 位
    'chinext'
    >>> plate_of("688981")
    'star'
    >>> plate_of("830799")  # 裸 6 位, bse
    'bse'
    """
    if not code:
        return None
    c = code.lower()
    # 带点 CK 格式
    if c.startswith("bj."):
        return "bse"
    if c.startswith("sz.30"):
        return "chinext"
    if c.startswith("sz.00") or c.startswith("sz.20"):
        return "main"
    if c.startswith("sh.688"):
        return "star"
    if c.startswith("sh.6") or c.startswith("sh.9"):
        return "main"
    # 兜底: normalize_code_ck 把 830xxx/4xxxxx 错归到 sh. 实际是北交所
    if c.startswith("sh.8") or c.startswith("sh.4"):
        return "bse"
    # 裸 6 位数字 (eltdx QuoteSnapshot.code 格式)
    if len(c) == 6 and c.isdigit():
        if c.startswith("92"):
            return "bse"     # 920xxx 北交所
        if c.startswith("8") or c.startswith("4"):
            return "bse"     # 8xxxxx / 4xxxxx 北交所
        if c.startswith("30") or c.startswith("20"):
            return "chinext" # 300/301 创业板
        if c.startswith("688"):
            return "star"    # 科创板
        if c.startswith("6") or c.startswith("0") or c.startswith("2"):
            return "main"    # 主板
    return None


def calc_limit(pre_close: float, code: str) -> tuple[float | None, float | None]:
    """算个股日涨跌停价.

    Args:
        pre_close: 昨收价 (元)
        code: 完整代码, 如 "sz.300323" / "sh.600519"

    Returns:
        (up_limit, down_limit), 都四舍五入到 0.01; 缺数据返回 (None, None).
    """
    if pre_close is None or pre_close <= 0:
        return None, None
    plate = plate_of(code)
    if plate is None:
        return None, None
    pct = _PLATE_PCT[plate]
    up = round(pre_close * (1 + pct), 2)
    dn = round(pre_close * (1 - pct), 2)
    return up, dn


def is_limit_up(last_price: float, pre_close: float, code: str, tol: float = 1e-6) -> bool:
    """last 是否触及涨停 (允许 1 分钱误差容忍集合竞价撮合偏差)."""
    up, _ = calc_limit(pre_close, code)
    return up is not None and last_price is not None and last_price >= up - tol


def is_limit_down(last_price: float, pre_close: float, code: str, tol: float = 1e-6) -> bool:
    """last 是否触及跌停."""
    _, dn = calc_limit(pre_close, code)
    return dn is not None and last_price is not None and last_price <= dn + tol