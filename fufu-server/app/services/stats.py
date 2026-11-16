"""
fufu新闻 - 文章统计与热度服务
===========================
集中放置与「文章统计量 / 热度分 / 趋势」相关的业务函数，
供排行榜路由、文章路由、评论路由共享，避免路由层互相 import。

本模块属于 service 层：
- 不引用任何 FastAPI 的 Request / Response / HTTPException；
- 只依赖 SQLAlchemy 会话与 ORM 模型，便于单测与复用。
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ranking import ArticleStats

logger = logging.getLogger("fufu.stats")


# ========== 热度计算公式 ==========


def calculate_hot_score(
    view_count: int,
    comment_count: int,
    collect_count: int,
    published_at: datetime | None,
    fetched_at: datetime,
) -> float:
    """
    根据优化方案的热度计算公式计算文章热度分。

    参数:
        view_count: 浏览/点击数
        comment_count: 评论数
        collect_count: 收藏数
        published_at: 文章原始发布时间（可为 None）
        fetched_at: 文章抓取入库时间（兜底用）

    返回:
        float: 热度分（越大越热）
    """
    click_weight = 0.6
    comment_weight = 0.3
    collect_weight = 0.1

    # 时间衰减：较新的内容获得较高权重
    # published_at 可能为 None，此时用 fetched_at 兜底
    ref_time = published_at if published_at is not None else fetched_at
    hours_since_publish = max(
        (datetime.now(timezone.utc) - ref_time.replace(tzinfo=timezone.utc)).total_seconds() / 3600,
        0.1  # 最小 0.1 小时，避免除以零
    )
    time_decay = 1.0 / (1.0 + hours_since_publish / 24.0)

    hot_score = (
        view_count * click_weight +
        comment_count * comment_weight +
        collect_count * collect_weight
    ) * time_decay

    return round(hot_score, 4)


def determine_hot_label(hot_score: float, published_at: datetime | None, fetched_at: datetime) -> str | None:
    """
    根据热度分和发布时间确定热度标签。

    规则:
    - "爆": hot_score >= 100
    - "热": hot_score >= 50
    - "新": 文章发布在 24 小时内（且不在上述区间）
    - None: 普通
    """
    if hot_score >= 100:
        return "爆"
    if hot_score >= 50:
        return "热"

    ref_time = published_at if published_at is not None else fetched_at
    if ref_time:
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - ref_time).total_seconds() < 24 * 3600:
            return "新"

    return None


def determine_trend(published_at: datetime | None, fetched_at: datetime) -> str:
    """
    确定趋势标识。

    规则:
    - "new": 文章发布在 24 小时内
    - "same": 其他情况
    """
    ref_time = published_at if published_at is not None else fetched_at
    if ref_time:
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - ref_time).total_seconds() < 24 * 3600:
            return "new"
    return "same"


def _determine_trend_with_history(
    published_at: datetime | None,
    fetched_at: datetime,
    hot_score: float,
    prev_hot_score: float | None,
) -> str:
    """
    带历史对比的趋势判定。

    修复：原先 determine_trend 只会返回 new / same，
    前端为 up / down 准备的箭头图标**永远不会出现**。
    这里用「上一次算出的热度分」做对比，让上升/下降真正可用。

    规则:
    - "new": 24 小时内发布，或尚无历史分
    - "up"  : 本次热度分高于上次
    - "down": 本次热度分低于上次
    - "same": 基本持平
    """
    if prev_hot_score is None:
        return determine_trend(published_at, fetched_at)

    # 变化幅度小于 1% 视为持平，避免抖动导致箭头乱跳
    if prev_hot_score > 0:
        delta = (hot_score - prev_hot_score) / prev_hot_score
        if delta > 0.01:
            return "up"
        if delta < -0.01:
            return "down"
        return "same"

    if hot_score > 0:
        return "up"
    return determine_trend(published_at, fetched_at)


# ========== 异步：同步统计量到 article_stats ==========


async def _ensure_stats(db: AsyncSession, article_id: int):
    """取（或按需创建）某篇文章的统计行。"""
    stats = (await db.execute(
        select(ArticleStats).where(ArticleStats.article_id == article_id)
    )).scalar_one_or_none()
    if stats is None:
        stats = ArticleStats(
            article_id=article_id,
            view_count=0,
            comment_count=0,
            collect_count=0,
        )
        db.add(stats)
        await db.flush()
    return stats


async def bump_comment_count(db: AsyncSession, article_id: int, delta: int) -> None:
    """
    增减文章的评论数。

    修复：热度公式里 comment 占 30% 权重，但 comment_count 此前**只有创建
    统计行时被写成 0**，之后再不更新 —— 这 30% 权重等于死代码，
    排行榜上的 💬 评论数永远显示 0。
    """
    try:
        stats = await _ensure_stats(db, article_id)
        stats.comment_count = max(0, (stats.comment_count or 0) + delta)
    except Exception as e:
        logger.warning(f"同步评论数失败 article_id={article_id}: {e}")


async def sync_collect_count(db: AsyncSession, article_id: int, is_favorite: bool) -> None:
    """
    同步文章的收藏数（按当前 is_favorite 状态设定为 0/1）。

    修复：collect_count 此前只在创建统计行的瞬间赋值一次
    （取决于用户首次点开时是否已收藏），之后再收藏/取消收藏都不更新，
    于是这个占 10% 权重的字段恒为 0 或 1，⭐ 收藏数永远失真。
    """
    try:
        stats = await _ensure_stats(db, article_id)
        stats.collect_count = 1 if is_favorite else 0
    except Exception as e:
        logger.warning(f"同步收藏数失败 article_id={article_id}: {e}")
