"""
fufu新闻 - 自学习服务层
========================
「推荐引擎自学习」的核心闭环，把业界 self-improving-agent 的三支柱
（记忆层 / 反馈闭环 / 门控提升）落地到推荐引擎上。

核心机制：
1. 反馈回流（record_feedback）：把 read_duration / 收藏等真实信号
   转化为标签兴趣强度的增量，写入 UserProfile。
2. 时间衰减（decay）：兴趣强度随时间指数衰减，久未触达的标签自然降温，
   避免被历史行为永久绑定。
3. 兴趣读取（get_interest_weights）：供推荐引擎读取，画像为空时
   回退到空 dict（fail-closed，推荐引擎自动用默认权重兜底）。

设计原则（借鉴 autocontext）：
- 纯 service 层：不引用 FastAPI HTTP 类型，只依赖 SQLAlchemy 会话
- 可关停：所有逻辑都在 try/except 内，任何异常不向上抛、不影响主流程
- 幂等：同一反馈重复计算不改变结论（用 max/累加 + 衰减保证稳定）
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import UserProfile

logger = logging.getLogger("fufu.learning")

# ========== 学习参数 ==========

# 反馈信号权重（正反馈越大越强）
WEIGHT_FAVORITE = 8.0   # 收藏：最强兴趣信号
WEIGHT_LONG_READ = 0.5  # 阅读时长：每 60 秒 +0.5
WEIGHT_SHORT_READ = 0.1 # 短阅读也有基础兴趣（至少点开看了）

# 兴趣强度半衰期（天）：超过这个时间强度减半
INTEREST_HALF_LIFE_DAYS = 30.0

# 单标签兴趣强度上限，防止异常值污染
MAX_SCORE = 100.0

# 读取画像时取前 N 个最强标签
TOP_INTERESTS = 30


def _decay_factor(last_seen_at: datetime, now: datetime | None = None) -> float:
    """
    计算时间衰减因子：0 < factor <= 1。

    半衰期 INTEREST_HALF_LIFE_DAYS 天。刚触达的标签 factor≈1，
    久未触达的标签 factor 趋近 0，让兴趣自然降温。
    """
    now = now or datetime.now(timezone.utc)
    if last_seen_at is None:
        # 防御：last_seen_at 意外为 None 时视为「刚触达」，不衰减
        return 1.0
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    days = max((now - last_seen_at).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (days / INTEREST_HALF_LIFE_DAYS)


async def _ensure_profile(db: AsyncSession, user_id: int, tag: str) -> UserProfile:
    """取（或按需创建）某个用户对某标签的画像记录。"""
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.user_id == user_id,
            UserProfile.tag == tag,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        # 显式赋值 last_seen_at：column default 只在 flush/insert 时才填充，
        # 若依赖懒填充，紧随其后的 _decay_factor 会拿到 None 而抛异常。
        profile = UserProfile(
            user_id=user_id,
            tag=tag,
            score=0.0,
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(profile)
    return profile


async def record_feedback(
    db: AsyncSession,
    user_id: int,
    tags: list[str],
    *,
    read_duration: int = 0,
    is_favorite: bool = False,
) -> None:
    """
    记录一次用户反馈，更新其兴趣画像。

    参数:
        user_id: 用户 ID
        tags: 文章标签列表（AI 打标结果）
        read_duration: 阅读时长（秒）
        is_favorite: 是否收藏

    说明:
        - 增量 = 阅读信号 + 收藏信号
        - 先按时间衰减旧分数，再累加新增量，保证兴趣随时间和行为演进
        - 任何异常都被吞掉并告警，绝不影响主流程（阅读/收藏照常成功）
    """
    try:
        if not tags:
            return
        now = datetime.now(timezone.utc)

        # 计算本次反馈的信号增量
        read_delta = WEIGHT_SHORT_READ
        if read_duration > 0:
            read_delta = WEIGHT_LONG_READ * (read_duration / 60.0)
        fav_delta = WEIGHT_FAVORITE if is_favorite else 0.0
        delta = read_delta + fav_delta

        for raw_tag in tags:
            tag = (raw_tag or "").strip()
            if not tag:
                continue
            profile = await _ensure_profile(db, user_id, tag)
            # 时间衰减 + 累加新信号，并夹紧到 [0, MAX_SCORE]
            profile.score = min(
                max(profile.score * _decay_factor(profile.last_seen_at, now) + delta, 0.0),
                MAX_SCORE,
            )
            profile.last_seen_at = now

        await db.flush()
        logger.debug(f"兴趣画像更新: user_id={user_id}, tags={len(tags)}, delta={delta:.2f}")

    except Exception as e:
        logger.warning(f"兴趣画像更新失败（忽略）: user_id={user_id}, error={e}")


async def get_interest_weights(db: AsyncSession, user_id: int) -> dict[str, float]:
    """
    读取用户的兴趣权重（标签 -> 强度，已做时间衰减）。

    返回:
        dict[str, float]: 前 TOP_INTERESTS 个最强标签及其强度。
        画像为空或异常时返回空 dict（fail-closed，调用方回退默认策略）。
    """
    try:
        result = await db.execute(
            select(UserProfile)
            .where(UserProfile.user_id == user_id)
            .order_by(UserProfile.score.desc())
            .limit(TOP_INTERESTS)
        )
        rows = result.scalars().all()
        now = datetime.now(timezone.utc)
        weights: dict[str, float] = {}
        for row in rows:
            score = row.score * _decay_factor(row.last_seen_at, now)
            if score > 0:
                weights[row.tag] = round(score, 4)
        return weights

    except Exception as e:
        logger.warning(f"读取兴趣画像失败（回退空）: user_id={user_id}, error={e}")
        return {}
