import os

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from models import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    init_db("sqlite:///data/business_system.db")

    # 确保存在默认 admin 用户
    try:
        from logic.auth import ensure_admin_exists
        ensure_admin_exists()
    except Exception as e:
        print(f"[Warning] Failed to ensure admin exists: {e}")

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="ShanYin ERP API",
        description="AI Agent 友好的闪饮业务管理系统 API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 注册中间件（注意：执行顺序是从下往上，所以错误处理在最前面）
    from api.middleware import ErrorHandlerMiddleware, ResponseWrapperMiddleware

    # 响应包装中间件 - 确保所有响应都是标准格式
    app.add_middleware(ResponseWrapperMiddleware)

    # 统一错误处理中间件 - 捕获所有异常并返回标准化错误
    app.add_middleware(ErrorHandlerMiddleware)

    # CORS 配置：从环境变量读取允许的来源列表，默认仅本地开发
    cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost,http://127.0.0.1,http://localhost:*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    # 导入路由模块
    from api.routers import system, master, business, supply_chain, virtual_contract, logistics, finance, rules, query, inventory, events, partner_relations, raw_query, auth

    # 认证路由（公开）
    app.include_router(auth.router)

    # 业务路由（需要认证）- 通过 dependencies 全局添加认证
    from api.deps import verify_token
    protected_router_dependencies = [Depends(verify_token)]

    for mod in [system, master, business, supply_chain, virtual_contract, logistics, finance, rules, query, inventory, events, partner_relations, raw_query]:
        app.include_router(mod.router, dependencies=protected_router_dependencies)

    return app


app = create_app()
