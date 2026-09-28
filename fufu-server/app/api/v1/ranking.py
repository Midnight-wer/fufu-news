"""
fufu新闻 - 排行榜接口
=========================
提供文章热度排行榜相关 REST API 端点：

- GET  /ranking/daily      → 今日热门（24h 浏览窗口）
- GET  /ranking/weekly     → 本周热门（7d 浏览窗口）
- GET  /ranking/monthly    → 本月热门（30d 浏览窗口）
- POST /ranking/hit/{id}   → 记录一次文章浏览/点击

热度计算公式（来自优化方案）：
    click_weight   = 0.6
    comment_weight = 0.3
    collect_weight = 0.1
    time_decay     = 1 / (1 + hours_since_publish / 24)
    hot_score      = (view * 0.6 + comment * 0.3 + collect * 0.1) * time_decay
"""
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from app.core.database import get_db
from app.models.article import Article
from app.models.source import Source
from app.models.ranking import ArticleStats, ViewLog
from app.models.user import User
from app.schemas.ranking import RankingItem, RankingResponse, HitResponse
from app.schemas.response import success, error
from app.api.deps import get_current_user

logger = logging.getLogger("fufu.ranking")

router = APIRouter(tags=["排行榜"])


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

    参数:
        hot_score: 热度分
        published_at: 文章发布时间
        fetched_at: 抓取时间

    返回:
        str | None: 热度标签
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
    - "same": 其他情况（后续可扩展为对比上期排名）

    参数:
        published_at: 文章发布时间
        fetched_at: 抓取时间

    返回:
        str: 趋势标识
    """
    ref_time = published_at if published_at is not None else fetched_at
    if ref_time:
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - ref_time).total_seconds() < 24 * 3600:
            return "new"
    return "same"


# ========== 辅助：获取时间窗口 ==========

def _time_window(period: str) -> timedelta:
    """将周期字符串转为时间窗口长度。"""
    windows = {
        "daily": timedelta(hours=24),
        "weekly": timedelta(days=7),
        "monthly": timedelta(days=30),
    }
    return windows.get(period, timedelta(hours=24))


# ========== 排行榜查询核心逻辑 ==========

async def _get_ranking(
    db: AsyncSession,
    period: str,
    limit: int,
) -> RankingResponse:
    """
    核心排行榜查询：按时间窗口统计热度并排序。

    逻辑:
    1. 根据 period 确定时间窗口（daily=24h / weekly=7d / monthly=30d）
    2. 查询时间窗口内的浏览日志，按文章聚合浏览数
    3. 对每篇文章计算热度分
    4. 按热度分降序排列，取前 limit 条
    5. 回写热度分到 article_stats 表

    参数:
        db: 数据库会话
        period: 时间周期（"daily"/"weekly"/"monthly"）
        limit: 返回条数上限

    返回:
        RankingResponse: 排行榜数据
    """
    window = _time_window(period)
    cutoff = datetime.now(timezone.utc) - window

    # 统计时间窗口内每篇文章的浏览数（按 IP 去重，1h 内同一 IP 同一文章只计一次）
    # 聚合：按 article_id 统计不重复的 (ip_address, viewed_at hour) 数
    # 简化做法：统计时间窗口内 view_log 的行数（已在前端/API 层做 1h 去重）
    view_counts_query = (
        select(
            ViewLog.article_id,
            func.count(ViewLog.id).label("window_views"),
        )
        .where(ViewLog.viewed_at >= cutoff)
        .group_by(ViewLog.article_id)
        .subquery()
    )

    # 主查询：关联 article_stats、article、source
    # 使用 LEFT JOIN 确保即使没有 stats 记录也能展示（只有浏览记录）
    main_query = (
        select(
            Article.id,
            Article.title,
            Article.image_url,
            Article.published_at,
            Article.fetched_at,
            ArticleStats.view_count,
            ArticleStats.comment_count,
            ArticleStats.collect_count,
            Source.name.label("source_name"),
            func.coalesce(view_counts_query.c.window_views, 0).label("window_views"),
        )
        .select_from(Article)
        .join(Source, Article.source_id == Source.id)
        .outerjoin(ArticleStats, Article.id == ArticleStats.article_id)
        .join(view_counts_query, Article.id == view_counts_query.c.article_id)
        .order_by(func.coalesce(view_counts_query.c.window_views, 0).desc())
        .limit(limit)
    )

    result = await db.execute(main_query)
    rows = result.all()

    # 计算热度分并构建排行条目
    items = []
    now = datetime.now(timezone.utc)
    for rank_idx, row in enumerate(rows, start=1):
        article_id = row[0]
        title = row[1] or ""
        image_url = row[2]
        published_at = row[3]
        fetched_at = row[4] or now
        view_count = row[5] or 0
        comment_count = row[6] or 0
        collect_count = row[7] or 0
        source_name = row[8] or ""
        window_views = row[9] or 0

        hot_score = calculate_hot_score(
            view_count=view_count,
            comment_count=comment_count,
            collect_count=collect_count,
            published_at=published_at,
            fetched_at=fetched_at,
        )

        items.append(RankingItem(
            rank=rank_idx,
            article_id=article_id,
            title=title,
            source_name=source_name,
            image_url=image_url,
            hot_score=hot_score,
            view_count=view_count,
            comment_count=comment_count,
            collect_count=collect_count,
            trend=determine_trend(published_at, fetched_at),
            hot_label=determine_hot_label(hot_score, published_at, fetched_at),
        ))

    # 回写热度分到 article_stats
    for item in items:
        stats_result = await db.execute(
            select(ArticleStats).where(ArticleStats.article_id == item.article_id)
        )
        stats = stats_result.scalar_one_or_none()
        if stats:
            stats.hot_score = item.hot_score
            stats.calculated_at = now

    await db.flush()

    return RankingResponse(
        items=items,
        updated_at=now,
    )


# ========== API 端点 ==========

@router.get("/daily")
async def ranking_daily(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    每日热门排行——GET /api/v1/ranking/daily

    统计过去 24 小时内浏览最多的文章，按热度分降序排列。

    参数:
        limit: 返回条数上限（1-50，默认 10）

    返回:
        dict: {"code": 200, "data": RankingResponse, "message": "ok"}
    """
    try:
        ranking = await _get_ranking(db, "daily", limit)
        return success(data=ranking.model_dump())
    except Exception as e:
        logger.error(f"获取每日排行失败: {e}", exc_info=True)
        return error(code=500, message="获取每日排行失败，请稍后再试～")


