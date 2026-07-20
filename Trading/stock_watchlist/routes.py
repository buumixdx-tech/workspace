"""Flask Blueprint：所有 HTTP API。"""

import threading
from flask import Blueprint, jsonify, render_template, request

bp = Blueprint("stock_watchlist", __name__)

# A 股 quote 缓存已迁移到 src.quote_cache.QuoteCache (daemon 维护)


def _is_yf_code(code: str) -> bool:
    """判断代码是否为港美股（Yahoo Finance 格式）。"""
    code = code.strip()
    if code.endswith('.HK'):
        return True  # 港股
    if code.startswith('^'):
        return True  # 指数
    # 全大写字母数字 = 美股（A股是 sh/sz/bj + 数字，混进来会走 eltdx）
    if code.isupper() and code.isalnum():
        return True
    # 旧格式 hk*/us* 也走 YF
    c = code.lower()
    if c.startswith('hk') or c.startswith('us'):
        return True
    return False


def _fetch_quote_for_stock(stock: dict) -> tuple:
    """后台线程：获取单只股票实时行情，返回 (stock, quote)。"""
    code = stock.get("stock_code") or stock.get("code") or ""
    quote = None
    if _is_yf_code(code):
        from src.yf import get_quote, _to_yf_symbol
        yf_sym = _to_yf_symbol(code)
        yf_data = get_quote(yf_sym) if yf_sym else None
        quote = yf_data
    else:
        from src.core import normalize_code_ck, get_client, _clean
        ck_code = normalize_code_ck(code)
        api_code = ck_code.replace(".", "")
        try:
            client = get_client()
            snapshots = client.get_quote([api_code])
            if snapshots:
                quote = _clean(snapshots[0])
        except Exception:
            pass
    return (stock, quote)


def _enrich_stocks(stocks: list[dict]) -> list[dict]:
    """批量并发拉取所有股票实时行情。
    A 股合并为一次 eltdx 批量请求，港美股并发 Yahoo Finance。
    """
    from src.core import normalize_code_ck, _clean, get_client, remap_quote
    from src.yf import get_quote, _to_yf_symbol

    # 分离 A 股和港美股
    a_stocks = []
    yf_stocks = []
    for s in stocks:
        code = s.get("stock_code") or s.get("code") or ""
        if _is_yf_code(code):
            yf_stocks.append(s)
        else:
            a_stocks.append(s)

    # A 股：一次批量 eltdx 请求（bj 用 stock_profile_table）
    a_quotes = {}
    bj_stocks = []
    other_a_stocks = []
    for s in a_stocks:
        ck = normalize_code_ck(s.get("stock_code") or s.get("code") or "")
        if ck.startswith("bj."):
            bj_stocks.append(s)
        else:
            other_a_stocks.append(s)

    # I2: O(N²) → O(N) — 用 raw_code 作 key 索引 stock_dict,
    # eltdx 返回的每个 snapshot 直接 dict 查找,不再嵌套循环。
    other_a_by_raw: dict[str, dict] = {}
    for s in other_a_stocks:
        ck = normalize_code_ck(s.get("stock_code") or s.get("code") or "")
        other_a_by_raw[ck.replace(".", "")] = s

    # 非 bj A 股：get_quote 批量
    if other_a_stocks:
        api_codes = [c.replace(".", "") for c in other_a_by_raw]
        try:
            client = get_client()
            snapshots = client.get_quote(api_codes)
            for snap in snapshots:
                clean = _clean(snap)
                if not clean:
                    continue
                # eltdx 返回的 code 不带 exchange 前缀 (如 "600519"),
                # 必须用 clean['exchange'] + clean['code'] 拼接才能匹配
                raw_code = (clean.get("exchange", "") + clean.get("code", "")).lower()
                s = other_a_by_raw.get(raw_code)
                if s is None:
                    continue
                key = s.get("stock_code") or s.get("code")
                a_quotes[key] = remap_quote(clean)
        except Exception:
            pass

    # bj A 股：stock_profile_table（get_quote 不支持）
    if bj_stocks:
        bj_by_raw: dict[str, dict] = {}
        for s in bj_stocks:
            ck = normalize_code_ck(s.get("stock_code") or s.get("code") or "")
            bj_by_raw[ck.replace(".", "")] = s
        bj_codes = list(bj_by_raw.keys())
        try:
            client = get_client()
            profiles = client.helpers.stock_profile_table(bj_codes)
            for p in (profiles.rows or []):
                quote = _clean(p.quote) if hasattr(p, "quote") and p.quote else None
                if not quote:
                    continue
                # 同样 bug: eltdx 返回的 code 不带 exchange 前缀
                raw_code = (quote.get("exchange", "") + quote.get("code", "")).lower()
                s = bj_by_raw.get(raw_code)
                if s is None:
                    continue
                key = s.get("stock_code") or s.get("code")
                a_quotes[key] = remap_quote(quote)
        except Exception:
            pass

    # I6: YF 分支 — 一次拿 YfCache 整张 _quotes 快照(N 次 lock acquire → 1 次)
    from src.yf_cache import CACHE as YF_CACHE
    yf_quotes_snapshot = YF_CACHE.snapshot() if yf_stocks else {}
    yf_results: dict[str, dict | None] = {}
    for s in yf_stocks:
        code = s.get("stock_code") or s.get("code") or ""
        yf_sym = _to_yf_symbol(code)
        if yf_sym:
            yf_results[code] = yf_quotes_snapshot.get(yf_sym)

    # 合并，保持原顺序
    # A 股 quote 优先从 QuoteCache 读 (daemon 3s 拉一次, 无网络调用)
    from src.quote_cache import CACHE as QUOTE_CACHE
    ordered = []
    for s in stocks:
        key = s.get("stock_code") or s.get("code")
        if _is_yf_code(key):
            quote = yf_results.get(key)
        else:
            quote = QUOTE_CACHE.get_quote(key) or a_quotes.get(key)
        ordered.append({**s, "quote": quote})
    return ordered


