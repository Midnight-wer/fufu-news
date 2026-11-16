"""
fufu新闻 - 全网搜索 API
==========================
多层搜索策略：ddgs → AI → 本地 FTS5 → LIKE 兜底。
带网络检测、结果缓存、重试机制。

端点列表：
- POST /api/v1/search/web          → 主搜索入口（无需认证）
- GET  /api/v1/search/web?q=xxx    → GET 兼容版本
- GET  /api/v1/search/ai?q=xxx     → 纯 AI 搜索
- GET  /api/v1/search/hot          → 热门搜索词
- GET  /api/v1/search/suggest?q=   → 搜索自动补全
"""
import asyncio
import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel, field_validator

from app.services.search import is_ddgs_available, search_ai

logger = logging.getLogger("fufu.api.search")
router = APIRouter(tags=["全网搜索"])

# 托管中的后台任务引用集合（防止 asyncio 任务被 GC 中途回收）
_BACKGROUND_TASKS: set = set()


# 搜索参数边界（补齐原先缺失的校验，避免超大 page_size 灌爆内存、
# 以及超长关键词引发全表 LIKE 扫描）
MAX_KEYWORD_LENGTH = 100
MAX_RESULTS_DEFAULT = 10
MAX_RESULTS_LIMIT = 50


class SearchRequest(BaseModel):
    """搜索请求体"""
    keyword: str
    max_results: int = MAX_RESULTS_DEFAULT
    skip_cache: bool = False  # 跳过缓存，强制实时搜索

    @field_validator("keyword")
    @classmethod
    def _keyword_not_blank(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("关键词不能为空")
        if len(v) > MAX_KEYWORD_LENGTH:
            raise ValueError(f"关键词过长（上限 {MAX_KEYWORD_LENGTH} 字符）")
        return v

    @field_validator("max_results")
    @classmethod
    def _max_results_bounded(cls, v: int) -> int:
        return max(1, min(int(v), MAX_RESULTS_LIMIT))


def _clamp_page_size(value: int) -> int:
    """把任意传入的 page_size 收敛到 1..MAX_RESULTS_LIMIT。"""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return MAX_RESULTS_DEFAULT
    return max(1, min(v, MAX_RESULTS_LIMIT))


def _cancel_task(task: "asyncio.Future") -> None:
    """安全取消一个不再需要的任务，抑制取消过程中的噪声。"""
    if task is None or task.done():
        return
    task.cancel()


def _detach_background(task: "asyncio.Future", label: str) -> None:
    """
    把一个后台任务「托管」出去：保留引用防止被 GC 中途回收，
    并挂上完成回调以便回收异常，避免 asyncio 报
    "Task exception was never retrieved"。
    """
    if task is None:
        return

    def _on_done(t: "asyncio.Future") -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.debug(f"后台任务失败（已忽略）[{label}]: {exc}")

    task.add_done_callback(_on_done)
    # 持有引用，防止被垃圾回收
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


# ========== 主搜索端点 ==========

@router.get("/web")
async def web_search_get(
    q: str = Query(default="", min_length=1, max_length=MAX_KEYWORD_LENGTH),
    max_results: int = Query(default=MAX_RESULTS_DEFAULT, ge=1, le=MAX_RESULTS_LIMIT),
    skip_cache: bool = False,
):
    """全网搜索 GET 兼容"""
    return await _do_search(q, max_results, skip_cache=skip_cache)


@router.post("/web")
async def web_search_post(req: SearchRequest):
    """全网搜索 POST 主入口"""
    return await _do_search(req.keyword, req.max_results, skip_cache=req.skip_cache)


async def _do_search(keyword: str, max_results: int = 10, skip_cache: bool = False):
    """
    快速搜索策略——本地优先，AI 后台缓存。

    1. 本地 FTS5 毫秒级 → 有结果就立即返回，不等待 AI
    2. AI 在后台运行，结果缓存后下次搜索秒出
    3. 本地无结果 → 等 AI 最多 10s
    """
    keyword = keyword.strip()
    if not keyword:
        return {
            "code": 200, "data": [], "total": 0,
            "message": "关键词不能为空", "source": "local",
        }
    max_results = _clamp_page_size(max_results)

    try:
        # 并行启动：本地 FTS5 + AI + DDG 检测
        local_task = asyncio.ensure_future(_local_fts_fallback(keyword, page_size=max_results))
        ai_task = asyncio.ensure_future(search_ai(keyword))
        ddgs_task = asyncio.ensure_future(is_ddgs_available())

        # 等待本地结果（毫秒级），不等 DDG 检测
        local_results = await local_task

        # 本地有结果 → 立即返回。
        # AI 任务保留在后台跑（结果会缓存供下次用），但不再放任不管：
        # 给它加完成回调回收异常，避免出现 "Task exception was never retrieved"，
        # 同时 DDG 检测任务已无用，显式取消。
        if local_results:
            _detach_background(ai_task, f"ai-search:{keyword[:20]}")
            _cancel_task(ddgs_task)
            return {
                "code": 200, "data": local_results, "total": len(local_results),
                "message": "local", "source": "local",
                "ai_pending": True,
            }

        # 本地无结果 → 等 AI，最多 10s，同时等 DDG 检测结果
        ddgs_ok = False
        try:
            ddgs_ok = await asyncio.wait_for(ddgs_task, timeout=3.0)
        except asyncio.TimeoutError:
            _cancel_task(ddgs_task)

        ai_results = []
        try:
            done, pending = await asyncio.wait([ai_task], timeout=10.0)
            for d in done:
                r = d.result()
                if r:
                    ai_results = r
                    break
            for p in pending:
                p.cancel()
        except Exception:
            logger.warning("AI 搜索等待异常", exc_info=True)

        if ai_results:
            return {
                "code": 200, "data": ai_results, "total": len(ai_results),
                "message": "ok", "source": "web",
                "ddgs_available": ddgs_ok,
            }

        return {
            "code": 200, "data": [], "total": 0,
            "message": "no_results", "source": "none",
            "ddgs_available": ddgs_ok,
        }
    except Exception:
        logger.error(f"搜索异常: {keyword!r}", exc_info=True)
        return {"code": 200, "data": [], "total": 0, "message": "搜索服务异常", "source": "error"}


async def _local_fts_fallback(keyword: str, page_size: int = 10) -> list[dict]:
    """本地搜索——FTS5 全文搜索 + LIKE 兜底"""
    try:
        from sqlalchemy import or_, select

        from app.core.database import async_session
        from app.models.article import Article
        from app.models.source import Source

        async with async_session() as db:
            ids = []
            # 先尝试 FTS5
            try:
                escaped = keyword.replace('"', '""')
                fts_q = 'SELECT rowid FROM article_fts WHERE article_fts MATCH ? ORDER BY rank LIMIT ?'
                conn = await db.connection()
                raw = await conn.exec_driver_sql(fts_q, (f'"{escaped}"', page_size))
                ids = [row[0] for row in raw.fetchall()]
            except Exception:
                logger.debug(f"FTS5 搜索失败，回退到 LIKE: {keyword[:20]!r}")

            # FTS5 无结果 → LIKE 兜底
            if not ids:
                # 转义 LIKE 通配符，防止用户输入 % _ 被错误匹配
                safe_keyword = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                pattern = f'%{safe_keyword}%'
                rows = (await db.execute(
                    select(Article).where(
                        or_(Article.title.like(pattern), Article.summary.like(pattern))
                    ).order_by(Article.published_at.desc()).limit(page_size)
                )).scalars().all()
            else:
                rows = (await db.execute(
                    select(Article).where(Article.id.in_(ids))
                )).scalars().all()
                rows.sort(key=lambda x: ids.index(x.id) if x.id in ids else 9999)

            if not rows:
                return []

            source_ids = {r.source_id for r in rows}
            source_map = {}
            if source_ids:
                src_rows = (await db.execute(
                    select(Source.id, Source.name).where(Source.id.in_(source_ids))
                )).all()
                source_map = {s[0]: s[1] for s in src_rows}

            results = []
            for r in rows:
                results.append({
                    "title": r.title or "",
                    "url": f"/articles/{r.id}",
                    "snippet": (r.summary or "")[:200],
                    "source": source_map.get(r.source_id, "本地文章"),
                    "published_at": r.published_at.isoformat() if r.published_at else None,
                    "local_id": r.id,
                })
            return results
    except Exception:
        logger.warning(f"本地搜索异常: {keyword[:20]!r}", exc_info=True)
        return []


# ========== 热门搜索词端点 ==========

# 硬编码兜底热门词（当数据库无标签时使用）
_FALLBACK_HOT_TERMS = [
    "AI 人工智能", "芯片制裁", "新番推荐", "游戏评测",
    "设计趋势", "科技新闻", "手机评测", "开源项目",
    "独立游戏", "前端开发", "自动驾驶", "航天发射",
]


@router.get("/hot")
async def get_hot_search_terms(limit: int = Query(default=10, ge=1, le=50)):
    """
    获取热门搜索词。

    优先从文章标签（tags JSON 字段）聚合最常见的标签；
    如果标签不足，则使用最近抓取的文章标题关键词；
    最后使用硬编码兜底列表。
    """
    try:
        from sqlalchemy import select

        from app.core.database import async_session
        from app.models.article import Article

        terms = []
        async with async_session() as db:
            # 策略 1：从文章标签聚合（tags JSON 字段）
            try:
                rows = (await db.execute(
                    select(Article.tags).where(
                        Article.tags.isnot(None)
                    ).limit(200)
                )).scalars().all()

                tag_counts: dict[str, int] = {}
                for tags in rows:
                    if isinstance(tags, list):
                        for t in tags:
                            t = str(t).strip()
                            if t and len(t) <= 12:
                                tag_counts[t] = tag_counts.get(t, 0) + 1

                terms = sorted(tag_counts, key=lambda k: tag_counts[k], reverse=True)[:limit]
            except Exception:
                logger.debug("热门搜索：标签聚合失败，尝试标题策略", exc_info=True)

            # 策略 2：标签不足，从最近文章标题提取关键词
            if len(terms) < 6:
                try:
                    title_rows = (await db.execute(
                        select(Article.title).where(
                            Article.title.isnot(None)
                        ).order_by(Article.fetched_at.desc()).limit(100)
                    )).scalars().all()

                    seen = set(terms)
                    for title in title_rows:
                        # 提取 4-6 字符的短关键词（中文字符）
                        import re
                        # 尝试提取中文关键词片段
                        chunks = re.findall(r'[一-鿿\w]{4,10}', str(title))
                        for chunk in chunks:
                            # 过滤掉全英文/数字的片段
                            if re.search(r'[一-鿿]', chunk) and chunk not in seen:
                                seen.add(chunk)
                                terms.append(chunk)
                                if len(terms) >= limit:
                                    break
                        if len(terms) >= limit:
                            break
                except Exception:
                    logger.debug("热门搜索：标题策略失败", exc_info=True)

        # 策略 3：硬编码兜底
        #
        # 修复说明（原实现是 P0 级故障）：
        #   原代码为 `while len(terms) < limit: for t in _FALLBACK_HOT_TERMS: ...`
        #   ——兜底词表只有 12 条且只追加不重复项，当 limit > 可用词数时
        #   len(terms) 永远无法继续增长，外层 while 永不退出；
        #   该协程体内没有任何 await，会直接占死整个事件循环，
        #   且此端点无需认证，一次请求即可让全站永久无响应。
        # 现在改为有界填充：单趟遍历，凑不满就直接截断返回。
        if len(terms) < limit:
            for t in _FALLBACK_HOT_TERMS:
                if len(terms) >= limit:
                    break
                if t not in terms:
                    terms.append(t)

        result = terms[:limit]
        return {
            "code": 200,
            "data": result,
            "total": len(result),
            "message": "ok",
        }
    except Exception as e:
        logger.error(f"热门搜索词获取失败: {e}", exc_info=True)
        return {
            "code": 200,
            "data": _FALLBACK_HOT_TERMS[:limit],
            "total": min(len(_FALLBACK_HOT_TERMS), limit),
            "message": "fallback",
        }


# ========== 搜索自动补全端点 ==========


@router.get("/suggest")
async def search_suggest(
    q: str = Query(default="", min_length=1, max_length=MAX_KEYWORD_LENGTH),
    limit: int = Query(default=5, ge=1, le=20),
):
    """
    搜索自动补全——基于文章标题的 LIKE 查询。

    返回匹配 q 关键词的文章标题列表，用于前端搜索框下拉建议。
    """
    try:
        from sqlalchemy import select

        from app.core.database import async_session
        from app.models.article import Article

        # 转义 LIKE 通配符：用户输入的 % 和 _ 不应被当作通配符，
        # 否则 "100%" 会匹配到所有标题，既不准又会拖慢查询。
        keyword = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{keyword}%"

        async with async_session() as db:
            rows = (await db.execute(
                select(Article.title, Article.id).where(
                    Article.title.like(pattern, escape="\\")
                ).order_by(Article.fetched_at.desc()).limit(limit)
            )).all()

        suggestions = [
            {"title": str(r[0]), "article_id": r[1]}
            for r in rows
        ]

        return {
            "code": 200,
            "data": suggestions,
            "total": len(suggestions),
            "message": "ok",
        }
    except Exception as e:
        logger.error(f"搜索建议获取失败: {e}", exc_info=True)
        return {
            "code": 200,
            "data": [],
            "total": 0,
            "message": f"error: {str(e)}",
        }


# ========== 纯 AI 搜索端点 ==========

@router.get("/ai")
async def ai_search(q: str = Query(default="", min_length=1, max_length=MAX_KEYWORD_LENGTH)):
    """纯 AI 搜索端点（DeepSeek API）"""
    try:
        results = await search_ai(q)
        return {
            "code": 200, "data": results, "total": len(results),
            "message": f"AI搜索, 共{len(results)}条",
            "source": "ai",
        }
    except Exception:
        logger.error(f"AI 搜索端点异常: {q[:30]!r}", exc_info=True)
        return {"code": 200, "data": [], "total": 0, "message": "AI搜索服务异常", "source": "error"}
