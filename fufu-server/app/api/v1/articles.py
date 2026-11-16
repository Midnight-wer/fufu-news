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
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.categories import CATEGORY_KEYWORDS
from app.core.database import get_db
from app.models.article import Article
from app.models.poll import POLL_OPTIONS, ArticlePoll
from app.models.source import Source
from app.models.user import User
from app.schemas.aggregation import AggregatedResponse
from app.schemas.article import ArticleListResponse, ArticleResponse, ArticleUpdate
from app.schemas.response import success
from app.services.aggregator import find_related_from_other_sources
from app.services.search import search_ddgs
from app.services.stats import sync_collect_count

# 创建文章路由实例
router = APIRouter(tags=["文章"])

logger = logging.getLogger("fufu.api.articles")




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


@router.get("/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    各分类的文章数量——GET /api/v1/articles/categories

    前端分类按钮上挂着"该分类有几篇"的小徽标。之前这个数字是在
    **当前这一页**的 20 条里数出来的，翻到第 2 页数字就变了，
    看起来像随机跳动的假数据。这里改成一次 SQL 聚合出全库真实数量。

    注意顺序：`/categories` 必须定义在 `/{article_id}` 之前，
    否则会被当成 article_id="categories" 吃掉。
    """
    total = (await db.execute(select(func.count()).select_from(Article))).scalar() or 0

    cases = []
    for name, keywords in CATEGORY_KEYWORDS.items():
        cases.append(
            func.sum(
                case((or_(*_category_conditions(keywords)), 1), else_=0)
            ).label(name)
        )

    row = (await db.execute(
        select(*cases).select_from(Article).join(
            Source, Source.id == Article.source_id, isouter=True
        )
    )).first()

    counts: dict[str, int] = {"all": int(total)}
    for i, name in enumerate(CATEGORY_KEYWORDS):
        counts[name] = int(row[i] or 0) if row else 0

    return success(counts)


def _category_conditions(keywords: list[str]):
    """
    把分类关键词列表翻译成 SQL 条件。

    分类命中两个来源：
      - 订阅源的 folder（Source.folder）
      - 文章自己的 AI 标签（Article.tags，JSON 数组，SQLite 里以文本存储）

    tags 用 LIKE '%"关键词"%' 匹配，是因为 JSON 列在 SQLite 中没有原生
    数组包含操作符；JSON 序列化后形如 ["动漫", "科技"]，带引号的模糊匹配
    可以避免「科技」误命中「科技圈」之外的子串问题（引号天然做了边界）。
    """
    conds = []
    for kw in keywords:
        conds.append(Source.folder == kw)
        conds.append(cast(Article.tags, String).like(f'%"{kw}"%'))
    return conds


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
    category: str | None = Query(default=None, max_length=50),
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
        category: 分类筛选（单个分类名，如 动漫/游戏/科技/设计/综合）

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

    # 分类筛选：需要 join 订阅源才能拿到 folder
    if category:
        keywords = CATEGORY_KEYWORDS.get(category)
        if not keywords:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的分类：{category}",
            )
        q = q.join(Source, Source.id == Article.source_id, isouter=True)
        q = q.where(or_(*_category_conditions(keywords)))

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
    changed = data.model_dump(exclude_unset=True)
    for key, val in changed.items():
        setattr(article, key, val)
    await db.flush()
    await db.refresh(article)

    # 收藏状态变化时同步收藏数。
    # 修复：article_stats.collect_count 此前只在创建统计行瞬间赋值一次，
    # 之后收藏/取消收藏都不更新，导致排行榜 ⭐ 收藏数永远失真、
    # 热度公式里 10% 的收藏权重形同虚设。
    if "is_favorite" in changed:
        await sync_collect_count(db, article.id, bool(changed["is_favorite"]))

    logger.debug(
        f"文章 {article_id} 状态更新: {', '.join(changed.keys()) or '无字段'}"
    )

    a = ArticleResponse.model_validate(article)

    # 补上订阅源名称：PATCH 的返回体也要带 source_name，
    # 否则前端更新单篇缓存后卡片上的来源标签会瞬间变空。
    # （这里曾经漏了查询直接引用 src_row，导致每个 PATCH 都 NameError → 500）
    src_row = (await db.execute(
        select(Source.name, Source.folder).where(Source.id == article.source_id)
    )).first()
    if src_row:
        a.source_name = src_row[0]
        a.source_folder = src_row[1]
    return a


# ========== 文章立场投票 ==========


@router.get("/{article_id}/poll")
async def get_article_poll(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取文章立场投票统计——GET /api/v1/articles/{id}/poll

    原先这个「你怎么看？」投票是纯前端 localStorage 假数据：
    换设备即丢失，且统计时没有按文章过滤（在第 5 篇投票，第 100 篇也会显示
    "已有 1 人参与"）。现在改为真实落库统计。

    返回:
        data = { support, oppose, neutral, total, my_vote }
    """
    rows = (await db.execute(
        select(ArticlePoll.option, func.count(ArticlePoll.id))
        .where(ArticlePoll.article_id == article_id)
        .group_by(ArticlePoll.option)
    )).all()

    counts = {"support": 0, "oppose": 0, "neutral": 0}
    for option, n in rows:
        if option in counts:
            counts[option] = n

    my_vote = (await db.execute(
        select(ArticlePoll.option).where(
            ArticlePoll.article_id == article_id,
            ArticlePoll.user_id == current_user.id,
        )
    )).scalar_one_or_none()

    return success({
        **counts,
        "total": sum(counts.values()),
        "my_vote": my_vote,
    })


class PollVoteRequest(BaseModel):
    """投票请求体。option 为 support / oppose / neutral，传 null 表示撤票。"""
    option: str | None


@router.post("/{article_id}/poll")
async def vote_article_poll(
    article_id: int,
    body: PollVoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    提交/修改文章立场投票——POST /api/v1/articles/{id}/poll

    一人一票（UNIQUE(article_id, user_id)）：重复投票视为改票，
    传 `{"option": null}` 表示撤票。

    异常:
        HTTPException(404): 文章不存在
        HTTPException(400): 选项不合法
    """
    article = (await db.execute(
        select(Article.id).where(Article.id == article_id)
    )).scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail="找不到这篇文章呢～")

    option = body.option
    if option is not None and option not in POLL_OPTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"投票选项不合法，只能是 {list(POLL_OPTIONS)} 之一",
        )

    existing = (await db.execute(
        select(ArticlePoll).where(
            ArticlePoll.article_id == article_id,
            ArticlePoll.user_id == current_user.id,
        )
    )).scalar_one_or_none()

    if option is None:
        # 撤票
        if existing:
            await db.delete(existing)
            logger.info(f"用户 {current_user.username} 撤销了对文章 {article_id} 的投票")
        return success({"voted": False}, message="已撤销投票～")

    if existing:
        existing.option = option
        existing.updated_at = datetime.now(timezone.utc)
        message = "已更新你的立场～"
    else:
        db.add(ArticlePoll(
            article_id=article_id,
            user_id=current_user.id,
            option=option,
        ))
        message = "投票成功，谢谢你的一票～"

    await db.flush()
    logger.info(f"用户 {current_user.username} 对文章 {article_id} 投票: {option}")

    # 返回最新统计，前端无需再发一次 GET
    rows = (await db.execute(
        select(ArticlePoll.option, func.count(ArticlePoll.id))
        .where(ArticlePoll.article_id == article_id)
        .group_by(ArticlePoll.option)
    )).all()
    counts = {"support": 0, "oppose": 0, "neutral": 0}
    for opt, n in rows:
        if opt in counts:
            counts[opt] = n

    return success({
        **counts,
        "total": sum(counts.values()),
        "my_vote": option,
        "voted": True,
    }, message=message)

    # 获取关联订阅源信息
    src_row = (await db.execute(
        select(Source.name, Source.folder).where(Source.id == article.source_id)
    )).one_or_none()

    a = ArticleResponse.model_validate(article)
    if src_row:
        a.source_name = src_row[0]
        a.source_folder = src_row[1]
    return a
