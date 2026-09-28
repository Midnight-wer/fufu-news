"""
fufu新闻 - 成就系统模型
===========================
定义成就系统的两个核心 ORM 模型：
1. AchievementDef: 成就定义（种子数据，描述每种成就的元信息）
2. UserAchievement: 用户成就进度（记录每个用户在各个成就上的进度和状态）

成就种子数据包含 11 个成就，涵盖阅读、收藏、探索、搜索等类别。
"""
from sqlalchemy import String, Integer, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.core.database import Base


class AchievementDef(Base):
    """
    成就定义表——存储成就的元数据（常量数据，由种子数据初始化）。

    字段说明：
    - id: 主键，自增
    - key: 成就键名（唯一标识，如 "read_10", "first_login"）
    - title: 成就标题（中文显示名）
    - description: 成就描述
    - icon: 成就图标（emoji 字符）
    - category: 成就类别（如 "reading", "collecting", "explore"）
    - tier: 成就等级（1-3，等级越高越稀有）
    """
    __tablename__ = "achievement_def"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=False)
    icon: Mapped[str] = mapped_column(String(8), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=1)


class UserAchievement(Base):
    """
    用户成就进度表——记录每个用户在各项成就上的进度。

    字段说明：
    - id: 主键，自增
    - user_id: 外键，关联 user 表（级联删除）
    - achievement_key: 成就键名（对应 AchievementDef.key）
    - progress: 当前进度数值（如已读文章数）
    - threshold: 解锁阈值（达到此值则解锁成就）
    - unlocked: 是否已解锁
    - unlocked_at: 解锁时间
    - notified: 是否已通知用户（避免重复弹窗）
    """
    __tablename__ = "user_achievement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    achievement_key: Mapped[str] = mapped_column(String(64), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    threshold: Mapped[int] = mapped_column(Integer, default=1)
    unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)


# ========== 成就种子数据 ==========
# 每个成就的元信息定义，首次启动时自动播种到 achievement_def 表中
ACHIEVEMENT_SEEDS = [
    # 探索类成就
    {"key": "first_login", "title": "初来乍到", "description": "第一次登录fufu新闻", "icon": "🌱", "category": "explore", "tier": 1},
    # 阅读类成就（三级递进）
    {"key": "read_10", "title": "阅读新秀", "description": "阅读了10篇文章", "icon": "📖", "category": "reading", "tier": 1},
    {"key": "read_50", "title": "阅读达人", "description": "阅读了50篇文章", "icon": "📚", "category": "reading", "tier": 2},
    {"key": "read_100", "title": "博览群书", "description": "阅读了100篇文章", "icon": "🏛️", "category": "reading", "tier": 3},
    # 收藏类成就（两级递进）
    {"key": "fav_10", "title": "心动收藏", "description": "收藏了10篇文章", "icon": "💝", "category": "collecting", "tier": 1},
    {"key": "fav_50", "title": "收藏家", "description": "收藏了50篇文章", "icon": "🏆", "category": "collecting", "tier": 2},
    # 探索类：搜索
    {"key": "first_search", "title": "好奇宝宝", "description": "第一次使用全网搜索", "icon": "🔍", "category": "explore", "tier": 1},
    # 收藏类：订阅源数量（两级递进）
    {"key": "source_5", "title": "源头寻觅", "description": "订阅了5个信息源", "icon": "🌐", "category": "collecting", "tier": 1},
    {"key": "source_10", "title": "源之猎人", "description": "订阅了10个信息源", "icon": "🎯", "category": "collecting", "tier": 2},
    # 探索类：AI 功能使用
    {"key": "first_ai", "title": "AI探索者", "description": "第一次使用AI功能", "icon": "🤖", "category": "explore", "tier": 1},
    # 阅读类：稍后阅读
    {"key": "later_10", "title": "马住再看", "description": "稍后阅读了10篇文章", "icon": "📌", "category": "reading", "tier": 1},
]
