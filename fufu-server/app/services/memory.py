"""
fufu新闻 - 经验记忆服务层
==========================
「经验记忆存储层」的核心，把 agent 运行中沉淀的经验结构化保存与检索。

参照 autocontext 的 knowledge/（playbook + hints）与 agent-beacon 的跨会话记忆：
- 保存（remember）：把可复用经验写入 AgentExperience，带类别与唯一键去重
- 检索（recall）：按类别 + 键取出经验，供 AI 生成 / 推荐引擎复用
- 门控提升（reinforce / penalize）：命中成功加分、失败减分，
  低于阈值的经验自然淘汰（fail-closed）

设计原则：
- 纯 service 层，不引用 HTTP 类型
- 所有操作 try/except 包裹，失败不影响主流程
- 幂等：同 key 重复 remember 只更新不新增
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experience import AgentExperience

logger = logging.getLogger("fufu.memory")

# 经验类别常量
CATEGORY_PROMPT_TWEAK = "prompt_tweak"      # prompt 微调经验
CATEGORY_PARSE_FAILURE = "parse_failure"    # 解析失败模式（错误签名 → 修复策略）
CATEGORY_TAG_FIX = "tag_fix"                # 标签映射修正
CATEGORY_STRATEGY_TUNE = "strategy_tune"    # 推荐策略调参轨迹

# 门控提升阈值：score 低于此值的经验不再返回（视为不可信）
RECALL_MIN_SCORE = 0.3

# 时间衰减半衰期（天）：经验久未命中则自然降温
EXPERIENCE_HALF_LIFE_DAYS = 60.0

# 每类别经验条数上限：超过则淘汰最弱（score 最低 + last_used_at 最旧）的一条，
# 防止经验表无限膨胀（参照 autocontext 的「容量有界」原则）。
MAX_EXPERIENCE_PER_CATEGORY = 500


async def remember(
    db: AsyncSession,
    category: str,
    key: str,
    value: dict,
    *,
    note: str | None = None,
) -> None:
    """
    保存一条经验（按 category + key 去重，已存在则更新 value 并加分）。

    参数:
        category: 经验类别
        key: 唯一键
        value: 结构化经验内容（JSON 可序列化）
        note: 可读说明（可选）
    """
    try:
        result = await db.execute(
            select(AgentExperience).where(
                AgentExperience.category == category,
                AgentExperience.key == key,
            )
        )
        exp = result.scalar_one_or_none()
        if exp is None:
            exp = AgentExperience(
                category=category, key=key, value=value, score=1.0, note=note
            )
            db.add(exp)
            # 先 flush 让新条目落库，再做容量控制（保证 count 是真实条数）
            await db.flush()
            await _evict_if_over_limit(db, category)
        else:
            exp.value = value
            exp.score = min(exp.score + 0.5, 10.0)  # 反复命中加分（门控提升）
            exp.note = note or exp.note
            exp.last_used_at = datetime.now(timezone.utc)
            await db.flush()
        logger.debug(f"经验已保存: {category}/{key}")

    except Exception as e:
        logger.warning(f"保存经验失败（忽略）: {category}/{key}, error={e}")


async def _evict_if_over_limit(db: AsyncSession, category: str) -> None:
    """
    容量控制：某类别经验条数超过上限时，淘汰最弱的一条，直到回落到上限。

    淘汰规则：优先淘汰 score 最低的；同分时淘汰 last_used_at 最旧的。
    前置条件：调用前新增条目已 flush，count 为真实条数，删到 = MAX 即可。
    """
    try:
        count = (await db.execute(
            select(func.count()).select_from(AgentExperience).where(
                AgentExperience.category == category
            )
        )).scalar() or 0

        while count > MAX_EXPERIENCE_PER_CATEGORY:
            # 找出最弱的一条（score 最低，其次 last_used_at 最旧）
            victim = (await db.execute(
                select(AgentExperience.id)
                .where(AgentExperience.category == category)
                .order_by(AgentExperience.score.asc(), AgentExperience.last_used_at.asc())
                .limit(1)
            )).scalar_one_or_none()
            if victim is None:
                break
            await db.execute(
                delete(AgentExperience).where(AgentExperience.id == victim)
            )
            count -= 1
            logger.debug(f"经验淘汰: category={category}, id={victim}")
    except Exception as e:
        logger.warning(f"经验容量控制失败（忽略）: category={category}, error={e}")


async def recall(
    db: AsyncSession,
    category: str,
    key: str,
) -> dict | None:
    """
    检索一条经验。

    返回:
        dict | None: 经验内容；不存在或可信度低于阈值时返回 None（fail-closed）。
    """
    try:
        result = await db.execute(
            select(AgentExperience).where(
                AgentExperience.category == category,
                AgentExperience.key == key,
            )
        )
        exp = result.scalar_one_or_none()
        if exp is None or exp.score < RECALL_MIN_SCORE:
            return None
        return exp.value

    except Exception as e:
        logger.warning(f"检索经验失败: {category}/{key}, error={e}")
        return None


async def recall_all(db: AsyncSession, category: str, limit: int = 20) -> list[dict]:
    """
    检索某类别下所有可信经验（按 score 降序）。

    返回:
        list[dict]: [{"key": ..., "value": ..., "score": ...}, ...]
    """
    try:
        result = await db.execute(
            select(AgentExperience)
            .where(
                AgentExperience.category == category,
                AgentExperience.score >= RECALL_MIN_SCORE,
            )
            .order_by(AgentExperience.score.desc())
            .limit(limit)
        )
        return [
            {"key": e.key, "value": e.value, "score": e.score}
            for e in result.scalars().all()
        ]

    except Exception as e:
        logger.warning(f"批量检索经验失败: {category}, error={e}")
        return []


async def reinforce(db: AsyncSession, category: str, key: str, delta: float = 1.0) -> None:
    """
    提升经验可信度（命中成功）。

    参数:
        delta: 增量（正数加分）
    """
    try:
        result = await db.execute(
            select(AgentExperience).where(
                AgentExperience.category == category,
                AgentExperience.key == key,
            )
        )
        exp = result.scalar_one_or_none()
        if exp is not None:
            exp.score = min(exp.score + delta, 10.0)
            exp.last_used_at = datetime.now(timezone.utc)
            await db.flush()

    except Exception as e:
        logger.warning(f"经验加分失败: {category}/{key}, error={e}")


async def penalize(db: AsyncSession, category: str, key: str, delta: float = 1.0) -> None:
    """
    降低经验可信度（命中失败），低于阈值后自然淘汰。

    参数:
        delta: 减量（正数扣分）
    """
    try:
        result = await db.execute(
            select(AgentExperience).where(
                AgentExperience.category == category,
                AgentExperience.key == key,
            )
        )
        exp = result.scalar_one_or_none()
        if exp is not None:
            exp.score = max(exp.score - delta, 0.0)
            await db.flush()

    except Exception as e:
        logger.warning(f"经验扣分失败: {category}/{key}, error={e}")
