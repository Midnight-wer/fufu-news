"""
fufu新闻 - 文章接口
=======================
提供文章相关的 REST API 端点：
- GET  /articles              → 分页获取文章列表（支持筛选和排序）
- GET  /articles/search       → FTS5 全文搜索本地文章
- GET  /articles/{id}         → 获取单篇文章详情
- PATCH /articles/{id}         → 更新文章状态（已读/收藏/进度等）
- GET  /articles/web-search   → 旧版全网搜索兼容端点
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import joinedload
from app.core.database import get_db
from app.models.article import Article
from app.models.source import Source
from app.models.user import User
from app.schemas.article import ArticleUpdate, ArticleResponse, ArticleListResponse
from app.api.deps import get_current_user
from app.services.search import search_ddgs
from app.services.aggregator import find_related_from_other_sources
from app.schemas.aggregation import AggregatedResponse

# 创建文章路由实例
router = APIRouter(tags=["文章"])


# ========== 旧版全网搜索兼容（转发到新端点） ==========
@router.get("/web-search")
async def web_search_legacy(
    q: str = Query(default="", min_length=1),
    max_results: int = Query(default=15, ge=1, le=30),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=15, ge=1, le=30),
):
    """
    旧版兼容端点——GET /api/v1/articles/web-search

    内部转发到 ddgs 搜索引擎，保持向后兼容旧版前端调用。

    参数:
        q: 搜索关键词（必填，长度 >= 1）
        max_results: 最大返回结果数（1-30）
        page: 页码（大于等于 1）
        page_size: 每页条数（1-30）

    返回:
        dict: 搜索结果，包含 code/data/total/page/page_size/message
    """
    results = await search_ddgs(q, max_results)
    return {
        "code": 200, "data": results, "total": len(results),
        "page": page, "page_size": page_size,
        "message": f"ok, 共{len(results)}条结果" if results else "no_results"
    }


def _since_cutoff(since: str) -> datetime | None:
    """
    根据时间筛选参数计算截止时间点。

    参数:
        since: 时间筛选标识（"24h"/"3d"/"7d"/"all"）

    返回:
        datetime | None: 截止时间（UTC），"all" 返回 None 表示不限制
    """
    if since == "24h":
        return datetime.now(timezone.utc) - timedelta(hours=24)
    if since == "3d":
        return datetime.now(timezone.utc) - timedelta(days=3)
    if since == "7d":
        return datetime.now(timezone.utc) - timedelta(days=7)
    return None


@router.get("", response_model=ArticleListResponse)
async def list_articles(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_read: bool | None = None,
    is_favorite: bool | None = None,
    is_later: bool | None = None,
    source_id: int | None = None,
    sort: str = Query(default="latest", pattern=r"^(latest|random)$"),
    since: str = Query(default="all", pattern=r"^(all|24h|3d|7d)$"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    获取文章列表——GET /api/v1/articles

    支持多条件筛选、排序和分页。

    查询参数:
        page: 页码（从 1 开始）
        page_size: 每页条数（1-100）
        is_read: 按已读/未读筛选
        is_favorite: 按收藏状态筛选
        is_later: 按稍后阅读筛选
        source_id: 按订阅源 ID 筛选
        sort: 排序方式（"latest" 按抓取时间降序 / "random" 随机排序）
        since: 时间范围筛选（"24h"/"3d"/"7d"/"all"）

    返回:
        ArticleListResponse: 包含 articles 列表和分页信息
    """
    # 构建基本查询
    q = select(Article)

    # 可选筛选条件：已读/未读 所有文章都没有用户维度，目前全局共享
    if is_read is not None:
        q = q.where(Article.is_read == is_read)
    if is_favorite is not None:
        q = q.where(Article.is_favorite == is_favorite)
    if is_later is not None:
        q = q.where(Article.is_later == is_later)
    if source_id is not None:
        q = q.where(Article.source_id == source_id)

    # 时间范围筛选
    cutoff = _since_cutoff(since)
    if cutoff is not None:
        # 如果文章有 published_at，用 published_at 比较
        # 如果 published_at 为空，则用 fetched_at 兜底
        q = q.where(
            (Article.published_at >= cutoff) |
            ((Article.published_at == None) & (Article.fetched_at >= cutoff))
        )

    # 计算符合条件的总数
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # 分页和排序
    offset = (page - 1) * page_size
    order_by = func.random() if sort == "random" else Article.fetched_at.desc()
    rows = (await db.execute(
        q.order_by(order_by).offset(offset).limit(page_size)
    )).scalars().all()

    # 批量获取关联的订阅源信息（避免 N+1 查询）
    source_ids = {r.source_id for r in rows}
    source_map: dict[int, tuple] = {}
    if source_ids:
        src_rows = (await db.execute(
            select(Source.id, Source.name, Source.folder).where(Source.id.in_(source_ids))
        )).all()
        source_map = {s[0]: (s[1], s[2]) for s in src_rows}

    # 构建响应列表，填充订阅源名称和文件夹
    articles = []
    for r in rows:
        a = ArticleResponse.model_validate(r)
        info = source_map.get(r.source_id, (None, None))
        a.source_name = info[0]
        a.source_folder = info[1]
        articles.append(a)

    return ArticleListResponse(
        articles=articles if articles else [], total=total or 0, page=page, page_size=page_size
    )


