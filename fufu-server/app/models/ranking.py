"""
fufu新闻 - 排名/热门榜单数据模型
=====================================
定义 ArticleStats（文章统计）和 ViewLog（浏览日志）ORM 模型。

ArticleStats: 每篇文章一条记录，存储浏览数、评论数、收藏数和计算出的热度分。
ViewLog: 记录每次浏览的 IP 和文章 ID，用于去重和排重统计。
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ArticleStats(Base):
    """
    文章统计 ORM 模型——对应数据库中的 article_stats 表。

    每篇文章只有一条统计记录（article_id 唯一约束），
    热度分在每次请求排行榜时动态计算并回写。

    字段说明：
    - id: 主键，自增
    - article_id: 外键关联 article 表（级联删除，唯一约束）
    - view_count: 累计浏览/点击数
    - comment_count: 累计评论数
    - collect_count: 累计收藏数
    - hot_score: 计算出的热度分（浮点数）
    - calculated_at: 热度分最近计算时间
    """
    __tablename__ = "article_stats"
    __table_args__ = (
        Index("idx_article_stats_hot_score", "hot_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("article.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    collect_count: Mapped[int] = mapped_column(Integer, default=0)
    hot_score: Mapped[float] = mapped_column(Float, default=0.0)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ViewLog(Base):
    """
    浏览日志 ORM 模型——对应数据库中的 view_log 表。

    记录每次浏览的 IP 地址、文章 ID 和浏览时间。
    用于去重（同一 IP 对同一文章 1 小时内只计一次）和排行榜时间窗口筛选。

    字段说明：
    - id: 主键，自增
    - article_id: 外键关联 article 表（级联删除）
    - ip_address: 浏览者 IP 地址
    - viewed_at: 浏览时间（默认当前 UTC 时间）
    """
    __tablename__ = "view_log"
    __table_args__ = (
        Index("idx_view_log_article_ip_time", "article_id", "ip_address", "viewed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("article.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ip_address: Mapped[str] = mapped_column(String(45), default="", index=True)
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
