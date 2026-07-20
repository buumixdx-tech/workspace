"""
认证路由：用户注册、登录、Token 刷新、用户管理
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from api.deps import get_db, api_success, verify_token, require_admin, get_current_user
from logic.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    refresh_access_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
    create_user,
    get_user_by_username,
)
from models import User


router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


# ==================== Models ====================

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


# ==================== Public Endpoints ====================

@router.post("/login", response_model=LoginResponse, summary="用户登录")
def login(req: LoginRequest, session: Session = Depends(get_db)):
    """用户登录，返回 Access Token 和 Refresh Token"""
    user = authenticate_user(req.username, req.password, session)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user, session)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=60 * 60,
    )


@router.post("/refresh", response_model=LoginResponse, summary="刷新 Token")
def refresh(req: RefreshRequest, session: Session = Depends(get_db)):
    """用 Refresh Token 换取新的 Access Token 和 Refresh Token"""
    result = refresh_access_token(req.refresh_token, session)
    if not result:
        raise HTTPException(status_code=401, detail="Refresh Token 无效或已过期")

    access_token, new_refresh = result
    return LoginResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=60 * 60,
    )


@router.post("/logout", summary="登出")
def logout(req: RefreshRequest, session: Session = Depends(get_db)):
    """登出，撤销 Refresh Token"""
    revoke_refresh_token(req.refresh_token, session)
    return api_success({"message": "已登出"})


@router.get("/debug-log")
def debug_log(msg: str = ""):
    """调试日志写入文件（公开 endpoint）"""
    import os
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "debug_client.log")
    from datetime import datetime
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    return {"success": True}


# ==================== Admin Only Endpoints ====================

@router.post("/register", summary="创建用户（仅 Admin）")
def register(req: RegisterRequest, session: Session = Depends(get_db), _: dict = Depends(require_admin)):
    """创建新用户，仅 Admin 可操作"""
    if get_user_by_username(req.username, session):
        raise HTTPException(status_code=400, detail="用户名已存在")

    if req.role not in ('admin', 'user'):
        raise HTTPException(status_code=400, detail="role 必须是 admin 或 user")

    user = create_user(req.username, req.password, req.role, session)
    return api_success(user.to_dict())


@router.get("/users", summary="用户列表（仅 Admin）")
def list_users(session: Session = Depends(get_db), _: dict = Depends(require_admin)):
    """获取所有用户列表，仅 Admin 可操作"""
    users = session.query(User).all()
    return api_success([u.to_dict() for u in users])


@router.delete("/users/{user_id}", summary="删除用户（仅 Admin）")
def delete_user(user_id: int, session: Session = Depends(get_db), token_data: dict = Depends(require_admin)):
    """删除用户，仅 Admin 可操作"""
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.id == int(token_data.get('sub', 0)):
        raise HTTPException(status_code=400, detail="不能删除自己")

    user.is_active = False
    revoke_all_user_tokens(user_id, session)
    session.commit()

    return api_success({"deleted": user_id})


# ==================== User Endpoints ====================

@router.get("/me", summary="获取当前用户信息")
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户的信息"""
    return api_success(current_user.to_dict())


@router.put("/me/password", summary="修改当前用户密码")
def change_password(req: PasswordChangeRequest, session: Session = Depends(get_db), token_data: dict = Depends(verify_token)):
    """修改当前用户密码"""
    user_id = int(token_data.get('sub'))
    user = session.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not user.check_password(req.old_password):
        raise HTTPException(status_code=400, detail="原密码错误")

    user.set_password(req.new_password)
    revoke_all_user_tokens(user_id, session)
    session.commit()

    return api_success({"message": "密码修改成功，请重新登录"})