# —— A 股 cache miss cooldown (I3) ——————————————————————————
# 防止用户切股时 cache miss → 同步打 eltdx 阻塞请求线程。
# 5s 内同 code 重复 miss 直接返 None,不重复打。
import threading as _threading
_MISS_COOLDOWN: dict[str, float] = {}
_MISS_LOCK = _threading.Lock()
_MISS_COOLDOWN_S = 5.0


def _safe(handler):
    """装饰器: 业务异常(ApiError) 返对应 HTTP 状态码,其他 Exception 兜底 500.

    迁移路径: 路由里 return jsonify({"ok":False, "error":"..."}), 400/404
    逐步改为 raise BadRequest("...") / NotFound("..."),客户端就能用 HTTP 码区分。
    """
    import functools
    from src.errors import ApiError

    @functools.wraps(handler)
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except ApiError as e:
            return jsonify({"ok": False, "error": e.message}), e.status
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

    return wrapper


# —— 前端入口 ————————————————————————————————————————

@bp.route("/")
def index():
    return render_template("index.html")


# —— 健康检查 ————————————————————————————————————————

@bp.route("/api/health")
def api_health():
    from src.core import get_client
    try:
        get_client()
        return jsonify({"ok": True, "tdx": "ready"})
    except Exception as e:
        return jsonify({"ok": False, "tdx": str(e)}), 503


# —— 指数快照（topbar） ——————————————————————————————————

@bp.route("/api/indices", methods=["GET"])
@_safe
def api_indices():
    """返回 6 个固定指数的最新 quote — 前端 topbar 3s tick 拉一次。

    顺序固定: 上证 / 深成 / 科创 / 日经225 / 韩国 KOSPI / 台湾加权。
    quote 字段缺值时为 null(冷启动 / 该源拉取失败)。
    """
    from src.indices_cache import CACHE as INDICES_CACHE
    data = INDICES_CACHE.snapshot()
    return jsonify({"ok": True, "data": data})


# =============================================================================
# Sectors（板块）
# =============================================================================

@bp.route("/api/sectors", methods=["GET"])
@_safe
def api_sectors_tree():
    """GET /api/sectors — 完整板块树（不含股票），节点内嵌 metrics。"""
    from src.db import build_sectors_tree
    from src.sector_aggregator import AGGREGATOR
    tree = build_sectors_tree()
    metrics = AGGREGATOR.get_all_metrics()
    _inject_metrics_into_tree(tree, metrics)
    return jsonify({"ok": True, "data": tree})


def _inject_metrics_into_tree(nodes: list[dict], metrics: dict[int, dict]) -> None:
    """递归把 metrics 注入到板块树每个节点 (含子板块)。
    metrics 字段: change_pct, turnover (None 表示非交易日/无数据)
    """
    for node in nodes:
        m = metrics.get(node["id"])
        if m:
            node["change_pct"] = m.get("change_pct")
            node["turnover"] = m.get("turnover")
        else:
            node["change_pct"] = None
            node["turnover"] = None
        if node.get("children"):
            _inject_metrics_into_tree(node["children"], metrics)


@bp.route("/api/sectors/metrics", methods=["GET"])
@_safe
def api_sectors_metrics():
    """GET /api/sectors/metrics — 所有板块的实时聚合指标 (涨跌幅/换手率/排名)。

    返回 {sector_id: {change_pct, turnover, top_gainers, top_losers, contributors, stock_count, ts}, ...}
    非交易日: change_pct/turnover 为 null.

    Query:
      ?summary=1  只返 change_pct / turnover / stock_count / ts(给 3s tick 用,流量砍 80%)
      默认        返全字段(给板块卡片弹窗用)
    """
    from src.sector_aggregator import AGGREGATOR
    all_m = AGGREGATOR.get_all_metrics()
    summary_mode = request.args.get("summary", "").strip() in ("1", "true", "yes")
    if summary_mode:
        # 精简字段,前端 3s tick 默认走这里
        out = {
            str(sid): {
                "change_pct": m.get("change_pct"),
                "turnover": m.get("turnover"),
                "stock_count": m.get("stock_count"),
                "ts": m.get("ts"),
            }
            for sid, m in all_m.items()
        }
    else:
        out = {str(k): v for k, v in all_m.items()}
    return jsonify({"ok": True, "data": out})


@bp.route("/api/sectors/<int:sid>/cache_coverage")
@_safe
def api_sector_cache_coverage(sid):
    """诊断: 看某板块每只股票在 quote/profile cache 里有没有数据.

    用于排查 contributors 数量异常 (板块有 N 只股票但 contributors < 3).
    返回 {code: {quote: bool, profile: bool, profile_mv: bool}}.
    """
    from src.quote_cache import CACHE as QC
    from src.profile_cache import CACHE as PC
    from src.db import _db_path, get_descendant_sector_ids
    ids = get_descendant_sector_ids(sid)
    if not ids:
        return jsonify({"ok": True, "data": {
            "total": 0, "with_quote": 0, "with_profile": 0, "with_profile_mv": 0,
            "stocks": {},
        }})
    import sqlite3
    with sqlite3.connect(str(_db_path())) as conn:
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT DISTINCT stock_code FROM sector_stocks WHERE sector_id IN ({placeholders})",
            ids,
        ).fetchall()
        codes = [r["stock_code"] for r in rows]
    result = {}
    for c in codes:
        q = QC.get_quote(c)
        p = PC.get(c)
        result[c] = {
            "quote": q is not None,
            "profile": p is not None,
            "profile_mv": (p or {}).get("total_market_value") is not None,
        }
    coverage = {
        "total": len(codes),
        "with_quote": sum(1 for v in result.values() if v["quote"]),
        "with_profile": sum(1 for v in result.values() if v["profile"]),
        "with_profile_mv": sum(1 for v in result.values() if v["profile_mv"]),
        "stocks": result,
    }
    return jsonify({"ok": True, "data": coverage})


