import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from models import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db("sqlite:///data/business_system.db")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="ShanYin ERP API",
        description="AI Agent 友好的山银业务管理系统 API",
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
    cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    from api.routers import system, master, business, supply_chain, virtual_contract, logistics, finance, rules, query, inventory, events, partner_relations, raw_query
    for mod in [system, master, business, supply_chain, virtual_contract, logistics, finance, rules, query, inventory, events, partner_relations, raw_query]:
        app.include_router(mod.router)

    return app
