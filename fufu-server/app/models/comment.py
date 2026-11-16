"""
fufu新闻 - 评论数据模型
==========================
定义 ArticleComment（文章评论）和 CommentLike（评论点赞）ORM 模型。

支持两级嵌套评论：
- parent_id 为 NULL 的评论为顶级评论
- parent_id 指向另一条评论的为回复
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ArticleComment(Base):
    """
    文章评论 ORM 模型——对应数据库中的 article_comment 表。

    字段说明：
    - id: 主键，自增
    - article_id: 外键，关联 article 表（级联删除）
    - user_id: 外键，关联 user 表（级联删除）
    - parent_id: 父评论 ID（NULL 表示顶级评论，级联删除）
    - content: 评论内容（TEXT，不可为空）
    - created_at: 创建时间（默认当前 UTC 时间）
    - updated_at: 更新时间
    - likes_count: 点赞数（冗余字段，由点赞操作维护）
    """
    __tablename__ = "article_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("article.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("article_comment.id", ondelete="CASCADE"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    likes_count: Mapped[int] = mapped_column(Integer, default=0)


class CommentLike(Base):
    """
    评论点赞记录 ORM 模型——对应数据库中的 comment_like 表。

    用于防止同一用户对同一条评论重复点赞。
    每个用户对每条评论最多只能有一条点赞记录。

    字段说明：
    - id: 主键，自增
    - comment_id: 外键，关联 article_comment 表（级联删除）
    - user_id: 外键，关联 user 表（级联删除）
    - created_at: 点赞时间（默认当前 UTC 时间）
    """
    __tablename__ = "comment_like"
    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_comment_like"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("article_comment.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