# —— I11: 灌库通知端点 ——————————————————————————————————————
# import_xlsx.py 等离线脚本灌完库后,POST 一下这里强制 daemon 重算,
# 否则前端 metrics 要等 SectorAggregator 30s TTL 过期才刷新。
# 本地单用户,无认证,无 CSRF。

@bp.route("/api/admin/recompute", methods=["POST"])
@_safe
def api_admin_recompute():
    from src.cache_invalidator import invalidate_a_share_pool, recompute_sector_aggregator
    invalidate_a_share_pool()
    recompute_sector_aggregator()
    return jsonify({"ok": True})


@bp.route("/api/sectors/metrics/config", methods=["GET", "PUT"])
@_safe
def api_sectors_metrics_config():
    """GET /api/sectors/metrics/config — 读取当前 weight_mode / top_n / period。
    PUT /api/sectors/metrics/config — 更新配置 (body: {weight_mode?, top_n?, period?}), 立即触发重算.
    """
    from src.sector_aggregator import AGGREGATOR
    if request.method == "GET":
        cfg = AGGREGATOR.get_config()
        return jsonify({"ok": True, "data": cfg})
    # PUT
    data = request.get_json(silent=True) or {}
    cfg = AGGREGATOR.set_config(
        weight_mode=data.get("weight_mode"),
        top_n=data.get("top_n"),
        period=data.get("period"),
    )
    return jsonify({"ok": True, "data": cfg})


@bp.route("/api/sectors/metrics/filter", methods=["GET", "PUT"])
@_safe
def api_sectors_metrics_filter():
    """GET /api/sectors/metrics/filter — 读取当前 label 过滤集合。
    PUT /api/sectors/metrics/filter — 设置 label 过滤 (body: {labels: [str]} 或 labels: null 清除过滤)。

    前端四个 label 勾选项变化时调用，板块聚合指标只计算这些 label 的股票。
    """
    from src.sector_aggregator import AGGREGATOR
    if request.method == "GET":
        f = AGGREGATOR.get_label_filter()
        return jsonify({"ok": True, "data": {"labels": list(f) if f is not None else None}})

    data = request.get_json(silent=True) or {}
    labels = data.get("labels")
    if labels is None:
        AGGREGATOR.set_label_filter(None)
    elif isinstance(labels, list):
        # observation 和 monitor 互通
        normalized = set()
        for l in labels:
            if l == "observation":
                normalized.add("observation")
                normalized.add("monitor")
            elif l == "monitor":
                normalized.add("monitor")
                normalized.add("observation")
            else:
                normalized.add(l)
        AGGREGATOR.set_label_filter(normalized if normalized else None)
    else:
        return jsonify({"ok": False, "error": "labels 必须是列表或 null"}), 400
    return jsonify({"ok": True})


@bp.route("/api/sectors/<int:sector_id>", methods=["GET"])
@_safe
def api_sector_detail(sector_id: int):
    """GET /api/sectors/:id — 单板块详情，include_stocks=true 时递归聚合股票。"""
    from src.db import get_sector, get_aggregated_stocks, get_sector_stocks

    sector = get_sector(sector_id)
    if not sector:
        return jsonify({"ok": False, "error": "板块不存在"}), 404

    include_stocks = request.args.get("include_stocks", "").lower() in ("true", "1", "yes")
    if include_stocks:
        stocks = get_aggregated_stocks(sector_id)
    else:
        stocks = get_sector_stocks(sector_id)

    stocks = _enrich_stocks(stocks)
    return jsonify({
        "ok": True,
        "data": {**sector, "stocks": stocks},
    })


@bp.route("/api/sectors/<int:sector_id>/tree", methods=["GET"])
@_safe
def api_sector_tree(sector_id: int):
    """
    GET /api/sectors/:id/tree
    返回该板块的直接个股 + 直接子板块信息。
    用于前端渲染：直接个股 + 可折叠的子板块区块。
    sector 自身 + 每个 child 注入 metrics (change_pct, turnover)。
    """
    from src.db import get_sector, get_sector_stocks, get_child_sectors
    from src.sector_aggregator import AGGREGATOR

    sector = get_sector(sector_id)
    if not sector:
        return jsonify({"ok": False, "error": "板块不存在"}), 404

    # 直接关联的个股
    direct_stocks = _enrich_stocks(get_sector_stocks(sector_id))

    # 直接子板块
    children = get_child_sectors(sector_id)
    metrics = AGGREGATOR.get_all_metrics()

    # 自身 metrics (注入完整 metrics 对象, 供前端 detail panel 用 top_gainers/losers/contributors)
    sm = metrics.get(sector_id)
    sector["metrics"] = sm

    # 每个子板块的计数（core + focus）
    agg_labels = ("core", "focus")
    child_summaries = []
    for child in children:
        child_stocks = get_sector_stocks(child["id"])
        core_focus_count = sum(1 for s in child_stocks if s.get("label") in agg_labels)
        cm = metrics.get(child["id"])
        child_summaries.append({
            "id": child["id"],
            "name": child["name"],
            "color": child["color"],
            "core_focus_count": core_focus_count,
            "change_pct": cm.get("change_pct") if cm else None,
            "turnover": cm.get("turnover") if cm else None,
        })

    return jsonify({
        "ok": True,
        "data": {
            "sector": sector,
            "stocks": direct_stocks,
            "children": child_summaries,
        },
    })


