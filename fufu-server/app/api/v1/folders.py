"""
fufu新闻 - 收藏夹文件夹接口
===============================
提供收藏夹文件夹相关的 REST API 端点：
- GET  /folders                              → 获取当前用户的所有文件夹列表
- POST /folders                              → 创建新文件夹
- PATCH /folders/{id}                        → 更新文件夹信息
- DELETE /folders/{id}                       → 删除文件夹（文章保留，只是取消分类）
- POST /folders/{folder_id}/articles/{article_id}    → 添加文章到文件夹
- DELETE /folders/{folder_id}/articles/{article_id}  → 从文件夹移除文章
- GET  /folders/{folder_id}/articles         → 获取文件夹内的文章列表
- POST /folders/move                         → 移动文章到另一个文件夹
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.models.user import User
from app.models.article import Article
from app.models.favorite import FavoriteFolder, FavoriteFolderItem
from app.models.source import Source
from app.schemas.folder import (
    FolderCreate, FolderUpdate, FolderResponse,
    FolderListResponse, FolderArticlesResponse, MoveArticleRequest,
)
from app.api.deps import get_current_user
import logging

logger = logging.getLogger("fufu.folders")

router = APIRouter(tags=["收藏夹文件夹"])


def _folder_to_response(folder: FavoriteFolder, article_count: int = 0) -> FolderResponse:
    """将 ORM 文件夹对象转换为响应模型"""
    return FolderResponse(
        id=folder.id,
        user_id=folder.user_id,
        name=folder.name,
        icon=folder.icon,
        is_public=folder.is_public,
        sort_order=folder.sort_order,
        article_count=article_count,
        created_at=folder.created_at,
    )


def _article_to_dict(article: Article, source_map: dict) -> dict:
    """将 ORM 文章对象转换为字典（兼容 ArticleResponse 结构）"""
    info = source_map.get(article.source_id, (None, None))
    return {
        "id": article.id,
        "source_id": article.source_id,
        "title": article.title,
        "url": article.url,
        "content": article.content,
        "summary": article.summary,
        "author": article.author,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "fetched_at": article.fetched_at.isoformat() if article.fetched_at else None,
        "image_url": article.image_url,
        "is_read": article.is_read,
        "is_favorite": article.is_favorite,
        "is_later": article.is_later,
        "read_progress": article.read_progress,
        "tags": article.tags or [],
        "source_name": info[0],
        "source_folder": info[1],
    }


# ========== 文件夹列表 ==========
@router.get("/folders", response_model=dict)
async def list_folders(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    获取当前用户的所有收藏夹文件夹——GET /api/v1/folders

    返回:
        dict: { code: 200, data: [{ id, name, icon, is_public, article_count, created_at }], message: "ok" }
    """
    # 查询用户的所有文件夹，按 sort_order 和创建时间排序
    result = await db.execute(
        select(FavoriteFolder)
        .where(FavoriteFolder.user_id == user.id)
        .order_by(FavoriteFolder.sort_order, FavoriteFolder.created_at)
    )
    folders = result.scalars().all()

    # 批量统计每个文件夹内的文章数
    folder_ids = [f.id for f in folders]
    count_map: dict[int, int] = {}
    if folder_ids:
        count_result = await db.execute(
            select(
                FavoriteFolderItem.folder_id,
                func.count(FavoriteFolderItem.id).label("cnt")
            )
            .where(FavoriteFolderItem.folder_id.in_(folder_ids))
            .group_by(FavoriteFolderItem.folder_id)
        )
        count_map = {row[0]: row[1] for row in count_result.all()}

    data = [
        _folder_to_response(f, count_map.get(f.id, 0))
        for f in folders
    ]

    return {"code": 200, "data": data, "message": "ok"}


