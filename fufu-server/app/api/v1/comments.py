"""
fufu新闻 - 评论接口
=======================
提供评论相关的 REST API 端点：
- GET  /articles/{article_id}/comments        → 获取评论列表（分页、排序）
- POST /articles/{article_id}/comments        → 创建顶级评论
- POST /comments/{comment_id}/reply           → 回复评论
- DELETE /comments/{comment_id}               → 软删除自己的评论
- POST /comments/{comment_id}/like            → 点赞/取消点赞
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.core.database import get_db
from app.models.article import Article
from app.models.comment import ArticleComment, CommentLike
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentItem, CommentReply
from app.schemas.response import error, success
from app.services.stats import bump_comment_count

logger = logging.getLogger("fufu.comments")

router = APIRouter(tags=["评论"])


async def _build_comment_item(
    db: AsyncSession,
    comment: ArticleComment,
    user_map: dict[int, str],
    liked_comment_ids: set[int],
) -> CommentItem:
    """构建单条评论的响应模型（不含 replies）"""
    return CommentItem(
        id=comment.id,
        content=comment.content,
        username=user_map.get(comment.user_id, "未知用户"),
        created_at=comment.created_at,
        likes_count=comment.likes_count or 0,
        is_liked=comment.id in liked_comment_ids,
        replies=[],
    )


@router.get("/articles/{article_id}/comments")
async def list_comments(
    article_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="latest", pattern=r"^(latest|hot)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """
    获取文章评论列表——GET /api/v1/articles/{article_id}/comments

    返回两级嵌套评论（顶级评论 + 一级回复）。
    支持按最新或最热排序，支持分页。

    参数:
        article_id: 文章 ID
        page: 页码（从 1 开始）
        page_size: 每页条数（1-100）
        sort: 排序方式（"latest" 按时间降序 / "hot" 按点赞数降序）

    返回:
        dict: 包含分页后的评论列表和元信息
    """
    # 验证文章存在
    article = (await db.execute(
        select(Article).where(Article.id == article_id)
    )).scalar_one_or_none()
    if not article:
        return error(code=404, message="找不到这篇文章呢～")

    user_id = current_user.id if current_user else None

    # 查询顶级评论总数
    count_q = select(func.count()).select_from(
        select(ArticleComment).where(
            and_(ArticleComment.article_id == article_id, ArticleComment.parent_id == None)
        ).subquery()
    )
    total = (await db.execute(count_q)).scalar() or 0

    # 排序方式
    order_col = ArticleComment.likes_count.desc() if sort == "hot" else ArticleComment.created_at.desc()

    # 查询当前页的顶级评论
    offset = (page - 1) * page_size
    top_rows = (await db.execute(
        select(ArticleComment)
        .where(and_(ArticleComment.article_id == article_id, ArticleComment.parent_id == None))
        .order_by(order_col)
        .offset(offset)
        .limit(page_size)
    )).scalars().all()

    if not top_rows:
        return success({
            "items": [],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    # 收集所有顶级评论 ID
    top_ids = [c.id for c in top_rows]

    # 批量查询所有顶级评论的回复
    replies_rows = (await db.execute(
        select(ArticleComment)
        .where(ArticleComment.parent_id.in_(top_ids))
        .order_by(ArticleComment.created_at.asc())
    )).scalars().all()

    # 按 parent_id 分组回复
    replies_map: dict[int, list[ArticleComment]] = {}
    for r in replies_rows:
        if r.parent_id not in replies_map:
            replies_map[r.parent_id] = []
        replies_map[r.parent_id].append(r)

    # 收集所有涉及的用户 ID（顶级评论 + 回复）
    all_user_ids = set()
    for c in top_rows:
        all_user_ids.add(c.user_id)
    for r in replies_rows:
        all_user_ids.add(r.user_id)

    # 批量查询用户名
    user_map: dict[int, str] = {}
    if all_user_ids:
        # SQLite 兼容：逐个查询
        for uid in all_user_ids:
            u = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
            if u:
                user_map[uid] = u.username

    # 收集所有评论 ID 用于查询点赞状态
    all_comment_ids = set(top_ids)
    for r in replies_rows:
        all_comment_ids.add(r.id)

    # 批量查询当前用户的点赞状态
    liked_comment_ids: set[int] = set()
    if user_id and all_comment_ids:
        likes_rows = (await db.execute(
            select(CommentLike.comment_id).where(
                and_(
                    CommentLike.comment_id.in_(all_comment_ids),
                    CommentLike.user_id == user_id,
                )
            )
        )).scalars().all()
        liked_comment_ids = set(likes_rows)

    # 构建响应
    items = []
    for top in top_rows:
        comment_item = await _build_comment_item(db, top, user_map, liked_comment_ids)
        # 添加回复
        child_comments = replies_map.get(top.id, [])
        for child in child_comments:
            reply_item = await _build_comment_item(db, child, user_map, liked_comment_ids)
            comment_item.replies.append(reply_item)
        items.append(comment_item)

    return success({
        "items": [item.model_dump() for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.post("/articles/{article_id}/comments")
async def create_comment(
    article_id: int,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建顶级评论——POST /api/v1/articles/{article_id}/comments

    参数:
        article_id: 文章 ID
        body: 包含 content 字段的请求体（1-1000 字符）

    返回:
        dict: 新创建的评论数据
    """
    # 验证文章存在
    article = (await db.execute(
        select(Article).where(Article.id == article_id)
    )).scalar_one_or_none()
    if not article:
        return error(code=404, message="找不到这篇文章呢～")

    # 创建评论
    comment = ArticleComment(
        article_id=article_id,
        user_id=current_user.id,
        parent_id=None,
        content=body.content.strip(),
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)

    # 同步评论数到 article_stats —— 让热度公式里 30% 的评论权重真正生效
    await bump_comment_count(db, article_id, +1)

    logger.info(f"用户 {current_user.username} 评论了文章 {article_id} (comment_id={comment.id})")

    return success({
        "id": comment.id,
        "content": comment.content,
        "username": current_user.username,
        "created_at": comment.created_at.isoformat(),
        "likes_count": comment.likes_count,
        "is_liked": False,
        "replies": [],
    }, message="评论发表成功～")


