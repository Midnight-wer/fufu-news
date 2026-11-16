"""
fufu新闻 - 画像/经验观察接口
============================
提供自学习机制的只读观察端点，便于在运行时查看：
- 兴趣画像（user_profile）是否在正常累积
- 经验库（agent_experience）的统计与分布

设计原则：
- 只读（除重置画像外），不改变任何学习逻辑
- 均需鉴权（get_current_user），未登录返回 401
- 复用 learning / memory 服务，不直接写 SQL
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.experience import AgentExperience
from app.models.profile import UserProfile
from app.models.user import User
from app.schemas.response import error, success
from app.services.learning import get_interest_weights

logger = logging.getLogger("fufu.profile")

router = APIRouter(tags=["画像"])


@router.get("/interests")
async def my_interests(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    获取当前用户的兴趣画像——GET /api/v1/profile/interests

    返回学习出的标签兴趣权重（按强度降序），以及画像记录条数。

    返回:
        dict: {"code":200, "data": {"interests": [{"tag":..., "score":...}], "count":...}}
    """
    try:
        weights = await get_interest_weights(db, user.id)
        interests = [
            {"tag": tag, "score": score}
            for tag, score in sorted(weights.items(), key=lambda x: x[1], reverse=True)
        ]
        return success(data={
            "interests": interests,
            "count": len(interests),
        })

    except Exception as e:
        logger.error(f"获取兴趣画像失败: user_id={user.id}, error={e}", exc_info=True)
        return error(code=500, message="获取兴趣画像失败，请稍后再试～")


@router.get("/experiences")
async def experience_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    获取经验库统计——GET /api/v1/profile/experiences

    返回各类别经验条数、可信度分布、以及 top 经验概览。

    返回:
        dict: {"code":200, "data": {"total":..., "by_category": {...}, "top": [...]}}
    """
    try:
        # 各类别条数统计
        cat_rows = (await db.execute(
            select(
                AgentExperience.category,
                func.count().label("cnt"),
            ).group_by(AgentExperience.category)
        )).all()
        by_category = {row.category: row.cnt for row in cat_rows}

        total = sum(by_category.values())

        # top 经验概览（score 最高的若干条，不返回完整 value 以控制体量）
        top_rows = (await db.execute(
            select(
                AgentExperience.category,
                AgentExperience.key,
                AgentExperience.score,
            )
            .order_by(AgentExperience.score.desc())
            .limit(20)
        )).all()
        top = [
            {"category": r.category, "key": r.key, "score": round(r.score, 2)}
            for r in top_rows
        ]

        # 画像总记录数（跨用户，便于观察全局累积）
        profile_count = (await db.execute(
            select(func.count()).select_from(UserProfile)
        )).scalar() or 0

        return success(data={
            "total": total,
            "by_category": by_category,
            "top": top,
            "profile_rows": profile_count,
        })

    except Exception as e:
        logger.error(f"获取经验统计失败: error={e}", exc_info=True)
        return error(code=500, message="获取经验统计失败，请稍后再试～")


@router.delete("/interests")
async def reset_interests(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    重置当前用户的兴趣画像——DELETE /api/v1/profile/interests

    清空该用户的 user_profile 记录，让其重新从零学习。

    返回:
        dict: {"code":200, "data": {"deleted": <条数>}}
    """
    try:
        from sqlalchemy import delete as _delete

        result = await db.execute(
            _delete(UserProfile).where(UserProfile.user_id == user.id)
        )
        await db.flush()
        deleted = result.rowcount or 0
        logger.info(f"重置兴趣画像: user_id={user.id}, 删除 {deleted} 条")
        return success(data={"deleted": deleted}, message="兴趣画像已重置～")

    except Exception as e:
        logger.error(f"重置兴趣画像失败: user_id={user.id}, error={e}", exc_info=True)
        return error(code=500, message="重置兴趣画像失败，请稍后再试～")