@bp.route("/api/sectors/<int:sector_id>/notes", methods=["GET"])
@_safe
def api_sector_notes(sector_id: int):
    """返回该板块(含子板块)所有股票的笔记,按 stock_code 索引。

    单 SQL 走 idx_notes_stock 索引,板块大小 50-200 只股时
    延迟 ~2-5ms,远低于 N 次 /api/stocks/<code>/notes 串行。
    """
    from src.db import get_sector, get_notes_for_sector
    if not get_sector(sector_id):
        return jsonify({"ok": False, "error": "板块不存在"}), 404
    notes_by_stock = get_notes_for_sector(sector_id)
    return jsonify({
        "ok": True,
        "data": {
            "notes_by_stock": notes_by_stock,
        },
    })


@bp.route("/api/sectors", methods=["POST"])
@_safe
def api_create_sector():
    from src.db import create_sector
    data = request.get_json(silent=True) or {}
    sector = create_sector({
        "name": data.get("name", "").strip(),
        "parent_id": data.get("parent_id"),
        "color": data.get("color", "#6b7280"),
        "sort_order": int(data.get("sort_order", 0)),
    })
    return jsonify({"ok": True, "data": sector}), 201


@bp.route("/api/sectors/<int:sector_id>", methods=["PUT"])
@_safe
def api_update_sector(sector_id: int):
    from src.db import update_sector, get_sector
    if not get_sector(sector_id):
        return jsonify({"ok": False, "error": "板块不存在"}), 404
    data = request.get_json(silent=True) or {}
    sector = update_sector(sector_id, data)
    return jsonify({"ok": True, "data": sector})


@bp.route("/api/sectors/<int:sector_id>", methods=["DELETE"])
@_safe
def api_delete_sector(sector_id: int):
    from src.db import delete_sector, get_sector
    if not get_sector(sector_id):
        return jsonify({"ok": False, "error": "板块不存在"}), 404
    delete_sector(sector_id)
    return jsonify({"ok": True})


# =============================================================================
# Sector Stocks（标的-板块关联）
# =============================================================================

@bp.route("/api/sectors/<int:sector_id>/stocks", methods=["GET"])
@_safe
def api_sector_stocks(sector_id: int):
    from src.db import get_sector, get_sector_stocks
    if not get_sector(sector_id):
        return jsonify({"ok": False, "error": "板块不存在"}), 404
    stocks = get_sector_stocks(sector_id)
    stocks = _enrich_stocks(stocks)
    return jsonify({"ok": True, "data": stocks})


@bp.route("/api/sectors/<int:sector_id>/stocks", methods=["POST"])
@_safe
def api_add_stock_to_sector(sector_id: int):
    from src.db import add_stock_to_sector, get_sector
    from src.cache_invalidator import invalidate_a_share_pool, recompute_sector_aggregator
    if not get_sector(sector_id):
        return jsonify({"ok": False, "error": "板块不存在"}), 404
    data = request.get_json(silent=True) or {}
    stock_code = (data.get("stock_code") or "").strip()
    if not stock_code:
        return jsonify({"ok": False, "error": "stock_code 必填"}), 400
    label = data.get("label", "observation")
    if label not in ("core", "focus", "monitor", "associate"):
        return jsonify({"ok": False, "error": "label 必须是 core/focus/monitor/associate 之一"}), 400
    # 确保 stock 已录入本地缓存（港美股转为 YF 格式，A 股走 eltdx）
    from src import stocks as stocks_mod
    from src.db import get_db, _row_to_dict, upsert_stock
    from src.yf import get_quote, _to_yf_symbol

    if _is_yf_code(stock_code):
        yf_sym = _to_yf_symbol(stock_code) or stock_code
        yf_data = get_quote(yf_sym)
        name = (yf_data.get("long_name") or yf_sym) if yf_data else yf_sym
        board = "HK" if stock_code.endswith(".HK") else "US"
        upsert_stock({
            "code": yf_sym,
            "exchange": board,
            "name": name,
            "board": board,
            "board_name": board,
        })
        result = add_stock_to_sector(sector_id, yf_sym, label)
        # YF 池子由 YfCache 30s tick 自动重载;A 股池子不变但 Aggregator 的
        # sector_stocks 缓存要立即刷,否则用户加完 HK 股后看板块 metrics 还是旧的
        recompute_sector_aggregator()
    else:
        stocks_mod.add_stock(stock_code)
        result = add_stock_to_sector(sector_id, stock_code, label)
        # 通知 A 股 cache 池子变化 (QuoteCache 拉 quote, ProfileCache 拉 profile)
        # + Aggregator 立即重算
        invalidate_a_share_pool()
        recompute_sector_aggregator()
    return jsonify({"ok": True, "data": result}), 201


@bp.route("/api/sectors/<int:sector_id>/stocks/<code>", methods=["PUT"])
@_safe
def api_update_sector_stock(sector_id: int, code: str):
    from src.db import update_sector_stock
    from src.cache_invalidator import recompute_sector_aggregator
    data = request.get_json(silent=True) or {}
    if "label" in data and data["label"] not in ("core", "focus", "monitor", "associate"):
        return jsonify({"ok": False, "error": "label 必须是 core/focus/monitor/associate 之一"}), 400
    result = update_sector_stock(sector_id, code, data)
    if not result:
        return jsonify({"ok": False, "error": "关联不存在"}), 404
    # label 改影响 Aggregator 聚合范围(只计 core/focus 等),池子本身没变但要立即重算
    if "label" in data:
        recompute_sector_aggregator()
    return jsonify({"ok": True, "data": result})


