"""Flask 入口。"""

from flask import Flask

from routes import bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(bp)
    return app


app = create_app()


def _bootstrap():
    """启动钩子：初始化数据库、TdxClient 预热、所有 cache 启动 + Aggregator 接线。"""
    from src.db import init_db
    from src.core import get_client
    from src.yf_cache import CACHE as YF_CACHE
    from src.quote_cache import CACHE as QUOTE_CACHE
    from src.profile_cache import CACHE as PROFILE_CACHE
    from src.indices_cache import CACHE as INDICES_CACHE
    from src.sector_aggregator import AGGREGATOR

    init_db()
    print("[stock_watchlist] 数据库初始化完成", flush=True)

    try:
        get_client()
        print("[stock_watchlist] TdxClient 预热完成", flush=True)
    except Exception as e:
        print(f"[stock_watchlist] TdxClient 预热失败（不影响核心功能）：{e}", flush=True)

    YF_CACHE.start()
    s = YF_CACHE.stats()
    print(f"[stock_watchlist] YfCache 启动: codes={s['tracked']} cached={s['cached']}", flush=True)

    QUOTE_CACHE.start()
    s = QUOTE_CACHE.stats()
    print(f"[stock_watchlist] QuoteCache 启动: tracked={s['tracked']} cached={s['cached']}", flush=True)

    PROFILE_CACHE.start()
    s = PROFILE_CACHE.stats()
    print(f"[stock_watchlist] ProfileCache 启动: tracked={s['tracked']} cached={s['cached']}", flush=True)

    INDICES_CACHE.start()
    s = INDICES_CACHE.stats()
    print(f"[stock_watchlist] IndicesCache 启动: tracked={s['tracked']} cached={s['cached']}", flush=True)

    # Aggregator 订阅 QuoteCache.on_refresh (3s tick 后重算板块)
    AGGREGATOR.attach(QUOTE_CACHE, PROFILE_CACHE)
    # 立即算一次 (不依赖首次 quote tick)
    AGGREGATOR.recompute()
    print(f"[stock_watchlist] SectorAggregator 启动: sectors={len(AGGREGATOR.get_all_metrics())}", flush=True)


if __name__ == "__main__":
    from src.config_loader import SERVER_HOST, SERVER_PORT

    print(f"[stock_watchlist] 启动: http://{SERVER_HOST}:{SERVER_PORT}")
    _bootstrap()
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, use_reloader=False)
