"""
fufu新闻 - 用户数据模型
===========================
定义 User（用户）ORM 模型。
每个用户拥有唯一的用户名、bcrypt 哈希密码和 JSON 格式的个性化设置。
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """
    用户 ORM 模型——对应数据库中的 user 表。

    字段说明：
    - id: 主键，自增
    - username: 用户名（唯一，不可为空，最大 50 字符）
    - password_hash: bcrypt 哈希后的密码（不可为空，最大 128 字符）
    - settings: 用户个性化设置（JSON 格式，默认空字典）
    - created_at: 用户创建时间（默认当前 UTC 时间）
    """
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