@bp.route("/api/sectors/<int:sector_id>/stocks/reorder", methods=["PUT"])
@_safe
def api_reorder_sector_stocks(sector_id: int):
    from src.db import reorder_sector_stocks, get_sector
    if not get_sector(sector_id):
        return jsonify({"ok": False, "error": "板块不存在"}), 404
    data = request.get_json(silent=True) or {}
    codes = data.get("codes")
    if not isinstance(codes, list):
        return jsonify({"ok": False, "error": "codes 必须是列表"}), 400
    reorder_sector_stocks(sector_id, codes)
    return jsonify({"ok": True})


@bp.route("/api/sectors/<int:sector_id>/stocks/<code>", methods=["DELETE"])
@_safe
def api_remove_stock_from_sector(sector_id: int, code: str):
    from src.db import remove_stock_from_sector
    removed = remove_stock_from_sector(sector_id, code)
    if not removed:
        return jsonify({"ok": False, "error": "关联不存在"}), 404
    # 通知 A 股 cache 池子变化
    if not _is_yf_code(code):
        from src.quote_cache import CACHE as QUOTE_CACHE
        from src.profile_cache import CACHE as PROFILE_CACHE
        QUOTE_CACHE.invalidate_pool()
        PROFILE_CACHE.invalidate_pool()
    return jsonify({"ok": True})


# =============================================================================
# Stocks（股票）
# =============================================================================

@bp.route("/api/stocks/search", methods=["GET"])
@_safe
def api_stocks_search():
    """搜索股票。优先从 eltdx A 股代码表查，搜索词以 hk/us 开头时直接查 Yahoo Finance。"""
    from src import stocks as stocks_mod
    from src.yf import get_quote
    q = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", 20)), 100)
    if not q:
        return jsonify({"ok": True, "data": [], "query": ""})

    # 港美股搜索：直接查 Yahoo Finance
    if _is_yf_code(q):
        yf_data = get_quote(q)
        if yf_data and yf_data.get("last_price"):
            return jsonify({
                "ok": True, "query": q, "count": 1, "data": [{
                    "code": q,
                    "name": yf_data.get("yf_symbol", q.upper()),
                    "board_name": yf_data.get("currency", ""),
                }]
            })

    results = stocks_mod.search(q, limit=limit)
    return jsonify({"ok": True, "query": q, "count": len(results), "data": results})


@bp.route("/api/stocks", methods=["POST"])
@_safe
def api_add_stock():
    """添加股票到自选。港美股转为 YF 格式存储，A 股走 eltdx 补全。"""
    from src import stocks as stocks_mod
    from src.db import upsert_stock, get_db
    from src.yf import get_quote, _to_yf_symbol

    code = (request.form.get("code") or request.get_json(silent=True).get("code") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "code 必填"}), 400

    if _is_yf_code(code):
        yf_sym = _to_yf_symbol(code)
        yf_data = get_quote(yf_sym) if yf_sym else None
        name = (yf_data.get("long_name") or yf_sym) if yf_data else code
        board = "HK" if (code.endswith(".HK") or code.lower().startswith("hk")) else "US"
        conn = get_db()
        stock = upsert_stock({
            "code": yf_sym or code,
            "exchange": board,
            "name": name,
            "board": board,
            "board_name": board,
        })
        return jsonify({"ok": True, "data": stock}), 201

    # A 股走 eltdx
    result = stocks_mod.add_stock(code)
    return jsonify({"ok": True, "data": result}), 201


@bp.route("/api/stocks/<code>", methods=["GET"])
@_safe
def api_stock_detail(code: str):
    """单只股票：本地缓存信息 + 实时行情（A股用 eltdx，港美股用 Yahoo Finance）。"""
    from src import stocks as stocks_mod
    from src.db import get_db

    # 港美股优先读 YfCache (后台 30s 批量拉),miss 才回退单只直打 YF
    if _is_yf_code(code):
        from src.yf import get_quote, enrich_yf_quote, _to_yf_symbol
        from src.yf_cache import CACHE as YF_CACHE
        yf_sym = _to_yf_symbol(code)
        conn = get_db()
        row = conn.execute("SELECT name, board_name FROM stocks WHERE code=?", (code,)).fetchone()
        name = row["name"] if row else code
        board_name = row["board_name"] if row else ""
        yf_raw = YF_CACHE.get(yf_sym) if yf_sym else None
        if yf_raw is None:
            # cache miss: YfCache 还没拉到这只(刚加或 cold start),直打 YF 兜底
            yf_raw = get_quote(yf_sym) if yf_sym else None
        yf_data = enrich_yf_quote(yf_raw, code)
        return jsonify({
            "ok": True,
            "data": {
                "code": code,
                "name": name,
                "board_name": board_name,
                "quote": yf_data,
            }
        })

    # A股走 QuoteCache (daemon 3s 拉一次, 5s TTL 复用)
    # 池子里没这只股票时 (e.g. 刚加还没拉), 走 eltdx 单只拉一次回写 cache
    from src.quote_cache import CACHE as QUOTE_CACHE
    from src.core import normalize_code_ck
    import time as _time
    ck_code = normalize_code_ck(code)
    cached_quote = QUOTE_CACHE.get_recent(ck_code)
    if cached_quote is not None:
        print(f"[quote_cache] api_stock_detail {ck_code} CACHE HIT", flush=True)
        info = stocks_mod.get_stock_info(code, quote_override=cached_quote)
    else:
        # CACHE MISS / TTL 过期 / 不在池子
        # I3: 5s cooldown 内同 code 重复 miss 不再打 eltdx,直接返 None
        now = _time.time()
        with _MISS_LOCK:
            last_miss = _MISS_COOLDOWN.get(ck_code, 0)
            in_cooldown = (now - last_miss) < _MISS_COOLDOWN_S
        if in_cooldown:
            print(f"[quote_cache] api_stock_detail {ck_code} CACHE MISS (cooldown, skip eltdx)", flush=True)
            info = None
        else:
            with _MISS_LOCK:
                _MISS_COOLDOWN[ck_code] = now
            # eltdx 单只拉一次
            info = stocks_mod.get_stock_info(code)
            if info and info.get("quote"):
                QUOTE_CACHE.put_recent(ck_code, info["quote"])
                print(f"[quote_cache] api_stock_detail {ck_code} CACHE MISS (called eltdx, wrote back)", flush=True)
            else:
                print(f"[quote_cache] api_stock_detail {ck_code} CACHE MISS (called eltdx, no quote)", flush=True)
    if not info:
        return jsonify({"ok": False, "error": "股票不在自选列表中，请先添加"}), 404
    # 注入换手率/市值 (来自 profile_cache, eltdx 本地按 成交股数/流通股本*100 算)
    from src.profile_cache import CACHE as PROFILE_CACHE
    profile = PROFILE_CACHE.get(ck_code)
    if profile and info.get("quote"):
        info["quote"]["turnover_rate"] = profile.get("turnover_rate")
        info["quote"]["total_mv"] = profile.get("total_market_value")
        info["quote"]["circ_mv"] = profile.get("circulating_market_value")
    return jsonify({"ok": True, "data": info})


