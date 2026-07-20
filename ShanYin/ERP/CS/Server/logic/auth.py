"""
JWT 认证模块
- 生成 Access Token 和 Refresh Token
- 验证 Token
- 刷新 Token
- 管理 Refresh Token（支持主动失效）
"""
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

import jwt
from sqlalchemy.orm import Session

from models import User, RefreshToken


# JWT 配置
# 注意：生产环境必须设置 JWT_SECRET 环境变量
# 开发环境使用默认密钥（仅供本地开发）
ENV = os.environ.get('ENV', 'development')
IS_PRODUCTION = ENV.lower() in ('production', 'prod')

_JWT_SECRET = os.environ.get('JWT_SECRET')
if IS_PRODUCTION and not _JWT_SECRET:
    raise ValueError(
        "JWT_SECRET environment variable must be set in production. "
        "Generate a secure key: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )

JWT_SECRET = _JWT_SECRET or 'dev-only-secret-key-do-not-use-in-production'
JWT_ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1小时
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7天


def create_access_token(user: User) -> str:
    """生成 Access Token"""
    payload = {
        'sub': str(user.id),
        'username': user.username,
        'role': user.role,
        'type': 'access',
        'exp': datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        'iat': datetime.now(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user: User, db: Session) -> str:
    """生成 Refresh Token 并存储到数据库"""
    token = secrets.token_urlsafe(64)
    expires_at = datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    db_token = RefreshToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
    )
    db.add(db_token)
    db.commit()

    return token


def verify_access_token(token: str) -> Optional[dict]:
    """
    验证 Access Token
    返回 payload dict 或 None（无效/过期）
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_iat": False}  # 禁用 iat 验证，避免时间漂移问题
        )
        if payload.get('type') != 'access':
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def refresh_access_token(refresh_token_str: str, db: Session) -> Optional[Tuple[str, str]]:
    """
    用 Refresh Token 换新的 Access Token
    返回 (access_token, refresh_token) 或 None（无效/过期/被撤销）
    """
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token_str,
        RefreshToken.revoked == False,
    ).first()

    if not db_token:
        return None

    if not db_token.is_valid():
        return None

    user = db_token.user
    if not user or not user.is_active:
        return None

    # 生成新的 tokens
    new_access = create_access_token(user)
    new_refresh = create_refresh_token(user, db)

    # 撤销旧的 refresh token
    db_token.revoked = True
    db.commit()

    return new_access, new_refresh


def revoke_refresh_token(refresh_token_str: str, db: Session) -> bool:
    """主动失效一个 Refresh Token"""
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token_str
    ).first()

    if db_token:
        db_token.revoked = True
        db.commit()
        return True
    return False


def revoke_all_user_tokens(user_id: int, db: Session) -> int:
    """撤销用户所有 Refresh Tokens"""
    count = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False,
    ).update({'revoked': True})
    db.commit()
    return count


def get_user_by_id(user_id: int, db: Session) -> Optional[User]:
    """根据 ID 获取用户"""
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def get_user_by_username(username: str, db: Session) -> Optional[User]:
    """根据用户名获取用户"""
    return db.query(User).filter(User.username == username, User.is_active == True).first()


def authenticate_user(username: str, password: str, db: Session) -> Optional[User]:
    """验证用户登录"""
    user = get_user_by_username(username, db)
    if not user:
        return None
    if not user.check_password(password):
        return None
    return user


def create_user(username: str, password: str, role: str = 'user', db: Session = None) -> User:
    """创建新用户"""
    # 如果没有传入 db（从 Session 外部调用），从当前 SessionLocal 获取
    if db is None:
        from models import get_session as _get_session
        db = _get_session()

    user = User(username=username, role=role)
    user.set_password(password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def ensure_admin_exists():
    """确保存在一个 admin 用户（首次启动时调用）"""
    from models import get_session as _get_session
    db = _get_session()
    try:
        admin = db.query(User).filter(User.role == 'admin').first()
        if not admin:
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')  # 默认密码，后续改
            db.add(admin)
            db.commit()
            print("[Auth] Default admin user created: admin / admin123")
    finally:
        db.close()
