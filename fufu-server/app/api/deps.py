"""
fufu新闻 - API 依赖注入
==========================
FastAPI 依赖注入函数，用于认证、授权和数据库会话注入。

核心函数：
- get_current_user: 从 JWT Bearer Token 中解析当前登录用户
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

# HTTP Bearer Token 认证方案
# auto_error=False 意味着即使没有提供 Token 也不会自动抛出 401，
# 而是返回 None，让 get_current_user 自行处理
bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    获取当前登录用户——FastAPI 依赖注入函数。

    从请求头的 Authorization: Bearer <token> 中提取 JWT，
    解码后查询对应的 User 记录并返回。

    参数:
        credentials: 从请求头解析的 Bearer Token 凭证（可空）
        db: 数据库会话（由 get_db 依赖注入）

    返回:
        User: 当前认证的用户 ORM 实例

    异常:
        HTTPException(401): 未提供 Token / Token 无效 / Token 过期 / 用户不存在
    """
    # 没有提供 Token
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录哦～")

    # 解码 JWT Token
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录过期啦，请重新登录～")

    # 从 JWT 中提取用户名（sub 字段）
    username: str | None = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录信息异常～")

    # 查询数据库中的用户
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在啦～")

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    获取可选当前用户——FastAPI 依赖注入函数。
    与 get_current_user 类似，但未登录时返回 None 而不是抛出 401。

    用于需要知道用户身份但允许匿名访问的端点（如查看评论列表时
    需要判断当前用户是否已点赞，但未登录也可以查看）。

    参数:
        credentials: 从请求头解析的 Bearer Token 凭证（可空）
        db: 数据库会话（由 get_db 依赖注入）

    返回:
        User | None: 当前认证的用户 ORM 实例，未登录时为 None
    """
    if credentials is None:
        return None

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None

    username: str | None = payload.get("sub")
    if username is None:
        return None

    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()
