"""
fufu新闻 - 安全工具
=====================
提供密码哈希、密码验证、JWT 令牌的创建与解析功能。

依赖：
- passlib + bcrypt：密码哈希和验证
- python-jose：JWT（JSON Web Token）的创建与解析
"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ========== 密码哈希上下文 ==========
# 使用 bcrypt 算法进行密码哈希
# deprecated="auto" 表示自动处理已弃用的算法（密码验证时会自动升级哈希算法）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    对明文密码进行 bcrypt 哈希。

    参数:
        password: 明文密码字符串

    返回:
        str: bcrypt 哈希后的密码字符串（包含盐值）
    """
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    验证明文密码是否与哈希值匹配。

    参数:
        plain: 用户输入的明文密码
        hashed: 数据库中存储的 bcrypt 哈希值

    返回:
        bool: 匹配返回 True，否则返回 False
    """
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    """
    创建 JWT 访问令牌。

    在传入的数据中注入过期时间（exp），然后使用 HS256 算法和 secret_key 签名。

    参数:
        data: 要编码到 JWT 中的数据字典（例如 {"sub": "用户名"}）

    返回:
        str: 编码后的 JWT 字符串
    """
    # 复制一份，避免修改原始数据
    to_encode = data.copy()
    # 计算过期时间：当前 UTC 时间 + 配置的过期分钟数
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    # 注入 exp 字段（JWT 标准过期声明）
    to_encode.update({"exp": expire})
    # 使用 HS256 算法签名
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict | None:
    """
    解码并验证 JWT 访问令牌。

    使用 HS256 算法和 secret_key 验证签名，检查是否过期。

    参数:
        token: JWT 令牌字符串

    返回:
        dict | None: 解码后的数据字典（验证通过），或 None（验证失败/过期）
    """
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        return None