# —— 批量 quote ————————————————————————————————————————
# C7: 前端 3s tick 原来 forEach fetchQuote 每个 stock 一次 HTTP。
# 这个端点一次返 N 只的 quote,内部只读 cache,不调外部 — 完全无 IO 开销。
# 上限 200 只防滥用。

@bp.route("/api/stocks/quotes", methods=["GET"])
@_safe
def api_stocks_quotes_batch():
    """GET /api/stocks/quotes?codes=sh.600519,sz.000001,00700.HK — 批量 quote.

    - A 股从 QuoteCache 读(daemon 3s tick 维护,完全无网络)
    - 港美股从 YfCache 读(30s tick 维护,完全无网络)
    - miss 返回 null,前端用 stale 数据兜底

    响应: {ok: True, data: {code: {last_price, change, change_pct, ...} | null}}
    """
    from src.quote_cache import CACHE as QUOTE_CACHE
    from src.yf_cache import CACHE as YF_CACHE
    from src.core import normalize_code_ck
    from src.yf import _to_yf_symbol
    from src.errors import BadRequest
    from src.profile_cache import CACHE as PROFILE_CACHE

    codes_raw = request.args.get("codes", "").strip()
    if not codes_raw:
        raise BadRequest("codes 必填,逗号分隔")
    codes = [c.strip() for c in codes_raw.split(",") if c.strip()]
    if not codes:
        raise BadRequest("codes 不能为空")
    if len(codes) > 200:
        raise BadRequest("一次最多 200 只")

    out: dict[str, dict | None] = {}
    for code in codes:
        if _is_yf_code(code):
            yf_sym = _to_yf_symbol(code)
            q = YF_CACHE.get(yf_sym) if yf_sym else None
        else:
            ck = normalize_code_ck(code)
            q = QUOTE_CACHE.get_quote(ck)
            if q:
                profile = PROFILE_CACHE.get(ck)
                if profile:
                    q["turnover_rate"] = profile.get("turnover_rate")
                    q["total_mv"] = profile.get("total_market_value")
                    q["circ_mv"] = profile.get("circulating_market_value")
        out[code] = q
    return jsonify({"ok": True, "data": out})


# =============================================================================
# Minute / K线（仅 A 股）
# =============================================================================

