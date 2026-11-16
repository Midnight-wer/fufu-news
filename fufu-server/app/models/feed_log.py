"""
fufu新闻 - 抓取日志模型
===========================
定义 FeedLog（抓取日志）ORM 模型。
每次 RSS 抓取操作都会生成一条日志记录，用于追踪抓取的成功/失败状态、
新增文章数量以及错误信息。
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FeedLog(Base):
    """
    抓取日志 ORM 模型——对应数据库中的 feed_log 表。

    字段说明：
    - id: 主键，自增
    - source_id: 外键，关联 source 表的订阅源（级联删除）
    - timestamp: 抓取操作的时间戳（默认当前 UTC 时间）
    - status: 抓取结果（"success" 成功 / "error" 失败）
    - new_articles_count: 本次抓取新增的文章数量
    - error_msg: 抓取失败时的错误信息（成功时为 None）
    """
    __tablename__ = "feed_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(String(20), default="success")
    new_articles_count: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
