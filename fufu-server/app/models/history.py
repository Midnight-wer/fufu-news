"""
fufu新闻 - 阅读历史数据模型
===============================
定义 ReadHistory（阅读历史）ORM 模型。
每个用户在阅读文章时自动记录阅读历史，包括阅读时间和阅读时长。
"""
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReadHistory(Base):
    """
    阅读历史 ORM 模型——对应数据库中的 read_history 表。

    字段说明：
    - id: 主键，自增
    - user_id: 外键，关联 user 表（级联删除）
    - article_id: 外键，关联 article 表（级联删除）
    - read_at: 阅读时间（默认当前 UTC 时间）
    - read_duration: 阅读时长（秒，默认 0）
    - (user_id, article_id): 唯一约束，同一用户同一文章只保留最新阅读记录
    """
    __tablename__ = "read_history"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_read_history_user_article"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("article.id", ondelete="CASCADE"), index=True, nullable=False
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    read_duration: Mapped[int] = mapped_column(Integer, default=0)
