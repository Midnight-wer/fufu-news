"""
fufu新闻 - 订阅源接口
=========================
提供订阅源相关的 REST API 端点：
- GET    /sources           → 获取所有订阅源列表
- POST   /sources           → 创建新订阅源
- GET    /sources/{id}      → 获取单个订阅源详情
- PATCH  /sources/{id}      → 更新订阅源信息
- DELETE /sources/{id}      → 删除订阅源
- POST   /sources/{id}/fetch → 手动触发单个源抓取
- POST   /sources/fetch-all  → 手动触发全量抓取
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.database import get_db
from app.models.source import Source
from app.models.user import User
from app.schemas.source import SourceCreate, SourceUpdate, SourceResponse
from app.api.deps import get_current_user

# 创建订阅源路由实例
router = APIRouter(tags=["订阅源"])


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    获取所有订阅源列表——GET /api/v1/sources

    返回按创建时间降序排列的所有订阅源。
    需要认证。

    返回:
        list[SourceResponse]: 订阅源列表
    """
    result = await db.execute(select(Source).order_by(Source.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    data: SourceCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    创建新订阅源——POST /api/v1/sources

    参数:
        data: 订阅源创建请求体（SourceCreate schema）

    返回:
        SourceResponse: 创建成功的订阅源详情

    异常:
        HTTPException(409): 该 URL 的订阅源已存在
    """
    # 检查是否已存在相同 URL 的源
    existing = await db.execute(select(Source).where(Source.url == data.url))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="这个订阅源已经添加过了哦～"
        )

    # 创建新源
    source = Source(**data.model_dump())
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    获取单个订阅源详情——GET /api/v1/sources/{source_id}

    参数:
        source_id: 订阅源 ID

    返回:
        SourceResponse: 订阅源详情

    异常:
        HTTPException(404): 订阅源不存在
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到这个订阅源呢～")
    return source


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    data: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    更新订阅源信息——PATCH /api/v1/sources/{source_id}

    支持部分更新，只传需要修改的字段。

    参数:
        source_id: 订阅源 ID
        data: 要更新的字段（SourceUpdate schema，所有字段可选）

    返回:
        SourceResponse: 更新后的订阅源详情

    异常:
        HTTPException(404): 订阅源不存在
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到这个订阅源呢～")

    # 将请求中的非空字段更新到订阅源对象上
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(source, key, val)
    await db.flush()
    await db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    删除订阅源——DELETE /api/v1/sources/{source_id}

    删除订阅源时，关联的文章也会因外键级联删除而被清理。

    参数:
        source_id: 订阅源 ID

    返回:
        204 No Content（成功删除无返回体）

    异常:
        HTTPException(404): 订阅源不存在
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到这个订阅源呢～")
    await db.execute(delete(Source).where(Source.id == source_id))
    await db.flush()


@router.post("/{source_id}/fetch")
async def trigger_fetch(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    手动触发单个订阅源抓取——POST /api/v1/sources/{source_id}/fetch

    立即对指定的订阅源执行一次 RSS 抓取并入库新文章。

    参数:
        source_id: 订阅源 ID

    返回:
        dict: {"status": 抓取状态, "new_articles": 新增文章数, "error": 错误信息}

    异常:
        HTTPException(404): 订阅源不存在
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到这个订阅源呢～")

    from app.services.fetcher import fetch_source
    log = await fetch_source(source)
    return {
        "status": log.status,
        "new_articles": log.new_articles_count,
        "error": log.error_msg
    }


@router.post("/fetch-all")
async def trigger_fetch_all(
    _user: User = Depends(get_current_user),
):
    """
    全量爬取所有订阅源——POST /api/v1/sources/fetch-all

    立即对所有活跃的订阅源执行一次全量抓取。

    返回:
        dict: {"message": 结果描述, "success": 成功数, "fail": 失败数}
    """
    from app.core.database import fetch_all_sources
    result = await fetch_all_sources()
    return {"message": f"全量爬取完成: 成功 {result['success']}, 失败 {result['fail']}", **result}
