"""Flask 入口。"""

from flask import Flask

from routes import bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(bp)
    return app


app = create_app()


def _bootstrap():
    """启动钩子：预热 TdxClient 连接、刷新 A 股代码表。"""
    # 触发 TdxClient 连接（如果代码表刷新失败也能降级使用行情）
    try:
        from src.core import get_client
        get_client()
    except Exception as e:
        print(f"[eltdx_test] TdxClient 预热失败：{e}", flush=True)

    # 刷新 A 股代码表
    try:
        from src import stocks as stocks_mod
        meta = stocks_mod.get_meta()
        print(
            f"[eltdx_test] A 股代码表已就绪: {meta['count']} 只, "
            f"更新于 {meta['updated_at']}",
            flush=True,
        )
    except Exception as e:
        print(f"[eltdx_test] 代码表刷新失败: {e}", flush=True)


if __name__ == "__main__":
    from src.config_loader import SERVER_HOST, SERVER_PORT

    print(f"[eltdx_test] 启动 Flask 服务: http://{SERVER_HOST}:{SERVER_PORT}")
    print("[eltdx_test] 浏览器打开上述地址即可使用")
    _bootstrap()
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, use_reloader=False)