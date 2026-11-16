"""
fufu新闻 - 经验记忆数据模型
============================
定义 AgentExperience（经验记忆）ORM 模型。

这是「经验记忆存储层」的持久化载体，参照 autocontext 的
knowledge/（playbook + hints）与 agent-beacon 的跨会话记忆层思想：
把 AI 生成与推荐过程中沉淀的可复用经验结构化保存，供后续调用检索复用，
避免每次从零开始、重复踩坑。

字段说明：
- id: 主键，自增
- category: 经验类别（如 "prompt_tweak" / "parse_failure" / "tag_fix" / "strategy_tune"）
- key: 经验的唯一键（如标签名、错误模式签名），用于去重与检索
- value: 经验内容（JSON 结构化数据，如修正后的 prompt、正确映射等）
- score: 经验置信度/命中次数（门控提升：越高越可信）
- last_used_at: 最近一次命中时间（用于热度与淘汰）
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentExperience(Base):
    """
    经验记忆 ORM 模型——对应数据库中的 agent_experience 表。

    每个 (category, key) 唯一，value 存结构化经验，score 表示可信度。
    score 会随「命中成功」递增、随「时间」缓慢衰减（门控提升 + 自然淘汰）。
    """
    __tablename__ = "agent_experience"
    __table_args__ = (
        Index("idx_agent_exp_category_key", "category", "key", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float] = mapped_column(Float, default=1.0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
