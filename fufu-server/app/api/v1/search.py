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
from pydantic import BaseModel
from app.services.search import search_ddgs, search_ai, is_ddgs_available

logger = logging.getLogger("fufu.api.search")
router = APIRouter(tags=["全网搜索"])


class SearchRequest(BaseModel):
    """搜索请求体"""
    keyword: str
    max_results: int = 10
    skip_cache: bool = False  # 跳过缓存，强制实时搜索


# ========== 主搜索端点 ==========

@router.get("/web")
async def web_search_get(
    q: str = Query(default="", min_length=1),
    max_results: int = 10,
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

    try:
        # 并行启动：本地 FTS5 + AI + DDG 检测
        local_task = asyncio.ensure_future(_local_fts_fallback(keyword, page_size=max_results))
        ai_task = asyncio.ensure_future(search_ai(keyword))
        ddgs_task = asyncio.ensure_future(is_ddgs_available())

        # 等待本地结果（毫秒级），不等 DDG 检测
        local_results = await local_task

        # 本地有结果 → 立即返回，AI 继续后台跑（结果会缓存供下次用）
        if local_results:
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
            pass

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
        from app.core.database import async_session
        from sqlalchemy import select, or_
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
        from sqlalchemy import select, func
        from app.models.article import Article
        from app.core.database import async_session

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
        while len(terms) < limit:
            for t in _FALLBACK_HOT_TERMS:
                if t not in terms:
                    terms.append(t)
                    if len(terms) >= limit:
                        break

        return {
            "code": 200,
            "data": terms[:limit],
            "total": len(terms[:limit]),
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
    q: str = Query(default="", min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
):
    """
    搜索自动补全——基于文章标题的 LIKE 查询。

    返回匹配 q 关键词的文章标题列表，用于前端搜索框下拉建议。
    """
    try:
        from sqlalchemy import select
        from app.models.article import Article
        from app.core.database import async_session

        pattern = f"%{q.strip()}%"

        async with async_session() as db:
            rows = (await db.execute(
                select(Article.title, Article.id).where(
                    Article.title.like(pattern)
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
async def ai_search(q: str = Query(default="", min_length=1)):
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