@router.post("/comments/{comment_id}/reply")
async def reply_to_comment(
    comment_id: int,
    body: CommentReply,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    回复评论——POST /api/v1/comments/{comment_id}/reply

    只允许对顶级评论（parent_id IS NULL）进行回复，不支持二级以上的嵌套。

    参数:
        comment_id: 父评论 ID（必须是顶级评论）
        body: 包含 content 字段的请求体（1-500 字符）

    返回:
        dict: 新创建的回复数据
    """
    # 验证父评论存在且为顶级评论
    parent = (await db.execute(
        select(ArticleComment).where(ArticleComment.id == comment_id)
    )).scalar_one_or_none()
    if not parent:
        return error(code=404, message="找不到这条评论呢～")
    if parent.parent_id is not None:
        return error(code=400, message="只能回复顶级评论哦～不可以再嵌套了呢")

    # 验证文章存在
    article = (await db.execute(
        select(Article).where(Article.id == parent.article_id)
    )).scalar_one_or_none()
    if not article:
        return error(code=404, message="找不到这篇文章呢～")

    # 创建回复
    reply = ArticleComment(
        article_id=parent.article_id,
        user_id=current_user.id,
        parent_id=comment_id,
        content=body.content.strip(),
    )
    db.add(reply)
    await db.flush()
    await db.refresh(reply)

    # 回复同样计入评论数
    await bump_comment_count(db, parent.article_id, +1)

    logger.info(f"用户 {current_user.username} 回复了评论 {comment_id} (reply_id={reply.id})")

    return success({
        "id": reply.id,
        "content": reply.content,
        "username": current_user.username,
        "created_at": reply.created_at.isoformat(),
        "likes_count": reply.likes_count,
        "is_liked": False,
        "replies": [],
    }, message="回复发表成功～")


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除评论——DELETE /api/v1/comments/{comment_id}

    软删除：将评论内容替换为"[已删除]"，保留评论结构。
    只有评论作者本人可以删除自己的评论。

    参数:
        comment_id: 要删除的评论 ID

    返回:
        dict: 操作结果
    """
    comment = (await db.execute(
        select(ArticleComment).where(ArticleComment.id == comment_id)
    )).scalar_one_or_none()
    if not comment:
        return error(code=404, message="找不到这条评论呢～")

    if comment.user_id != current_user.id:
        return error(code=403, message="只能删除自己的评论哦～")

    # 软删除。
    # 修复：原先写 `updated_at = None`，注释称"SQLite will use default"，
    # 但显式赋 None 会真的把列写成 NULL，而不是触发默认值。
    # 这里改为显式赋当前时间。
    comment.content = "[已删除]"
    comment.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # 同步评论数（软删除也算减少一条有效评论）
    await bump_comment_count(db, comment.article_id, -1)

    logger.info(f"用户 {current_user.username} 删除了评论 {comment_id}")

    return success(message="评论已删除～")


@router.post("/comments/{comment_id}/like")
async def toggle_like(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    点赞/取消点赞——POST /api/v1/comments/{comment_id}/like

    同一用户对同一评论只能点赞一次，再次调用则取消点赞。
    点赞和取消点赞都会更新 article_comment 的 likes_count 冗余字段。

    参数:
        comment_id: 要点赞的评论 ID

    返回:
        dict: 操作结果（liked 表示当前是否已点赞）
    """
    # 验证评论存在
    comment = (await db.execute(
        select(ArticleComment).where(ArticleComment.id == comment_id)
    )).scalar_one_or_none()
    if not comment:
        return error(code=404, message="找不到这条评论呢～")

    # 检查是否已点赞
    existing = (await db.execute(
        select(CommentLike).where(
            and_(
                CommentLike.comment_id == comment_id,
                CommentLike.user_id == current_user.id,
            )
        )
    )).scalar_one_or_none()

    if existing:
        # 取消点赞
        await db.delete(existing)
        comment.likes_count = max(0, (comment.likes_count or 0) - 1)
        await db.flush()
        logger.info(f"用户 {current_user.username} 取消了对评论 {comment_id} 的点赞")
        return success({"liked": False, "likes_count": comment.likes_count}, message="已取消点赞～")
    else:
        # 点赞
        like = CommentLike(
            comment_id=comment_id,
            user_id=current_user.id,
        )
        db.add(like)
        comment.likes_count = (comment.likes_count or 0) + 1
        await db.flush()
        logger.info(f"用户 {current_user.username} 点赞了评论 {comment_id}")
        return success({"liked": True, "likes_count": comment.likes_count}, message="点赞成功～")