# ========== 创建文件夹 ==========
@router.post("/folders", response_model=dict)
async def create_folder(
    body: FolderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    创建新的收藏夹文件夹——POST /api/v1/folders

    请求体:
        { name: "科技收藏", icon: "💻", is_public: false }

    返回:
        dict: { code: 200, data: { ...folder... }, message: "ok" }
    """
    # 检查同名文件夹是否已存在
    existing = await db.execute(
        select(FavoriteFolder).where(
            FavoriteFolder.user_id == user.id,
            FavoriteFolder.name == body.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同名文件夹已经存在啦～换个名字试试？"
        )

    folder = FavoriteFolder(
        user_id=user.id,
        name=body.name,
        icon=body.icon,
        is_public=body.is_public,
    )
    db.add(folder)
    await db.flush()
    await db.refresh(folder)

    logger.info(f"用户 {user.username} 创建了文件夹: {folder.name}")

    return {
        "code": 200,
        "data": _folder_to_response(folder, 0),
        "message": "文件夹创建成功啦～"
    }


# ========== 更新文件夹 ==========
@router.patch("/folders/{folder_id}", response_model=dict)
async def update_folder(
    folder_id: int,
    body: FolderUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    更新收藏夹文件夹——PATCH /api/v1/folders/{folder_id}

    请求体（所有字段可选）:
        { name: "新名称", icon: "🎨", is_public: true, sort_order: 1 }

    返回:
        dict: { code: 200, data: { ...folder... }, message: "ok" }
    """
    result = await db.execute(
        select(FavoriteFolder).where(
            FavoriteFolder.id == folder_id,
            FavoriteFolder.user_id == user.id,
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到这个文件夹呢～"
        )

    # 如果要改名，检查同名冲突
    if body.name is not None and body.name != folder.name:
        existing = await db.execute(
            select(FavoriteFolder).where(
                FavoriteFolder.user_id == user.id,
                FavoriteFolder.name == body.name,
                FavoriteFolder.id != folder_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="同名文件夹已经存在啦～换个名字试试？"
            )
        folder.name = body.name

    if body.icon is not None:
        folder.icon = body.icon
    if body.is_public is not None:
        folder.is_public = body.is_public
    if body.sort_order is not None:
        folder.sort_order = body.sort_order

    await db.flush()
    await db.refresh(folder)

    # 重新统计文章数
    count_result = await db.execute(
        select(func.count(FavoriteFolderItem.id))
        .where(FavoriteFolderItem.folder_id == folder.id)
    )
    article_count = count_result.scalar() or 0

    return {
        "code": 200,
        "data": _folder_to_response(folder, article_count),
        "message": "文件夹更新成功啦～"
    }


# ========== 删除文件夹 ==========
@router.delete("/folders/{folder_id}", response_model=dict)
async def delete_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    删除收藏夹文件夹——DELETE /api/v1/folders/{folder_id}

    注意：删除文件夹不会删除文章，只是取消分类关系。
    文章本身的 is_favorite 状态保持不变。

    返回:
        dict: { code: 200, data: {...}, message: "ok" }
    """
    result = await db.execute(
        select(FavoriteFolder).where(
            FavoriteFolder.id == folder_id,
            FavoriteFolder.user_id == user.id,
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到这个文件夹呢～"
        )

    folder_name = folder.name
    await db.delete(folder)
    await db.flush()

    logger.info(f"用户 {user.username} 删除了文件夹: {folder_name}")

    return {
        "code": 200,
        "data": None,
        "message": f"文件夹「{folder_name}」已删除，文章都还在收藏里哦～"
    }


# ========== 添加文章到文件夹 ==========
@router.post("/folders/{folder_id}/articles/{article_id}", response_model=dict)
async def add_article_to_folder(
    folder_id: int,
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    添加文章到收藏夹文件夹——POST /api/v1/folders/{folder_id}/articles/{article_id}

    会同时将文章的 is_favorite 设置为 true。

    返回:
        dict: { code: 200, data: None, message: "ok" }
    """
    # 验证文件夹归属
    folder_result = await db.execute(
        select(FavoriteFolder).where(
            FavoriteFolder.id == folder_id,
            FavoriteFolder.user_id == user.id,
        )
    )
    folder = folder_result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到这个文件夹呢～"
        )

    # 验证文章存在
    article_result = await db.execute(
        select(Article).where(Article.id == article_id)
    )
    article = article_result.scalar_one_or_none()
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到这篇文章呢～"
        )

    # 检查是否已经在文件夹中
    existing = await db.execute(
        select(FavoriteFolderItem).where(
            FavoriteFolderItem.folder_id == folder_id,
            FavoriteFolderItem.article_id == article_id,
        )
    )
    if existing.scalar_one_or_none():
        return {
            "code": 200,
            "data": None,
            "message": "文章已经在这个文件夹里啦～"
        }

    # 添加关联
    item = FavoriteFolderItem(folder_id=folder_id, article_id=article_id)
    db.add(item)

    # 标记文章为收藏
    if not article.is_favorite:
        article.is_favorite = True

    await db.flush()

    return {
        "code": 200,
        "data": None,
        "message": "文章已添加到文件夹啦～"
    }


# ========== 从文件夹移除文章 ==========
@router.delete("/folders/{folder_id}/articles/{article_id}", response_model=dict)
async def remove_article_from_folder(
    folder_id: int,
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    从收藏夹文件夹移除文章——DELETE /api/v1/folders/{folder_id}/articles/{article_id}

    注意：只是移除分类关系，文章的 is_favorite 状态保持不变。

    返回:
        dict: { code: 200, data: None, message: "ok" }
    """
    # 验证文件夹归属
    folder_result = await db.execute(
        select(FavoriteFolder).where(
            FavoriteFolder.id == folder_id,
            FavoriteFolder.user_id == user.id,
        )
    )
    folder = folder_result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到这个文件夹呢～"
        )

    # 查找并删除关联
    item_result = await db.execute(
        select(FavoriteFolderItem).where(
            FavoriteFolderItem.folder_id == folder_id,
            FavoriteFolderItem.article_id == article_id,
        )
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="这个文件夹里没有这篇文章呢～"
        )

    await db.delete(item)
    await db.flush()

    return {
        "code": 200,
        "data": None,
        "message": "文章已从文件夹移除啦～"
    }


# ========== 获取文件夹内文章列表 ==========
@router.get("/folders/{folder_id}/articles", response_model=dict)
async def list_folder_articles(
    folder_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    获取文件夹内的文章列表——GET /api/v1/folders/{folder_id}/articles?page=1&page_size=20

    返回:
        dict: { code: 200, data: { items: [...articles...], total, page, page_size }, message: "ok" }
    """
    # 验证文件夹归属
    folder_result = await db.execute(
        select(FavoriteFolder).where(
            FavoriteFolder.id == folder_id,
            FavoriteFolder.user_id == user.id,
        )
    )
    folder = folder_result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到这个文件夹呢～"
        )

    # 查询文件夹关联的文章 ID（按添加时间倒序）
    items_subq = (
        select(FavoriteFolderItem.article_id, FavoriteFolderItem.added_at)
        .where(FavoriteFolderItem.folder_id == folder_id)
        .subquery()
    )

    # 计算总数
    count_result = await db.execute(
        select(func.count()).select_from(items_subq)
    )
    total = count_result.scalar() or 0

    # 分页查询文章
    offset = (page - 1) * page_size
    article_rows = await db.execute(
        select(Article)
        .join(items_subq, Article.id == items_subq.c.article_id)
        .order_by(items_subq.c.added_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    articles = article_rows.scalars().all()

    # 批量获取订阅源信息
    source_ids = {a.source_id for a in articles}
    source_map: dict[int, tuple] = {}
    if source_ids:
        src_rows = await db.execute(
            select(Source.id, Source.name, Source.folder).where(Source.id.in_(source_ids))
        )
        source_map = {s[0]: (s[1], s[2]) for s in src_rows.all()}

    items = [_article_to_dict(a, source_map) for a in articles]

    return {
        "code": 200,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        "message": "ok" if items else "这个文件夹还是空的呢～",
    }


# ========== 移动文章到另一个文件夹 ==========
@router.post("/folders/move", response_model=dict)
async def move_article(
    body: MoveArticleRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    移动文章从一个文件夹到另一个——POST /api/v1/folders/move

    请求体:
        { article_id, from_folder_id, to_folder_id }

    返回:
        dict: { code: 200, data: None, message: "ok" }
    """
    # 验证两个文件夹都属于当前用户
    folders_result = await db.execute(
        select(FavoriteFolder).where(
            FavoriteFolder.id.in_([body.from_folder_id, body.to_folder_id]),
            FavoriteFolder.user_id == user.id,
        )
    )
    folders = folders_result.scalars().all()
    folder_ids = {f.id for f in folders}

    if body.from_folder_id not in folder_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到源文件夹呢～"
        )
    if body.to_folder_id not in folder_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到目标文件夹呢～"
        )

    # 查找源文件夹中的文章关联
    item_result = await db.execute(
        select(FavoriteFolderItem).where(
            FavoriteFolderItem.folder_id == body.from_folder_id,
            FavoriteFolderItem.article_id == body.article_id,
        )
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="源文件夹中没有这篇文章呢～"
        )

    # 删除旧关联
    await db.delete(item)

    # 检查目标文件夹是否已有此文章
    existing = await db.execute(
        select(FavoriteFolderItem).where(
            FavoriteFolderItem.folder_id == body.to_folder_id,
            FavoriteFolderItem.article_id == body.article_id,
        )
    )
    if not existing.scalar_one_or_none():
        # 添加新关联
        new_item = FavoriteFolderItem(
            folder_id=body.to_folder_id,
            article_id=body.article_id,
        )
        db.add(new_item)

    await db.flush()

    return {
        "code": 200,
        "data": None,
        "message": "文章移动成功啦～"
    }