@bp.route("/api/stocks/<code>/minute", methods=["GET"])
@_safe
def api_stock_minute(code: str):
    """当日分时数据。A 股用 eltdx，港美股用 Yahoo Finance 5m K 线。"""
    from src.core import get_client, normalize_code_ck, _clean

    if _is_yf_code(code):
        from src.yf import get_kline, get_quote, _to_yf_symbol
        from datetime import datetime, timezone, timedelta
        yf_sym = _to_yf_symbol(code)
        if not yf_sym:
            return jsonify({"ok": False, "error": "无效代码"}), 400

        # 用 yf_sym 判定 exchange（兼容 hk00700 / 0700.HK 两种输入）
        exchange = "HK" if yf_sym.endswith(".HK") else "US"

        # 拿 5m 数据作为分时（YF URL 已加 includePrePost=false，过滤 pre/after-market）
        kline_data = get_kline(code, "5m", 100)
        if not kline_data or not kline_data.get("bars"):
            return jsonify({"ok": False, "error": "暂无分时数据"}), 400

        bars = kline_data["bars"]
        tz = timezone(timedelta(hours=8))  # YF 5m bar 时间戳转 HKT

        # 昨收和今开：从当日第一根5m bar之前的价格
        yf_quote = get_quote(yf_sym)
        last_price = yf_quote.get("last_price") if yf_quote else None
        change_val = yf_quote.get("change") if yf_quote else None
        prev_close = (last_price - change_val) if (last_price and change_val is not None) else None

        # 今开：当日第一根5m bar的开盘价
        open_price = bars[0].get("open") if bars else None

        # 成交额：∑(收盘价 × 成交量)
        amount = sum((b.get("close") or 0) * (b.get("volume") or 0) for b in bars)

        # 转换 bars → points
        # includePrePost=false 已过滤 pre/after-market, 这里再防御性过滤港股午休
        seen_labels = set()
        points = []
        for b in bars:
            if not b.get("time"):
                continue
            price = b.get("close")
            if price is None:
                continue
            dt_utc = datetime.fromisoformat(b["time"]).astimezone(timezone.utc)
            dt_local = dt_utc.astimezone(tz)
            h = dt_local.hour
            # 港股午休防御性过滤（YF 不会返回,这里只是兜底）
            if h == 12:
                continue
            time_label = dt_local.strftime("%H:%M")
            if time_label in seen_labels:
                continue
            seen_labels.add(time_label)
            points.append({
                "time_label": time_label,
                "price": price,
                "avg_price": None,
                "volume": b.get("volume"),
            })

        return jsonify({"ok": True, "data": {
            "code": code,
            "exchange": exchange,
            "trading_date": None,
            "prev_close": prev_close,
            "open_price": open_price,
            "amount": amount if amount > 0 else None,
            "points": points,
        }})

    # A 股
    ck = normalize_code_ck(code).replace(".", "")
    try:
        client = get_client()
        series = client.get_minute(ck)
        data = _clean(series)
        prev_close = data.get("prev_close")
        if not prev_close:
            snaps = client.get_quote([ck])
            if snaps:
                prev_close = _clean(snaps[0]).get("pre_close_price")
        # eltdx 跳过了 9:30 集合竞价那根 1m bar，从 9:31 开始；最后 1m bar 也不一定是 15:00。
        # 前端用 idx 映射时间（0=09:30, 121=13:00, 末端=15:00），
        # 必须在 points 两端各补一根占位 bar，让 idx 与 label 精确对齐。
        points = data.get("points", [])
        if points:
            first_label = points[0].get("time_label", "")
            if first_label and first_label != "09:30":
                open_p = (
                    data.get("open_price")
                    or prev_close
                    or points[0].get("price")
                    or 0
                )
                points = [
                    {"time_label": "09:30", "price": open_p, "avg_price": open_p, "volume": 0}
                ] + points
            last_label = points[-1].get("time_label", "")
            if last_label and last_label != "15:00":
                last_p = points[-1].get("price") or 0
                points = points + [
                    {"time_label": "15:00", "price": last_p, "avg_price": last_p, "volume": 0}
                ]
        return jsonify({"ok": True, "data": {
            "code": data.get("code"),
            "exchange": data.get("exchange"),
            "trading_date": data.get("trading_date"),
            "prev_close": prev_close,
            "open_price": data.get("open_price"),
            "points": points,
        }})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/stocks/<code>/kline", methods=["GET"])
@_safe
def api_stock_kline(code: str):
    """K 线数据。A 股用 eltdx，港美股用 Yahoo Finance。"""
    period = request.args.get("period", "day")
    count = min(int(request.args.get("count", 300)), 1000)
    adjust = request.args.get("adjust", "qfq")

    if _is_yf_code(code):
        from src.yf import get_kline
        data = get_kline(code, period=period, count=count)
        if not data:
            return jsonify({"ok": False, "error": "获取K线失败"}), 500
        return jsonify({"ok": True, "data": data})

    from src.core import get_client, normalize_code_ck
    ck = normalize_code_ck(code).replace(".", "")
    try:
        client = get_client()
        series = client.bars.get(ck, period=period, count=count, adjust=adjust)
        bars = []
        for b in series.bars:
            bars.append({
                "time": b.time.isoformat() if b.time else None,
                "open": b.open,
                "close": b.close,
                "high": b.high,
                "low": b.low,
                "volume": b.volume_lots,
                "amount": b.amount,
            })

        # —— 今日涨跌停价 (K 线 tooltip 用) ——
        # 优先从 quote_cache 取,miss 才打 eltdx (5s TTL 内复用,避免每条 K 线都打)
        from src.quote_cache import CACHE as QUOTE_CACHE
        from src.limit_price import calc_limit
        cached = QUOTE_CACHE.get_recent(code)
        pre_close_now = (cached or {}).get("pre_close")
        if pre_close_now is None:
            # fallback: eltdx 单拉
            try:
                q = client.get_quote([ck])[0]
                pre_close_now = getattr(q, "pre_close_price", None)
            except Exception:
                pre_close_now = None
        # 用 CK 标准格式 (带点) 喂给 calc_limit,plate_of 才能识别 bse
        limit_up, limit_down = calc_limit(pre_close_now, normalize_code_ck(code))

        return jsonify({"ok": True, "data": {
            "code": series.code,
            "exchange": series.exchange,
            "period": series.period_name,
            "bars": bars,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "pre_close": pre_close_now,
        }})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# Notes（笔记）
# =============================================================================

@bp.route("/api/stocks/<code>/notes", methods=["GET"])
@_safe
def api_stock_notes(code: str):
    from src.db import get_notes_for_stock
    notes = get_notes_for_stock(code)
    return jsonify({"ok": True, "data": notes})


@bp.route("/api/stocks/<code>/notes", methods=["POST"])
@_safe
def api_create_note(code: str):
    from src.db import create_note, get_stock
    from src.errors import BadRequest
    if not get_stock(code):
        return jsonify({"ok": False, "error": "股票不在自选列表中"}), 404
    data = request.get_json(silent=True) or {}
    # I5: 与 API.md 文档对齐的字段长度限制
    title = data.get("title") or ""
    body = data.get("body") or ""
    tags = data.get("tags") or []
    if isinstance(title, str) and len(title) > 15:
        raise BadRequest(f"title 最多 15 字,当前 {len(title)}")
    if isinstance(body, str) and len(body) > 300:
        raise BadRequest(f"body 最多 300 字,当前 {len(body)}")
    if not isinstance(tags, list):
        raise BadRequest("tags 必须是数组")
    if len(tags) > 10:
        raise BadRequest(f"tags 最多 10 个,当前 {len(tags)}")
    note = create_note(code, data)
    return jsonify({"ok": True, "data": note}), 201


