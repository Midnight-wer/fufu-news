"""
fufu新闻 - 认证接口
=======================
提供用户认证相关的 REST API 端点：

- POST /auth/token → 用户登录（OAuth2 密码流程），返回 JWT 访问令牌
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User

# 创建认证路由实例
router = APIRouter(tags=["认证"])


@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    用户登录接口——POST /api/v1/auth/token

    使用 OAuth2 密码凭证流程（表单提交 username + password），
    验证用户名密码后返回 JWT Bearer Token。

    请求格式：application/x-www-form-urlencoded
    参数:
        username: 用户名
        password: 密码

    返回:
        dict: {"access_token": "JWT字符串", "token_type": "bearer"}

    异常:
        HTTPException(401): 用户名或密码错误
    """
    # 查询用户名对应的用户记录
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()

    # 验证密码（使用 bcrypt 比对哈希值）
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码不对哦，再试试看～",
        )

    # 创建 JWT 令牌（sub 字段存储用户名）
    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}
