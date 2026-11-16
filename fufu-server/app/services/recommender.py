"""
fufu新闻 - 个性化推荐引擎
===========================
多策略混合推荐系统，为每位用户生成个性化推荐文章。

策略组合（按权重）：
1. 内容推荐 (35%): 基于用户阅读历史中提取的兴趣标签，匹配相似标签文章
2. 协同推荐 (20%): 找到与用户有相似标签偏好的文章群体中的热门内容
3. 趋势推荐 (25%): 高热度分文章（hot_score），排除用户已读
4. 来源偏好 (10%): 用户常读来源的新文章
5. 新鲜度 (10%): 时间衰减因子，新文章获得更高权重

综合评分 = content*0.35 + collab*0.20 + trend*0.25 + source*0.10 + freshness*0.10
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.favorite import FavoriteFolder, FavoriteFolderItem
from app.models.history import ReadHistory
from app.models.ranking import ArticleStats
from app.models.source import Source

logger = logging.getLogger("fufu.recommender")

# 推荐策略权重
WEIGHT_CONTENT = 0.35    # 内容推荐权重
WEIGHT_COLLAB = 0.20     # 协同推荐权重
WEIGHT_TREND = 0.25      # 趋势推荐权重
WEIGHT_SOURCE = 0.10     # 来源偏好权重
WEIGHT_FRESHNESS = 0.10  # 新鲜度权重

# 新鲜度衰减参数
FRESHNESS_HALF_LIFE = 48  # 48 小时半衰期


def _freshness_factor(published_at: datetime | None, fetched_at: datetime | None) -> float:
    """
    计算新鲜度因子：时间越近权重越高。
    衰减公式: 1 / (1 + hours / 48)
    """
    ref_time = published_at if published_at else fetched_at
    if ref_time is None:
        return 0.5
    if ref_time.tzinfo is None:
        ref_time = ref_time.replace(tzinfo=timezone.utc)
    hours = max(
        (datetime.now(timezone.utc) - ref_time).total_seconds() / 3600,
        0.1
    )
    return 1.0 / (1.0 + hours / FRESHNESS_HALF_LIFE)


async def _get_user_read_article_ids(db: AsyncSession, user_id: int) -> set[int]:
    """获取用户已读的所有文章 ID。"""
    result = await db.execute(
        select(ReadHistory.article_id).where(ReadHistory.user_id == user_id)
    )
    return {row[0] for row in result.all()}


async def _get_user_preferred_tags(db: AsyncSession, user_id: int, top_n: int = 20) -> list[str]:
    """
    获取用户的兴趣标签（按强度排序）。

    自学习版本：优先读取 UserProfile 画像中学习出的兴趣权重；
    画像为空时回退到「阅读历史 + 收藏」的启发式统计（原逻辑）。
    返回的标签按兴趣强度降序排列。

    参数:
        db: 数据库会话
        user_id: 用户 ID
        top_n: 最多返回的标签数
    """
    # 1. 优先用自学习画像（真实反馈回流后的兴趣强度）
    try:
        from app.services.learning import get_interest_weights

        weights = await get_interest_weights(db, user_id)
        if weights:
            return [tag for tag, _ in sorted(weights.items(), key=lambda x: x[1], reverse=True)][:top_n]
    except Exception as e:
        logger.debug(f"读取兴趣画像失败，回退启发式: {e}")

    # 2. 回退：从阅读历史 + 收藏中统计标签（原逻辑，fail-closed 兜底）
    tag_counter: dict[str, int] = {}
    tag_total_duration: dict[str, int] = {}

    # 1. 从阅读历史中提取标签（按阅读时长加权）
    history_query = (
        select(ReadHistory.article_id, ReadHistory.read_duration)
        .where(ReadHistory.user_id == user_id)
        .order_by(ReadHistory.read_at.desc())
        .limit(200)
    )
    result = await db.execute(history_query)
    history_rows = result.all()
    history_article_ids = [row[0] for row in history_rows]
    duration_map = {row[0]: row[1] or 0 for row in history_rows}

    if history_article_ids:
        article_result = await db.execute(
            select(Article.id, Article.tags).where(Article.id.in_(history_article_ids))
        )
        for art_id, tags in article_result.all():
            if not tags:
                continue
            dur = duration_map.get(art_id, 0)
            weight = max(1, int(dur / 30))  # 每 30 秒阅读时间加 1 权重
            for tag in tags:
                tag = tag.strip()
                if tag:
                    tag_counter[tag] = tag_counter.get(tag, 0) + weight
                    tag_total_duration[tag] = tag_total_duration.get(tag, 0) + dur

    # 2. 从收藏夹中提取标签
    fav_result = await db.execute(
        select(FavoriteFolderItem.article_id)
        .join(FavoriteFolder, FavoriteFolder.id == FavoriteFolderItem.folder_id)
        .where(FavoriteFolder.user_id == user_id)
        .limit(100)
    )
    fav_article_ids = [row[0] for row in fav_result.all()]

    if fav_article_ids:
        article_result = await db.execute(
            select(Article.id, Article.tags).where(Article.id.in_(fav_article_ids))
        )
        for _art_id, tags in article_result.all():
            if not tags:
                continue
            for tag in tags:
                tag = tag.strip()
                if tag:
                    tag_counter[tag] = tag_counter.get(tag, 0) + 2  # 收藏权重为 2

    # 按频率排序取 top_n
    sorted_tags = sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)
    return [tag for tag, _ in sorted_tags[:top_n]]


async def _get_user_top_sources(db: AsyncSession, user_id: int, top_n: int = 3) -> list[int]:
    """获取用户最常阅读的 top-N 个来源 ID。"""
    result = await db.execute(
        select(
            Article.source_id,
            func.count(ReadHistory.id).label("cnt")
        )
        .select_from(ReadHistory)
        .join(Article, ReadHistory.article_id == Article.id)
        .where(ReadHistory.user_id == user_id)
        .group_by(Article.source_id)
        .order_by(func.count(ReadHistory.id).desc())
        .limit(top_n)
    )
    return [row[0] for row in result.all() if row[0] is not None]


def _compute_content_score(preferred_tags: list[str], article_tags: list) -> float:
    """
    计算内容匹配分：文章标签与用户兴趣标签的重合度。
    使用 Jaccard 相似度 + 权重加成。
    """
    if not preferred_tags or not article_tags:
        return 0.0
    preferred_set = set(preferred_tags)
    article_set = set(article_tags)
    intersection = preferred_set & article_set
    union = preferred_set | article_set
    if not union:
        return 0.0
    jaccard = len(intersection) / len(union)
    # 如果匹配到用户 top 标签，额外加分
    top_bonus = 0.0
    for i, tag in enumerate(preferred_tags[:5]):
        if tag in article_set:
            top_bonus += (5 - i) * 0.02  # top-1 加 0.1，top-5 加 0.02
    return min(jaccard + top_bonus, 1.0)


def _compute_collab_score(preferred_tags: list[str], article_tags: list) -> float:
    """
    计算协同推荐分：文章标签与全局流行标签的重合度。
    简化为——如果文章标签在用户兴趣标签中，给予更高分。
    """
    if not preferred_tags or not article_tags:
        return 0.0
    preferred_set = set(preferred_tags)
    article_set = set(article_tags)
    match_count = len(preferred_set & article_set)
    if match_count == 0:
        return 0.0
    return min(match_count / max(len(article_set), 1), 1.0)


def _compute_source_score(user_top_sources: list[int], article_source_id: int) -> float:
    """计算来源偏好分：用户常读来源获得更高分。"""
    if not user_top_sources:
        return 0.0
    if article_source_id == user_top_sources[0]:
        return 1.0
    elif article_source_id in user_top_sources[1:]:
        return 0.6
    return 0.0


def _determine_reason(
    content_score: float,
    collab_score: float,
    trend_score: float,
    source_score: float,
    preferred_tags: list[str],
    article_tags: list,
) -> str:
    """
    根据各策略得分确定推荐理由标签。
    返回更适合展示的中文理由。
    """
    reasons = []

    if content_score > 0.3:
        matching = [t for t in article_tags if t in preferred_tags][:3]
        if matching:
            reasons.append(f"因为你喜欢「{matching[0]}」")

    if source_score >= 0.6:
        reasons.append("常读来源")

    if trend_score > content_score and trend_score > collab_score:
        reasons.append("热门趋势")

    if collab_score > 0.3 and not reasons:
        reasons.append("标签匹配")

    if not reasons:
        if preferred_tags and article_tags:
            reasons.append("内容推荐")
        else:
            reasons.append("为你推荐")

    return reasons[0] if reasons else "为你推荐"


async def get_personalized_recommendations(
    db: AsyncSession,
    user_id: int,
    limit: int = 10,
    exclude_ids: list[int] | None = None,
) -> list[dict]:
    """
    生成个性化推荐，使用多策略混合评分算法。

    算法流程：
    1. 获取用户已读文章 ID（用于排除）
    2. 提取用户兴趣标签（从阅读历史 + 收藏）
    3. 提取用户常读来源 top-3
    4. 获取候选文章池（未读、有一定热度、排除 exclude_ids）
    5. 对每篇候选文章计算五项评分，加权求和
    6. 按综合分降序排序，返回前 limit 条

    参数:
        db: 数据库会话
        user_id: 用户 ID
        limit: 返回条数上限
        exclude_ids: 额外需要排除的文章 ID 列表（如当前页已展示的）

    返回:
        list[dict]: 推荐条目列表，每个包含 article_id, title, reason, score 等
    """
    try:
        exclude_set = set(exclude_ids or [])

        # 1. 获取用户已读文章 ID
        read_ids = await _get_user_read_article_ids(db, user_id)
        exclude_set.update(read_ids)

        # 2. 提取用户兴趣标签
        preferred_tags = await _get_user_preferred_tags(db, user_id)

        # 3. 提取用户常读来源
        top_sources = await _get_user_top_sources(db, user_id)

        # 4. 获取候选文章池
        # 策略：取近期未读文章（有热度分或近期发布），上限 200 篇构成候选池
        candidate_query = (
            select(
                Article.id.label("article_id"),
                Article.title,
                Article.tags,
                Article.source_id,
                Article.image_url,
                Article.published_at,
                Article.fetched_at,
                Source.name.label("source_name"),
                func.coalesce(ArticleStats.hot_score, 0.0).label("hot_score"),
            )
            .select_from(Article)
            .join(Source, Article.source_id == Source.id)
            .outerjoin(ArticleStats, Article.id == ArticleStats.article_id)
            .where(Article.id.notin_(exclude_set) if exclude_set else True)
            .order_by(Article.published_at.desc().nulls_last())
            .limit(200)
        )
        result = await db.execute(candidate_query)
        candidate_rows = result.all()

        if not candidate_rows:
            # 回退：如果候选池为空，取最新文章（排除已读）
            fallback_query = (
                select(
                    Article.id.label("article_id"),
                    Article.title,
                    Article.tags,
                    Article.source_id,
                    Article.image_url,
                    Article.published_at,
                    Article.fetched_at,
                    Source.name.label("source_name"),
                    func.coalesce(ArticleStats.hot_score, 0.0).label("hot_score"),
                )
                .select_from(Article)
                .join(Source, Article.source_id == Source.id)
                .outerjoin(ArticleStats, Article.id == ArticleStats.article_id)
                .order_by(Article.published_at.desc().nulls_last())
                .limit(50)
            )
            result = await db.execute(fallback_query)
            candidate_rows = result.all()

        if not candidate_rows:
            logger.info(f"推荐引擎：用户 {user_id} 无候选文章")
            return []

        # 5. 计算评分
        scored_items = []
        for row in candidate_rows:
            article_id = row.article_id
            title = row.title or ""
            tags = row.tags or []
            source_id = row.source_id
            image_url = row.image_url
            published_at = row.published_at
            fetched_at = row.fetched_at
            source_name = row.source_name or ""
            hot_score = row.hot_score or 0.0

            # 计算各策略分
            content_score = _compute_content_score(preferred_tags, tags)
            collab_score = _compute_collab_score(preferred_tags, tags)

            # 趋势分：归一化热度分到 [0, 1]
            trend_score = min(hot_score / 100.0, 1.0) if hot_score > 0 else 0.0

            # 来源偏好分
            source_score = _compute_source_score(top_sources, source_id)

            # 新鲜度
            freshness = _freshness_factor(published_at, fetched_at)

            # 综合评分
            final_score = (
                content_score * WEIGHT_CONTENT +
                collab_score * WEIGHT_COLLAB +
                trend_score * WEIGHT_TREND +
                source_score * WEIGHT_SOURCE +
                freshness * WEIGHT_FRESHNESS
            )

            reason = _determine_reason(
                content_score, collab_score, trend_score, source_score,
                preferred_tags, tags
            )

            scored_items.append({
                "article_id": article_id,
                "title": title,
                "source_name": source_name,
                "image_url": image_url,
                "published_at": published_at.isoformat() if published_at else None,
                "hot_score": round(hot_score, 1),
                "reason": reason,
                "score": round(final_score, 4),
                "tags": tags,
            })

        # 6. 按综合分降序
        scored_items.sort(key=lambda x: x["score"], reverse=True)

        top_items = scored_items[:limit]

        logger.info(
            f"推荐引擎：用户 {user_id} 获得 {len(top_items)} 条推荐，"
            f"偏好标签数={len(preferred_tags)}，常读来源数={len(top_sources)}，"
            f"Top reasons: {[item['reason'] for item in top_items[:5]]}"
        )

        return top_items

    except Exception as e:
        logger.error(f"推荐引擎失败: user_id={user_id}, error={e}", exc_info=True)
        return []


async def get_similar_articles(
    db: AsyncSession,
    article_id: int,
    limit: int = 5,
) -> list[dict]:
    """
    获取与给定文章相似的其他文章。

    算法：
    1. 获取目标文章的标签
    2. 找到有标签重合的文章
    3. 按标签重合度 + 热度分排序
    4. 排除目标文章自身

    参数:
        db: 数据库会话
        article_id: 目标文章 ID
        limit: 返回条数上限

    返回:
        list[dict]: 相似文章列表
    """
    try:
        # 获取目标文章的标签和来源
        article_result = await db.execute(
            select(Article.tags, Article.source_id)
            .where(Article.id == article_id)
        )
        row = article_result.one_or_none()
        if not row:
            return []

        target_tags = row[0] or []
        target_source_id = row[1]

        if not target_tags:
            # 标签为空时退化为同来源推荐
            similar_query = (
                select(
                    Article.id.label("article_id"),
                    Article.title,
                    Article.tags,
                    Article.image_url,
                    Article.published_at,
                    Source.name.label("source_name"),
                    func.coalesce(ArticleStats.hot_score, 0.0).label("hot_score"),
                )
                .select_from(Article)
                .join(Source, Article.source_id == Source.id)
                .outerjoin(ArticleStats, Article.id == ArticleStats.article_id)
                .where(
                    and_(
                        Article.id != article_id,
                        Article.source_id == target_source_id,
                    )
                )
                .order_by(Article.published_at.desc().nulls_last())
                .limit(limit)
            )
            result = await db.execute(similar_query)
            rows = result.all()

            items = []
            for row in rows:
                items.append({
                    "article_id": row.article_id,
                    "title": row.title or "",
                    "source_name": row.source_name or "",
                    "image_url": row.image_url,
                    "published_at": row.published_at.isoformat() if row.published_at else None,
                    "hot_score": round(row.hot_score or 0.0, 1),
                    "reason": "同源推荐",
                    "score": 0.5,
                    "tags": row.tags or [],
                })
            return items

        target_set = set(target_tags)

        # 查找有标签重合的文章
        candidates_query = (
            select(
                Article.id.label("article_id"),
                Article.title,
                Article.tags,
                Article.image_url,
                Article.published_at,
                Article.fetched_at,
                Source.name.label("source_name"),
                func.coalesce(ArticleStats.hot_score, 0.0).label("hot_score"),
            )
            .select_from(Article)
            .join(Source, Article.source_id == Source.id)
            .outerjoin(ArticleStats, Article.id == ArticleStats.article_id)
            .where(Article.id != article_id)
            .order_by(Article.published_at.desc().nulls_last())
            .limit(200)
        )
        result = await db.execute(candidates_query)
        candidate_rows = result.all()

        scored_items = []
        for row in candidate_rows:
            tags = row.tags or []
            article_set = set(tags)
            overlap = len(target_set & article_set)

            if overlap == 0 and row.article_id != article_id:
                # 无标签重合但同源的文章，给一个基础分
                if row.article_id != article_id:
                    base_score = 0.1
                else:
                    continue
            else:
                # Jaccard 相似度
                union = len(target_set | article_set) or 1
                base_score = overlap / union

            freshness = _freshness_factor(row.published_at, row.fetched_at)
            hot_score = row.hot_score or 0.0
            trend_score = min(hot_score / 100.0, 1.0)

            final_score = base_score * 0.5 + trend_score * 0.25 + freshness * 0.25

            matching = [t for t in tags if t in target_tags][:2]
            reason = f"相似「{matching[0]}」" if matching else "相关内容"

            scored_items.append({
                "article_id": row.article_id,
                "title": row.title or "",
                "source_name": row.source_name or "",
                "image_url": row.image_url,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "hot_score": round(hot_score, 1),
                "reason": reason,
                "score": round(final_score, 4),
                "tags": tags,
            })

        scored_items.sort(key=lambda x: x["score"], reverse=True)

        return scored_items[:limit]

    except Exception as e:
        logger.error(f"相似文章推荐失败: article_id={article_id}, error={e}", exc_info=True)
        return []


async def get_trending_articles(
    db: AsyncSession,
    limit: int = 10,
    exclude_ids: list[int] | None = None,
) -> list[dict]:
    """
    获取热门趋势文章（全局热榜）。

    算法：
    1. 从 article_stats 中取 hot_score 最高的文章
    2. 结合新鲜度因子
    3. 做一定的多样性控制（避免同一来源占比过高）

    参数:
        db: 数据库会话
        limit: 返回条数上限
        exclude_ids: 需要排除的文章 ID 列表

    返回:
        list[dict]: 趋势文章列表
    """
    try:
        exclude_set = set(exclude_ids or [])

        trend_query = (
            select(
                Article.id.label("article_id"),
                Article.title,
                Article.tags,
                Article.image_url,
                Article.published_at,
                Article.fetched_at,
                Source.name.label("source_name"),
                func.coalesce(ArticleStats.hot_score, 0.0).label("hot_score"),
            )
            .select_from(Article)
            .join(Source, Article.source_id == Source.id)
            .outerjoin(ArticleStats, Article.id == ArticleStats.article_id)
            .where(Article.id.notin_(exclude_set) if exclude_set else True)
            .order_by(func.coalesce(ArticleStats.hot_score, 0.0).desc())
            .limit(limit * 4)  # 多取一些做多样性过滤
        )
        result = await db.execute(trend_query)
        rows = result.all()

        if not rows:
            return []

        # 多样性控制：每源最多出现 2 篇
        source_counts: dict[int, int] = {}
        diverse_items = []
        for row in rows:
              # 这里实际用的是 article id，我们需要 source_name
            # 用 source_name 做去重判断
            source_name = row.source_name or ""
            s_key = source_name
            if source_counts.get(s_key, 0) >= 2:
                continue
            source_counts[s_key] = source_counts.get(s_key, 0) + 1

            published_at = row.published_at
            fetched_at = row.fetched_at
            hot_score = row.hot_score or 0.0
            freshness = _freshness_factor(published_at, fetched_at)

            # 综合趋势分 = hot_score 归一化 + 新鲜度
            trend_score = min(hot_score / 100.0, 1.0)
            final_score = trend_score * 0.7 + freshness * 0.3

            diverse_items.append({
                "article_id": row.article_id,
                "title": row.title or "",
                "source_name": source_name,
                "image_url": row.image_url,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "hot_score": round(hot_score, 1),
                "reason": "热门趋势",
                "score": round(final_score, 4),
                "tags": row.tags or [],
            })

            if len(diverse_items) >= limit:
                break

        return diverse_items

    except Exception as e:
        logger.error(f"趋势推荐失败: error={e}", exc_info=True)
        return []


async def get_category_recommendations(
    db: AsyncSession,
    category: str,
    limit: int = 10,
) -> list[dict]:
    """
    获取特定分类下的趋势文章。

    与 get_trending_articles 类似，但限定在 category 对应的标签/来源范围内。

    参数:
        db: 数据库会话
        category: 分类名（"科技"/"游戏"/"动漫"/"设计"/"科普"/"综合"）
        limit: 返回条数上限

    返回:
        list[dict]: 分类趋势文章列表
    """
    try:
        # 分类关键词映射（公开分类/前端计数见 app.core.categories.CATEGORY_NAMES；此处为推荐的细分关键词）
        category_keywords: dict[str, list[str]] = {
            "科技": ["科技", "技术", "编程", "AI", "人工智能", "互联网", "数码", "软件", "硬件"],
            "游戏": ["游戏", "电竞", "主机", "手游", "PC游戏", "独立游戏"],
            "动漫": ["动漫", "动画", "漫画", "二次元", "B站", "新番", "MAD", "AMV"],
            "设计": ["设计", "UI", "UX", "创意", "艺术", "平面设计"],
            "科普": ["科普", "科学", "自然", "天文", "健康", "生物", "物理"],
            "综合": ["新闻", "时事", "社会", "财经", "文化", "生活", "趣味"],
        }

        keywords = category_keywords.get(category, [])

        if not keywords:
            return await get_trending_articles(db, limit)

        # 构建标签匹配条件——使用 SQLite instr + json_extract 做 JSON 数组内模糊匹配
        conditions = []
        for kw in keywords:
            conditions.append(
                func.instr(func.lower(func.json_extract(Article.tags, '$')), kw.lower()) > 0
            )

        cat_query = (
            select(
                Article.id.label("article_id"),
                Article.title,
                Article.tags,
                Article.image_url,
                Article.published_at,
                Article.fetched_at,
                Source.name.label("source_name"),
                func.coalesce(ArticleStats.hot_score, 0.0).label("hot_score"),
            )
            .select_from(Article)
            .join(Source, Article.source_id == Source.id)
            .outerjoin(ArticleStats, Article.id == ArticleStats.article_id)
            .where(or_(*conditions))
            .order_by(func.coalesce(ArticleStats.hot_score, 0.0).desc())
            .limit(limit * 3)
        )

        result = await db.execute(cat_query)
        rows = result.all()

        items = []
        for row in rows:
            published_at = row.published_at
            fetched_at = row.fetched_at
            hot_score = row.hot_score or 0.0
            freshness = _freshness_factor(published_at, fetched_at)
            trend_score = min(hot_score / 100.0, 1.0)
            final_score = trend_score * 0.7 + freshness * 0.3

            items.append({
                "article_id": row.article_id,
                "title": row.title or "",
                "source_name": row.source_name or "",
                "image_url": row.image_url,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "hot_score": round(hot_score, 1),
                "reason": f"{category}热门",
                "score": round(final_score, 4),
                "tags": row.tags or [],
            })

        return items[:limit]

    except Exception as e:
        logger.error(f"分类推荐失败: category={category}, error={e}", exc_info=True)
        return []