@router.get("/search", response_model=list[ArticleResponse])
async def search_articles(
    q: str = Query(default="", min_length=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    本地文章全文搜索——GET /api/v1/articles/search

    使用 SQLite FTS5 全文搜索引擎进行中文分词搜索。
    搜索字段包括标题和正文内容。

    参数:
        q: 搜索关键词（必填，长度 >= 1）
        page_size: 返回结果数量上限（1-100）

    返回:
        list[ArticleResponse]: 按相关性排序的文章列表
    """
    # 转义双引号（FTS5 语法中双引号是特殊字符）
    escaped = q.replace('"', '""')
    # FTS5 MATCH 查询：按 BM25 排名返回匹配行
    fts_q = 'SELECT rowid FROM article_fts WHERE article_fts MATCH ? ORDER BY rank LIMIT ?'
    try:
        raw = await db.exec_driver_sql(fts_q, (f'"{escaped}"', page_size))
    except AttributeError:
        # SQLAlchemy 版本兼容：部分版本需要先获取 connection
        conn = await db.connection()
        raw = await conn.exec_driver_sql(fts_q, (f'"{escaped}"', page_size))
    ids = [row[0] for row in raw.fetchall()]

    # 没有匹配结果，直接返回空列表
    if not ids:
        return []

    # 根据 FTS 返回的 ID 列表查询文章详情
    rows = (await db.execute(
        select(Article).where(Article.id.in_(ids))
    )).scalars().all()

    # 批量获取订阅源信息
    source_ids = {r.source_id for r in rows}
    source_map: dict[int, tuple] = {}
    if source_ids:
        src_rows = (await db.execute(
            select(Source.id, Source.name, Source.folder).where(Source.id.in_(source_ids))
        )).all()
        source_map = {s[0]: (s[1], s[2]) for s in src_rows}

    # 构建响应列表
    articles = []
    for r in rows:
        a = ArticleResponse.model_validate(r)
        info = source_map.get(r.source_id, (None, None))
        a.source_name = info[0]
        a.source_folder = info[1]
        articles.append(a)

    # 按 FTS 搜索结果的相关性顺序排列
    articles.sort(key=lambda x: ids.index(x.id) if x.id in ids else 9999)
    return articles


@router.get("/{article_id}/aggregated", response_model=AggregatedResponse)
async def get_aggregated_article(
    article_id: int,
    limit: int = Query(default=4, ge=1, le=8),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    多源聚合对比——GET /api/v1/articles/{article_id}/aggregated

    查找来自不同订阅源但报道同一话题的相关文章，提供多角度新闻视角。

    参数:
        article_id: 主文章 ID
        limit: 返回的相关文章数量上限（1-8，默认 4）

    返回:
        AggregatedResponse: 包含主文章、相关来源列表、共同点和不同点
    """
    result = await find_related_from_other_sources(article_id, db, limit=limit)

    if result["main_article"] is None:
        return {
            "code": 404,
            "data": None,
            "message": "找不到这篇文章呢～",
        }

    # 构建主文章响应
    main = result["main_article"]
    main_article = {
        "id": main.id,
        "source_id": main.source_id,
        "title": main.title,
        "url": main.url,
        "content": main.content,
        "summary": main.summary,
        "author": main.author,
        "published_at": main.published_at.isoformat() if main.published_at else None,
        "fetched_at": main.fetched_at.isoformat() if main.fetched_at else None,
        "image_url": main.image_url,
        "is_read": main.is_read,
        "is_favorite": main.is_favorite,
        "is_later": main.is_later,
        "read_progress": main.read_progress,
        "tags": main.tags or [],
        "deep_summary": main.deep_summary,
        "source_name": getattr(main, "source_name", None),
        "source_folder": getattr(main, "source_folder", None),
    }

    return {
        "code": 200,
        "data": {
            "main_article": main_article,
            "related_sources": result["related_sources"],
            "common_points": result["common_points"],
            "different_points": result["different_points"],
        },
        "message": f"ok, 找到 {len(result['related_sources'])} 篇相关报道" if result["related_sources"] else "暂无其他来源的相关报道",
    }


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    获取单篇文章详情——GET /api/v1/articles/{article_id}

    参数:
        article_id: 文章 ID

    返回:
        ArticleResponse: 文章详情（含订阅源信息）

    异常:
        HTTPException(404): 文章不存在
    """
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到这篇文章呢～")

    # 获取关联订阅源信息
    src_row = (await db.execute(
        select(Source.name, Source.folder).where(Source.id == article.source_id)
    )).one_or_none()

    a = ArticleResponse.model_validate(article)
    if src_row:
        a.source_name = src_row[0]
        a.source_folder = src_row[1]
    return a


@router.patch("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: int,
    data: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    更新文章状态——PATCH /api/v1/articles/{article_id}

    支持部分更新：只需在请求体中传入需要修改的字段即可。

    参数:
        article_id: 文章 ID
        data: 要更新的字段（ArticleUpdate schema，所有字段可选）

    返回:
        ArticleResponse: 更新后的文章详情

    异常:
        HTTPException(404): 文章不存在
    """
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到这篇文章呢～")

    # 将请求中的非空字段更新到文章对象上
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(article, key, val)
    await db.flush()
    await db.refresh(article)

    # 获取关联订阅源信息
    src_row = (await db.execute(
        select(Source.name, Source.folder).where(Source.id == article.source_id)
    )).one_or_none()

    a = ArticleResponse.model_validate(article)
    if src_row:
        a.source_name = src_row[0]
        a.source_folder = src_row[1]
    return a
