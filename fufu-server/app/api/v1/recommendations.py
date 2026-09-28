"""
fufu新闻 - 个性化推荐接口
=========================
提供个性化推荐相关的 REST API 端点：

- GET /personalized  → 基于用户阅读历史和兴趣的个性化推荐
- GET /similar/{article_id} → 与指定文章相似的文章
- GET /trending    → 全局热门趋势
- GET /category/{category} → 特定分类下的趋势文章
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.recommendation import (
    RecommendationItem,
    PersonalizedResponse,
    SimilarResponse,
    TrendingResponse,
)
from app.schemas.response import success, error
from app.api.deps import get_current_user
from app.services.recommender import (
    get_personalized_recommendations,
    get_similar_articles,
    get_trending_articles,
    get_category_recommendations,
)

logger = logging.getLogger("fufu.recommendations")

router = APIRouter(tags=["个性化推荐"])


@router.get("/personalized")
async def personalized_recommendations(
    limit: int = Query(default=10, ge=1, le=30),
    exclude_ids: str = Query(default="", description="逗号分隔的需要排除的文章ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    获取个性化推荐——GET /api/v1/recommendations/personalized

    基于用户的阅读历史、收藏、兴趣标签生成个性化推荐。
    多策略混合评分：内容匹配(35%) + 协同过滤(20%) + 趋势热度(25%) + 来源偏好(10%) + 新鲜度(10%)

    参数:
        limit: 返回条数上限（1-30，默认 10）
        exclude_ids: 需要排除的文章 ID，逗号分隔（如 "1,2,3"）

    返回:
        dict: {
            "code": 200,
            "data": {
                "items": [...],
                "reasons": {article_id: "推荐理由"}
            },
            "message": "ok"
        }
    """
    try:
        # 解析 exclude_ids
        parsed_exclude: list[int] = []
        if exclude_ids.strip():
            try:
                parsed_exclude = [int(x.strip()) for x in exclude_ids.split(",") if x.strip().isdigit()]
            except (ValueError, TypeError):
                pass

        items = await get_personalized_recommendations(
            db=db,
            user_id=user.id,
            limit=limit,
            exclude_ids=parsed_exclude,
        )

        # 构建 reasons 映射
        reasons = {item["article_id"]: item["reason"] for item in items}

        return success(data={
            "items": items,
            "reasons": reasons,
        })

    except Exception as e:
        logger.error(f"个性化推荐接口异常: user_id={user.id}, error={e}", exc_info=True)
        return error(code=500, message="推荐引擎暂时休息中，请稍后再试～")


@router.get("/similar/{article_id}")
async def similar_articles(
    article_id: int,
    limit: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    获取相似文章——GET /api/v1/recommendations/similar/{article_id}

    基于标签重合度查找与目标文章相似的其他文章。

    参数:
        article_id: 目标文章 ID
        limit: 返回条数上限（1-20，默认 5）

    返回:
        dict: {"code": 200, "data": {"items": [...], "reasons": {...}}, "message": "ok"}
    """
    try:
        items = await get_similar_articles(
            db=db,
            article_id=article_id,
            limit=limit,
        )
        reasons = {item["article_id"]: item["reason"] for item in items}

        return success(data={
            "items": items,
            "reasons": reasons,
        })

    except Exception as e:
        logger.error(f"相似文章推荐异常: article_id={article_id}, error={e}", exc_info=True)
        return error(code=500, message="获取相似文章失败，请稍后再试～")


@router.get("/trending")
async def trending_articles(
    limit: int = Query(default=10, ge=1, le=30),
    exclude_ids: str = Query(default="", description="逗号分隔的需要排除的文章ID"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    获取热门趋势——GET /api/v1/recommendations/trending

    全局热榜：结合热度分 + 新鲜度 + 多样性控制的趋势文章列表。

    参数:
        limit: 返回条数上限（1-30，默认 10）
        exclude_ids: 需要排除的文章 ID，逗号分隔

    返回:
        dict: {"code": 200, "data": {"items": [...], "reasons": {...}}, "message": "ok"}
    """
    try:
        parsed_exclude: list[int] = []
        if exclude_ids.strip():
            try:
                parsed_exclude = [int(x.strip()) for x in exclude_ids.split(",") if x.strip().isdigit()]
            except (ValueError, TypeError):
                pass

        items = await get_trending_articles(
            db=db,
            limit=limit,
            exclude_ids=parsed_exclude,
        )
        reasons = {item["article_id"]: item["reason"] for item in items}

        return success(data={
            "items": items,
            "reasons": reasons,
        })

    except Exception as e:
        logger.error(f"趋势推荐异常: error={e}", exc_info=True)
        return error(code=500, message="获取热门趋势失败，请稍后再试～")


@router.get("/category/{category}")
async def category_recommendations(
    category: str,
    limit: int = Query(default=10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    获取分类推荐——GET /api/v1/recommendations/category/{category}

    特定分类下的热门趋势文章。

    参数:
        category: 分类名（科技/游戏/动漫/设计/科普/综合）
        limit: 返回条数上限（1-30，默认 10）

    返回:
        dict: {"code": 200, "data": {"items": [...], "reasons": {...}}, "message": "ok"}
    """
    try:
        items = await get_category_recommendations(
            db=db,
            category=category,
            limit=limit,
        )
        reasons = {item["article_id"]: item["reason"] for item in items}

        return success(data={
            "items": items,
            "reasons": reasons,
        })

    except Exception as e:
        logger.error(f"分类推荐异常: category={category}, error={e}", exc_info=True)
        return error(code=500, message="获取分类推荐失败，请稍后再试～")
