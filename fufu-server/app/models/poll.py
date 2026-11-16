"""
fufu新闻 - 文章立场投票数据模型
==================================
定义 ArticlePoll（文章立场投票）ORM 模型。

对应数据库 article_poll 表（迁移 v9 创建）。

背景：文章页的「你怎么看？」支持 / 反对 / 中立 投票原先纯靠前端 localStorage
实现，既不能跨设备同步，统计时也没按文章过滤。现在改为真实落库。

约束：UNIQUE(article_id, user_id) —— 每人对每篇文章只有一票，可改票。
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# 合法的投票选项
POLL_OPTIONS = ("support", "oppose", "neutral")


class ArticlePoll(Base):
    """
    文章立场投票 ORM 模型——对应数据库中的 article_poll 表。

    字段说明：
    - id: 主键，自增
    - article_id: 外键关联 article 表（级联删除）
    - user_id: 外键关联 user 表（级联删除）
    - option: 投票选项 support / oppose / neutral
    - created_at: 首次投票时间
    - updated_at: 最近改票时间
    """
    __tablename__ = "article_poll"
    __table_args__ = (
        UniqueConstraint("article_id", "user_id", name="uq_poll_article_user"),
        Index("idx_poll_article", "article_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("article.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    option: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
