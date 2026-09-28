"""
fufu新闻 - 成就系统 API
===========================
提供成就相关的 REST API 端点：

- GET  /achievements          → 获取所有成就及当前用户进度
- GET  /achievements/unlocked → 获取当前用户已解锁的成就
- POST /achievements/check    → 递增成就进度并检查是否新解锁
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.achievement import AchievementDef, UserAchievement

# 创建成就路由实例
router = APIRouter()


class AchievementOut(BaseModel):
    """
    成就输出模型——用于 API 响应的成就数据结构。

    字段说明：
    - key: 成就键名（唯一标识）
    - title: 成就标题（中文）
    - description: 成就描述
    - icon: 成就图标（emoji）
    - category: 成就类别
    - tier: 成就等级（1-3）
    - progress: 当前用户在此成就上的进度
    - threshold: 解锁所需阈值
    - unlocked: 是否已解锁
    - unlocked_at: 解锁时间（ISO 格式字符串）
    """
    key: str
    title: str
    description: str
    icon: str
    category: str
    tier: int
    progress: int = 0
    threshold: int = 1
    unlocked: bool = False
    unlocked_at: str | None = None

    model_config = {"from_attributes": True}


class CheckRequest(BaseModel):
    """
    成就进度检查请求体模型。

    字段说明：
    - key: 要检查的成就键名
    - count: 递增的进度数值（默认每次 +1）
    """
    key: str
    count: int = 1


def _match_seed_threshold(key: str) -> int:
    """
    根据成就键名推断默认阈值。

    解析规则：
    - 键名含 "100" → 阈值 100
    - 键名含 "50"  → 阈值 50
    - 键名含 "10"  → 阈值 10
    - 键名含 "5"   → 阈值 5
    - 键名含 "first" → 阈值 1
    - 默认 → 1

    参数:
        key: 成就键名（如 "read_100", "first_login" 等）

    返回:
        int: 推断的解锁阈值
    """
    if "100" in key:
        return 100
    if "50" in key:
        return 50
    if "10" in key:
        return 10
    if "5" in key:
        return 5
    if "first" in key:
        return 1
    if "daily_3" in key:
        return 3
    return 1


@router.get("", response_model=list[AchievementOut])
async def list_achievements(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取所有成就及当前用户进度——GET /api/v1/achievements

    返回所有成就定义以及当前用户的各项进度。
    对于用户尚未产生进度的成就，progress 为 0。

    返回:
        list[AchievementOut]: 所有成就及用户进度列表
    """
    # 获取所有成就定义
    result = await db.execute(
        select(AchievementDef).order_by(AchievementDef.category, AchievementDef.tier)
    )
    defs = result.scalars().all()

    # 获取当前用户的所有成就进度
    ua_result = await db.execute(
        select(UserAchievement).where(UserAchievement.user_id == _user.id)
    )
    ua_map: dict[str, UserAchievement] = {
        ua.achievement_key: ua for ua in ua_result.scalars().all()
    }

    # 合并成就定义和用户进度
    out = []
    for d in defs:
        ua = ua_map.get(d.key)
        out.append(AchievementOut(
            key=d.key,
            title=d.title,
            description=d.description,
            icon=d.icon,
            category=d.category,
            tier=d.tier,
            progress=ua.progress if ua else 0,
            threshold=ua.threshold if ua else _match_seed_threshold(d.key),
            unlocked=ua.unlocked if ua else False,
            unlocked_at=ua.unlocked_at.isoformat() if (ua and ua.unlocked_at) else None,
        ))
    return out


@router.get("/unlocked", response_model=list[AchievementOut])
async def list_unlocked(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取已解锁成就——GET /api/v1/achievements/unlocked

    仅返回当前用户已经解锁的成就列表。

    返回:
        list[AchievementOut]: 已解锁的成就列表
    """
    # 查询用户已解锁的成就记录
    result = await db.execute(
        select(UserAchievement).where(
            UserAchievement.user_id == _user.id,
            UserAchievement.unlocked == True,
        )
    )
    uas = result.scalars().all()
    keys = [ua.achievement_key for ua in uas]

    # 查询对应的成就定义
    defs_result = await db.execute(
        select(AchievementDef).where(AchievementDef.key.in_(keys))
    )
    defs_map = {d.key: d for d in defs_result.scalars().all()}

    # 构建返回列表
    out = []
    for ua in uas:
        d = defs_map.get(ua.achievement_key)
        if not d:
            continue
        out.append(AchievementOut(
            key=d.key,
            title=d.title,
            description=d.description,
            icon=d.icon,
            category=d.category,
            tier=d.tier,
            progress=ua.progress,
            threshold=ua.threshold,
            unlocked=True,
            unlocked_at=ua.unlocked_at.isoformat() if ua.unlocked_at else None,
        ))
    return out


@router.post("/check", response_model=list[AchievementOut])
async def check_achievements(
    body: CheckRequest,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    递增成就进度并检查解锁——POST /api/v1/achievements/check

    前端在用户完成某项操作后调用此接口（如阅读了一篇文章、收藏等），
    后端会自动递增进度，当进度达到阈值时自动解锁成就。

    如果成就刚刚被解锁，返回列表中会包含该成就。
    如果成就已经解锁过，返回空列表。

    参数:
        body: CheckRequest（key: 成就键名, count: 递增数目）

    返回:
        list[AchievementOut]: 本次新解锁的成就列表（空列表表示没有新解锁）
    """
    threshold = _match_seed_threshold(body.key)

    # 查询或创建用户成就进度记录（upsert 逻辑）
    result = await db.execute(
        select(UserAchievement).where(
            UserAchievement.user_id == _user.id,
            UserAchievement.achievement_key == body.key,
        )
    )
    ua = result.scalar_one_or_none()

    if ua is None:
        # 首次产生此成就的进度，创建新记录
        ua = UserAchievement(
            user_id=_user.id,
            achievement_key=body.key,
            progress=body.count,
            threshold=threshold,
        )
        db.add(ua)
    else:
        # 已有进度记录，递增
        ua.progress += body.count
        # 进度不超过阈值（防止溢出显示）
        if ua.progress > ua.threshold:
            ua.progress = ua.threshold

    # 检查是否新解锁
    newly_unlocked = []
    if not ua.unlocked and ua.progress >= ua.threshold:
        from datetime import datetime, timezone
        ua.unlocked = True
        ua.unlocked_at = datetime.now(timezone.utc)
        ua.notified = False

        # 获取成就定义用于返回
        def_result = await db.execute(
            select(AchievementDef).where(AchievementDef.key == body.key)
        )
        d = def_result.scalar_one_or_none()
        if d:
            newly_unlocked.append(AchievementOut(
                key=d.key,
                title=d.title,
                description=d.description,
                icon=d.icon,
                category=d.category,
                tier=d.tier,
                progress=ua.progress,
                threshold=ua.threshold,
                unlocked=True,
                unlocked_at=ua.unlocked_at.isoformat() if ua.unlocked_at else None,
            ))

    await db.flush()
    return newly_unlocked
