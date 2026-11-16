"""
fufu新闻 - AI 生成质检闭环
===========================
给 ai.py 的生成结果增加「质检 + 经验回灌」，参照 autocontext 的
fail-closed 与「保留有效经验 / 丢弃死胡同」思想：

1. 解析失败时，把失败模式（错误签名）沉淀到记忆层（parse_failure）
2. 生成结果过短/异常时，标记为低质并可选降级
3. 复用记忆层里已有的「标签映射修正」（tag_fix），在 AI 打标后做二次修正

设计原则：
- 纯 service 层，只依赖 memory 服务与纯函数
- 质检失败不阻断主流程（返回原值或空值，由上层兜底）
- 所有经验读写 try/except 包裹
"""
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import memory

logger = logging.getLogger("fufu.ai_quality")

# 标签映射修正的默认兜底（冷启动经验，AI 常见误打标修正）
DEFAULT_TAG_FIXES: dict[str, str] = {
    "AI": "人工智能",
    "ai": "人工智能",
    "LLM": "人工智能",
    "大模型": "人工智能",
    "5G": "科技",
    "iPhone": "科技",
}

# 摘要最小有效长度（低于此值视为低质）
MIN_SUMMARY_LEN = 20

# 打标结果的最大合法标签数（超过视为解析异常）
MAX_TAG_COUNT = 8


def _failure_signature(result: str) -> str:
    """从失败结果中提取稳定签名，用于去重经验。"""
    if not result:
        return "empty"
    # 去掉动态内容，只保留结构特征
    s = result.strip()
    if len(s) < 5:
        return "too_short"
    if s.startswith("{"):
        return "json_object_unexpected"
    if s.startswith("```"):
        return "code_block"
    # 取前 16 字符做弱签名
    return "len_" + str(len(s))


async def record_parse_failure(
    db: AsyncSession,
    task: str,
    result: str,
    *,
    note: str = "",
) -> None:
    """
    记录一次 AI 解析失败，沉淀失败模式经验。

    参数:
        task: 任务名（summary / tags / deep_summary）
        result: AI 返回的原始文本（用于提取失败签名）
    """
    try:
        sig = _failure_signature(result)
        await memory.remember(
            db,
            memory.CATEGORY_PARSE_FAILURE,
            f"{task}:{sig}",
            {"task": task, "signature": sig, "sample": (result or "")[:120]},
            note=note or f"{task} 解析失败（签名 {sig}）",
        )
    except Exception as e:
        logger.warning(f"记录解析失败经验异常: {e}")


async def apply_tag_fixes(db: AsyncSession, tags: list[str]) -> list[str]:
    """
    对 AI 打标结果做二次修正（复用记忆层的 tag_fix 经验）。

    流程：
    1. 用默认修正表做冷启动兜底
    2. 叠加记忆层中沉淀的 tag_fix 经验（score 高的优先）
    """
    try:
        fixes: dict[str, str] = dict(DEFAULT_TAG_FIXES)
        learned = await memory.recall_all(db, memory.CATEGORY_TAG_FIX)
        for item in learned:
            v = item.get("value") or {}
            src = v.get("from")
            dst = v.get("to")
            if isinstance(src, str) and isinstance(dst, str):
                fixes[src] = dst

        fixed: list[str] = []
        seen: set[str] = set()
        for t in tags:
            mapped = fixes.get(t.strip(), t).strip()
            if mapped and mapped not in seen:
                fixed.append(mapped)
                seen.add(mapped)
        return fixed

    except Exception as e:
        logger.warning(f"标签修正异常，返回原值: {e}")
        return tags


def quality_check_summary(summary: str) -> bool:
    """摘要质检：过短或纯符号视为低质。"""
    if not summary:
        return False
    text = summary.strip()
    if len(text) < MIN_SUMMARY_LEN:
        return False
    # 去掉标点/空白后仍为空则视为低质
    return bool(re.sub(r"[\s\W_]+", "", text))


def quality_check_tags(tags: list[str]) -> bool:
    """打标质检：数量异常或含空串视为低质。"""
    if not tags:
        return False
    if len(tags) > MAX_TAG_COUNT:
        return False
    return all((t or "").strip() for t in tags)
