"""
fufu新闻 - 用户兴趣画像数据模型
================================
定义 UserProfile（用户兴趣画像）ORM 模型。

这是「推荐引擎自学习」的持久化载体：从用户的历史行为
（阅读时长 / 收藏 / 点击）中学习出每个标签的兴趣权重，
供推荐引擎动态调整策略，取代写死的全局常量。

设计参照业界 self-improving-agent 三支柱：
- 记忆层：画像持久化在 SQLite，跨会话保留
- 反馈闭环：read_duration / 收藏等真实信号回流更新权重
- 门控提升：权重带时间衰减，冷启动回退到默认值（fail-closed）
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserProfile(Base):
    """
    用户兴趣画像 ORM 模型——对应数据库中的 user_profile 表。

    每个 (user_id, tag) 一条记录，存储该用户对某标签的兴趣强度。
    兴趣强度由阅读时长、收藏、点击等隐式反馈累计而成，随时间衰减。

    字段说明：
    - id: 主键，自增
    - user_id: 外键，关联 user 表（级联删除）
    - tag: 兴趣标签（如 "科技" / "动漫"）
    - score: 兴趣强度（越大越感兴趣，随时间衰减）
    - last_seen_at: 最近一次触发该标签的时间（用于时间衰减）
    """
    __tablename__ = "user_profile"
    __table_args__ = (
        Index("idx_user_profile_user_tag", "user_id", "tag", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tag: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