@bp.route("/api/notes/<int:note_id>", methods=["GET"])
@_safe
def api_get_note(note_id: int):
    from src.db import get_note
    note = get_note(note_id)
    if not note:
        return jsonify({"ok": False, "error": "笔记不存在"}), 404
    return jsonify({"ok": True, "data": note})


@bp.route("/api/notes/<int:note_id>", methods=["PUT"])
@_safe
def api_update_note(note_id: int):
    from src.db import update_note, get_note
    from src.errors import BadRequest
    if not get_note(note_id):
        return jsonify({"ok": False, "error": "笔记不存在"}), 404
    data = request.get_json(silent=True) or {}
    # I5: 与 create_note 一致的长度限制(只校验提供的字段)
    if "title" in data:
        title = data["title"] or ""
        if isinstance(title, str) and len(title) > 15:
            raise BadRequest(f"title 最多 15 字,当前 {len(title)}")
    if "body" in data:
        body = data["body"] or ""
        if isinstance(body, str) and len(body) > 300:
            raise BadRequest(f"body 最多 300 字,当前 {len(body)}")
    if "tags" in data:
        tags = data["tags"]
        if tags is not None and not isinstance(tags, list):
            raise BadRequest("tags 必须是数组")
        if isinstance(tags, list) and len(tags) > 10:
            raise BadRequest(f"tags 最多 10 个,当前 {len(tags)}")
    note = update_note(note_id, data)
    return jsonify({"ok": True, "data": note})


@bp.route("/api/notes/<int:note_id>", methods=["DELETE"])
@_safe
def api_delete_note(note_id: int):
    from src.db import delete_note, get_note
    if not get_note(note_id):
        return jsonify({"ok": False, "error": "笔记不存在"}), 404
    delete_note(note_id)
    return jsonify({"ok": True})


@bp.route("/api/stocks", methods=["GET"])
@_safe
def api_all_stocks():
    """GET /api/stocks — 返回系统全部股票列表（stocks 表，不含行情）。"""
    from src.db import get_all_stocks
    stocks = get_all_stocks()
    return jsonify({"ok": True, "data": stocks, "count": len(stocks)})


@bp.route("/api/stocks/<code>/sectors", methods=["GET"])
@_safe
def api_stock_sectors(code: str):
    """GET /api/stocks/:code/sectors — 返回该股票所属的全部板块。"""
    from src.db import get_stock_sectors
    sectors = get_stock_sectors(code)
    return jsonify({"ok": True, "data": sectors, "count": len(sectors)})


@bp.route("/api/stocks/<code>/sectors", methods=["PUT"])
@_safe
def api_move_stock_sector(code: str):
    """PUT /api/stocks/:code/sectors — 将股票从源板块移到目标板块。

    Body: { from_sector_id: int, to_sector_id: int, label?: str }
    """
    from src.db import move_stock_sector
    from src.cache_invalidator import on_sector_stocks_mutated
    from src.errors import BadRequest, NotFound
    data = request.get_json(silent=True) or {}
    from_sid = data.get("from_sector_id")
    to_sid = data.get("to_sector_id")
    if from_sid is None or to_sid is None:
        raise BadRequest("from_sector_id 和 to_sector_id 必须提供")
    label = data.get("label", "observation")
    if label not in ("core", "focus", "monitor", "associate"):
        raise BadRequest("label 无效")
    try:
        result = move_stock_sector(code, int(from_sid), int(to_sid), label)
    except (TypeError, ValueError):
        raise BadRequest("from_sector_id / to_sector_id 必须是整数")
    if not result:
        raise NotFound("股票与源板块的关联不存在")
    # sector_stocks 改了 — 池子和聚合都要失效
    on_sector_stocks_mutated()
    return jsonify({"ok": True, "data": result})


@bp.route("/api/sectors/<int:sector_id>/stocks/batch", methods=["POST"])
@_safe
def api_batch_add_stocks(sector_id: int):
    """POST /api/sectors/:id/stocks/batch — 批量添加多只股票到同一板块。

    Body: { stocks: [{stock_code: str, label: str}, ...] }
    """
    from src.db import batch_add_stocks, get_sector
    from src.cache_invalidator import on_sector_stocks_mutated
    if not get_sector(sector_id):
        return jsonify({"ok": False, "error": "板块不存在"}), 404
    data = request.get_json(silent=True) or {}
    stocks = data.get("stocks", [])
    if not isinstance(stocks, list):
        return jsonify({"ok": False, "error": "stocks 必须是列表"}), 400
    result = batch_add_stocks(sector_id, stocks)
    # sector_stocks 改了 — 池子和聚合都要失效(A 股 + YF 都包含,统一调)
    on_sector_stocks_mutated()
    return jsonify({"ok": True, "data": result, "count": len(result)})


@bp.route("/api/stocks/<code>/notes", methods=["DELETE"])
@_safe
def api_delete_notes_for_stock(code: str):
    """DELETE /api/stocks/:code/notes — 删除该股票的全部笔记。"""
    from src.db import delete_notes_for_stock
    count = delete_notes_for_stock(code)
    return jsonify({"ok": True, "deleted": count})


@bp.route("/api/notes/<int:note_id>/move", methods=["PUT"])
@_safe
def api_move_note(note_id: int):
    """PUT /api/notes/:id/move — 将笔记移动到另一股票。

    Body: { stock_code: str }
    """
    from src.db import move_note_to_stock, get_note
    if not get_note(note_id):
        return jsonify({"ok": False, "error": "笔记不存在"}), 404
    data = request.get_json(silent=True) or {}
    target = (data.get("stock_code") or "").strip()
    if not target:
        return jsonify({"ok": False, "error": "stock_code 必须提供"}), 400
    result = move_note_to_stock(note_id, target)
    return jsonify({"ok": True, "data": result})