@router.get("/weekly")
async def ranking_weekly(
    limit: int = Query(default=15, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    每周热门排行——GET /api/v1/ranking/weekly

    统计过去 7 天内浏览最多的文章，按热度分降序排列。

    参数:
        limit: 返回条数上限（1-50，默认 15）

    返回:
        dict: {"code": 200, "data": RankingResponse, "message": "ok"}
    """
    try:
        ranking = await _get_ranking(db, "weekly", limit)
        return success(data=ranking.model_dump())
    except Exception as e:
        logger.error(f"获取每周排行失败: {e}", exc_info=True)
        return error(code=500, message="获取每周排行失败，请稍后再试～")


@router.get("/monthly")
async def ranking_monthly(
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    每月热门排行——GET /api/v1/ranking/monthly

    统计过去 30 天内浏览最多的文章，按热度分降序排列。

    参数:
        limit: 返回条数上限（1-50，默认 20）

    返回:
        dict: {"code": 200, "data": RankingResponse, "message": "ok"}
    """
    try:
        ranking = await _get_ranking(db, "monthly", limit)
        return success(data=ranking.model_dump())
    except Exception as e:
        logger.error(f"获取每月排行失败: {e}", exc_info=True)
        return error(code=500, message="获取每月排行失败，请稍后再试～")


@router.post("/hit/{article_id}")
async def record_hit(
    article_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    记录文章浏览——POST /api/v1/ranking/hit/{article_id}

    由前端在用户点击/阅读文章时调用，记录一次浏览。
    去重规则：同一 IP 对同一文章 1 小时内只计一次。

    参数:
        article_id: 文章 ID

    返回:
        dict: {"code": 200, "data": {"recorded": true/false, "message": "..."}}
    """
    try:
        # 获取客户端 IP
        client_ip = request.client.host if request.client else "127.0.0.1"
        # 处理 IPv6 映射的 IPv4 地址（如 ::ffff:127.0.0.1）
        if client_ip.startswith("::ffff:"):
            client_ip = client_ip[7:]

        # 检查文章是否存在
        article_result = await db.execute(select(Article).where(Article.id == article_id))
        article = article_result.scalar_one_or_none()
        if not article:
            return error(code=404, message="找不到这篇文章呢～")

        # 去重检查：同一 IP 同一文章 1 小时内只计一次
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        dup_result = await db.execute(
            select(ViewLog.id).where(
                and_(
                    ViewLog.article_id == article_id,
                    ViewLog.ip_address == client_ip,
                    ViewLog.viewed_at >= one_hour_ago,
                )
            ).limit(1)
        )
        if dup_result.scalar_one_or_none() is not None:
            return success(
                data={"recorded": False, "message": "1小时内已记录过，跳过去重～"},
            )

        # 创建浏览日志
        view_log = ViewLog(
            article_id=article_id,
            ip_address=client_ip,
        )
        db.add(view_log)

        # 更新或创建文章统计
        stats_result = await db.execute(
            select(ArticleStats).where(ArticleStats.article_id == article_id)
        )
        stats = stats_result.scalar_one_or_none()
        if stats:
            stats.view_count += 1
        else:
            stats = ArticleStats(
                article_id=article_id,
                view_count=1,
                comment_count=0,
                collect_count=1 if article.is_favorite else 0,
            )
            db.add(stats)

        await db.flush()
        logger.info(f"记录浏览: article_id={article_id}, ip={client_ip}, view_count={stats.view_count}")

        return success(
            data={"recorded": True, "message": "浏览已记录～"},
        )

    except Exception as e:
        logger.error(f"记录浏览失败: {e}", exc_info=True)
        return error(code=500, message="记录浏览失败，请稍后再试～")
