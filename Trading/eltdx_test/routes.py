"""Flask Blueprint：所有 HTTP 接口。"""

from flask import Blueprint, jsonify, render_template, request

from eltdx.exceptions import ProtocolError

from src.config_loader import (
    UI_DEFAULT_CODE,
    UI_REFRESH_SECONDS,
)
from src.core import fetch_all, fetch_depth, fetch_minute, fetch_quote

bp = Blueprint("eltdx_test", __name__)


def _safe(handler):
    """装饰器：把任何异常转为 {ok:false, error:...} JSON 响应。"""
    import functools

    @functools.wraps(handler)
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except ProtocolError as e:
            return jsonify({"ok": False, "error": f"协议错误：{e}"}), 400
        except ValueError as e:
            return jsonify({"ok": False, "error": f"参数错误：{e}"}), 400
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

    return wrapper


@bp.route("/")
def index():
    """单页 UI。"""
    return render_template(
        "index.html",
        refresh_seconds=UI_REFRESH_SECONDS,
        default_code=UI_DEFAULT_CODE,
    )


@bp.route("/api/config")
def api_config():
    """前端拉取 UI 配置（刷新频率、默认代码、预设）。"""
    return jsonify(
        {
            "ok": True,
            "refresh_seconds": UI_REFRESH_SECONDS,
            "default_code": UI_DEFAULT_CODE,
            "presets": UI_PRESETS,
        }
    )


@bp.route("/api/quote")
@_safe
def api_quote():
    code = request.args.get("code", UI_DEFAULT_CODE)
    return jsonify(fetch_quote(code))


@bp.route("/api/minute")
@_safe
def api_minute():
    code = request.args.get("code", UI_DEFAULT_CODE)
    return jsonify(fetch_minute(code))


@bp.route("/api/depth")
@_safe
def api_depth():
    code = request.args.get("code", UI_DEFAULT_CODE)
    return jsonify(fetch_depth(code))


@bp.route("/api/all")
@_safe
def api_all():
    """前端轮询主入口：一次返回报价+分时+五档。"""
    code = request.args.get("code", UI_DEFAULT_CODE)
    return jsonify(fetch_all(code))


@bp.route("/api/kline")
@_safe
def api_kline():
    """K 线。参数：code, period (day/week/month/5min/...), count, adjust (qfq/hfq/none)"""
    from src.core import fetch_kline

    code = request.args.get("code", UI_DEFAULT_CODE)
    period = request.args.get("period", "day")
    count = min(int(request.args.get("count", 500)), 5000)
    adjust = request.args.get("adjust", "qfq")
    if adjust in ("none", ""):
        adjust = None
    return jsonify(fetch_kline(code, period=period, count=count, adjust=adjust))


@bp.route("/api/health")
def api_health():
    """健康检查（含 TdxClient 是否就绪）。"""
    from src.core import get_client

    try:
        get_client()
        return jsonify({"ok": True, "client": "ready"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503


@bp.route("/api/stocks/meta")
def api_stocks_meta():
    """代码表元信息：updated_at、count、source。"""
    from src import stocks as stocks_mod
    return jsonify({"ok": True, "data": stocks_mod.get_meta()})


@bp.route("/api/stocks/search")
def api_stocks_search():
    """智能搜索：code / 中文 / 拼音首字母。

    范例：
      /api/stocks/search?q=000001
      /api/stocks/search?q=平安
      /api/stocks/search?q=pay  (平安银行)
      /api/stocks/search?q=gzmt (贵州茅台)
    """
    from src import stocks as stocks_mod
    q = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", 20)), 100)
    if not q:
        return jsonify({"ok": True, "data": [], "query": ""})
    results = stocks_mod.search(q, limit=limit)
    # 去掉调试字段
    cleaned = [
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in results
    ]
    return jsonify({"ok": True, "query": q, "count": len(cleaned), "data": cleaned})