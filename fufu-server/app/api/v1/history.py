"""
fufu新闻 - 阅读历史接口
===========================
提供阅读历史相关的 REST API 端点：

- GET  /history              → 获取当前用户的阅读历史（分页）
- POST /history/{article_id} → 记录/更新阅读历史
- DELETE /history/{article_id} → 删除单条阅读历史
- DELETE /history            → 清空当前用户全部阅读历史
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.article import Article
from app.models.history import ReadHistory
from app.models.source import Source
from app.models.user import User
from app.schemas.history import HistoryItem, ReadHistoryRecord
from app.schemas.response import error, success
from app.services.learning import record_feedback

logger = logging.getLogger("fufu.history")

router = APIRouter(tags=["阅读历史"])


@router.get("")
async def list_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    获取当前用户的阅读历史——GET /api/v1/history

    按 read_at 降序排列，支持分页。

    参数:
        page: 页码（从 1 开始）
        page_size: 每页条数（1-100）

    返回:
        dict: {"code": 200, "data": HistoryListResponse, "message": "ok"}
    """
    try:
        # 计算总数
        count_q = (
            select(func.count())
            .select_from(ReadHistory)
            .where(ReadHistory.user_id == user.id)
        )
        total = (await db.execute(count_q)).scalar() or 0

        # 分页查询阅读历史，关联文章和订阅源信息
        offset = (page - 1) * page_size
        history_query = (
            select(
                ReadHistory.article_id,
                ReadHistory.read_at,
                ReadHistory.read_duration,
                Article.title,
                Article.image_url,
                Article.published_at,
                Source.name.label("source_name"),
            )
            .select_from(ReadHistory)
            .join(Article, ReadHistory.article_id == Article.id)
            .outerjoin(Source, Article.source_id == Source.id)
            .where(ReadHistory.user_id == user.id)
            .order_by(ReadHistory.read_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(history_query)
        rows = result.all()

        # 构建响应
        items = []
        for row in rows:
            items.append(HistoryItem(
                article_id=row.article_id,
                title=row.title or "",
                source_name=row.source_name,
                image_url=row.image_url,
                published_at=row.published_at,
                read_at=row.read_at,
                read_duration=row.read_duration or 0,
            ))

        return success(data={
            "items": [item.model_dump() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    except Exception as e:
        logger.error(f"获取阅读历史失败: {e}", exc_info=True)
        return error(code=500, message="获取阅读历史失败，请稍后再试～")


@router.post("/{article_id}")
async def record_history(
    article_id: int,
    body: ReadHistoryRecord = ReadHistoryRecord(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    记录或更新阅读历史——POST /api/v1/history/{article_id}

    如果该用户已阅读过此文章，则更新 read_at 和 read_duration；
    否则创建新的阅读历史记录。
    同时将该文章标记为已读。

    参数:
        article_id: 文章 ID
        body: 请求体，包含可选的 read_duration（阅读时长，秒）

    返回:
        dict: {"code": 200, "data": {...}, "message": "ok"}
    """
    try:
        # 检查文章是否存在
        article_result = await db.execute(
            select(Article).where(Article.id == article_id)
        )
        article = article_result.scalar_one_or_none()
        if not article:
            return error(code=404, message="找不到这篇文章呢～")

        # 查找已有的阅读历史记录
        existing_result = await db.execute(
            select(ReadHistory).where(
                ReadHistory.user_id == user.id,
                ReadHistory.article_id == article_id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        duration = body.read_duration or 0

        if existing:
            # 更新已有记录
            existing.read_at = now
            if body.read_duration is not None and body.read_duration > 0:
                existing.read_duration += body.read_duration
            action = "updated"
            logger.info(f"更新阅读历史: user_id={user.id}, article_id={article_id}, duration={existing.read_duration}")
        else:
            # 创建新记录
            new_history = ReadHistory(
                user_id=user.id,
                article_id=article_id,
                read_at=now,
                read_duration=duration,
            )
            db.add(new_history)
            action = "created"
            logger.info(f"创建阅读历史: user_id={user.id}, article_id={article_id}")

        # 标记文章为已读
        if not article.is_read:
            article.is_read = True

        # 自学习反馈回流：把本次阅读时长 + 收藏状态 + 文章标签喂给兴趣画像，
        # 让推荐引擎随使用逐步学会用户偏好（失败静默，不影响主流程）。
        await record_feedback(
            db,
            user.id,
            article.tags or [],
            read_duration=duration,
            is_favorite=bool(article.is_favorite),
        )

        await db.flush()

        return success(data={
            "recorded": True,
            "action": action,
            "message": "阅读历史已记录～",
        })

    except Exception as e:
        logger.error(f"记录阅读历史失败: {e}", exc_info=True)
        return error(code=500, message="记录阅读历史失败，请稍后再试～")


@router.delete("/{article_id}")
async def delete_history_item(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    删除单条阅读历史——DELETE /api/v1/history/{article_id}

    参数:
        article_id: 文章 ID

    返回:
        dict: {"code": 200, "data": {...}, "message": "ok"}
    """
    try:
        result = await db.execute(
            delete(ReadHistory).where(
                ReadHistory.user_id == user.id,
                ReadHistory.article_id == article_id,
            )
        )
        await db.flush()

        if result.rowcount == 0:
            return error(code=404, message="找不到这条阅读记录呢～")

        logger.info(f"删除阅读历史: user_id={user.id}, article_id={article_id}")
        return success(data={"deleted": True}, message="阅读记录已删除～")

    except Exception as e:
        logger.error(f"删除阅读历史失败: {e}", exc_info=True)
        return error(code=500, message="删除阅读历史失败，请稍后再试～")


@router.delete("")
async def clear_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    清空当前用户全部阅读历史——DELETE /api/v1/history

    返回:
        dict: {"code": 200, "data": {...}, "message": "ok"}
    """
    try:
        result = await db.execute(
            delete(ReadHistory).where(ReadHistory.user_id == user.id)
        )
        await db.flush()

        deleted_count = result.rowcount
        logger.info(f"清空阅读历史: user_id={user.id}, 删除 {deleted_count} 条")
        return success(data={"deleted": True, "count": deleted_count}, message="阅读历史已清空～")

    except Exception as e:
        logger.error(f"清空阅读历史失败: {e}", exc_info=True)
        return error(code=500, message="清空阅读历史失败，请稍后再试～")
