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

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.article import Article
from app.models.ranking import ArticleStats, ViewLog
from app.models.source import Source
from app.models.user import User
from app.schemas.ranking import RankingItem, RankingResponse
from app.schemas.response import error, success
from app.services.stats import (
    _determine_trend_with_history,
    calculate_hot_score,
    determine_hot_label,
)

logger = logging.getLogger("fufu.ranking")

router = APIRouter(tags=["排行榜"])


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
    now = datetime.now(timezone.utc)

    # 统计时间窗口内每篇文章的浏览数
    view_counts_query = (
        select(
            ViewLog.article_id,
            func.count(ViewLog.id).label("window_views"),
        )
        .where(ViewLog.viewed_at >= cutoff)
        .group_by(ViewLog.article_id)
        .subquery()
    )

    # ---- 修复说明 ----
    # 原实现有两个致命问题，导致榜单数据链断裂：
    # 1. `join(view_counts_query, ...)` 是 INNER JOIN —— 没有任何 ViewLog 记录时
    #    结果集为空，排行榜永远显示"还没有热榜数据～"（新装用户必然如此）。
    # 2. 排序键是 window_views 而不是算出来的 hot_score，
    #    comment_count(30%) / collect_count(10%) / 时间衰减全部不参与排序，
    #    热度公式等于白算；且三档共用同一批数据，日/周/月没有区分度。
    #
    # 现在改为：LEFT JOIN + 按 hot_score 排序 + 用窗口内的真实浏览数计分，
    # 并在候选不足时用最新文章兜底，保证榜单不空。

    def _build_query(exclude_ids: list[int] | None = None, max_rows: int | None = None):
        q = (
            select(
                Article.id,
                Article.title,
                Article.image_url,
                Article.published_at,
                Article.fetched_at,
                ArticleStats.view_count,
                ArticleStats.comment_count,
                ArticleStats.collect_count,
                ArticleStats.hot_score.label("prev_hot_score"),
                Source.name.label("source_name"),
                func.coalesce(view_counts_query.c.window_views, 0).label("window_views"),
            )
            .select_from(Article)
            .join(Source, Article.source_id == Source.id)
            .outerjoin(ArticleStats, Article.id == ArticleStats.article_id)
            .outerjoin(view_counts_query, Article.id == view_counts_query.c.article_id)
        )
        if exclude_ids:
            q = q.where(Article.id.notin_(exclude_ids))
        q = q.order_by(Article.fetched_at.desc())
        if max_rows is not None:
            q = q.limit(max_rows)
        return q

    # 候选池：时间窗口内抓取的文章，或窗口内有浏览记录的文章
    candidate_query = (
        _build_query()
        .where(
            or_(
                Article.fetched_at >= cutoff,
                func.coalesce(view_counts_query.c.window_views, 0) > 0,
            )
        )
        .limit(limit * 3)  # 多取一些，排序后再截断
    )
    result = await db.execute(candidate_query)
    rows = list(result.all())

    # 候选不足时用最新文章补齐，保证榜单永远不空
    if len(rows) < limit:
        exclude = [r[0] for r in rows]
        filler = await db.execute(
            _build_query(exclude_ids=exclude, max_rows=limit * 3 - len(rows))
        )
        rows.extend(filler.all())

    # 计算热度分并构建排行条目
    scored: list[tuple[float, datetime, RankingItem]] = []
    for row in rows:
        article_id = row[0]
        title = row[1] or ""
        image_url = row[2]
        published_at = row[3]
        fetched_at = row[4] or now
        comment_count = row[6] or 0
        collect_count = row[7] or 0
        prev_hot_score = row[8]
        source_name = row[9] or ""
        window_views = row[10] or 0

        # 计分优先用「窗口内的真实浏览数」；浏览量用窗口值与累计值的较大者，
        # 避免历史累计把旧文章永久顶在榜首。
        view_count = max(window_views, row[5] or 0 if window_views == 0 else window_views)

        hot_score = calculate_hot_score(
            view_count=view_count,
            comment_count=comment_count,
            collect_count=collect_count,
            published_at=published_at,
            fetched_at=fetched_at,
        )

        item = RankingItem(
            rank=0,  # 排序后再赋值
            article_id=article_id,
            title=title,
            source_name=source_name,
            image_url=image_url,
            hot_score=hot_score,
            view_count=view_count,
            comment_count=comment_count,
            collect_count=collect_count,
            trend=_determine_trend_with_history(
                published_at, fetched_at, hot_score, prev_hot_score
            ),
            hot_label=determine_hot_label(hot_score, published_at, fetched_at),
        )
        scored.append((hot_score, fetched_at, item))

    # 按热度分降序；同分时新的在前
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)

    items: list[RankingItem] = []
    for rank_idx, (_score, _fetched, item) in enumerate(scored[:limit], start=1):
        item.rank = rank_idx
        items.append(item)

    # 回写热度分（批量查询，避免逐条 select 的 N+1）
    if items:
        article_ids = [i.article_id for i in items]
        stats_rows = (
            await db.execute(
                select(ArticleStats).where(ArticleStats.article_id.in_(article_ids))
            )
        ).scalars().all()
        by_article = {s.article_id: s for s in stats_rows}
        for item in items:
            stats = by_article.get(item.article_id)
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
