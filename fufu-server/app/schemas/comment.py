"""
fufu新闻 - 评论 Pydantic Schema
==================================
定义评论相关的请求/响应数据结构（Pydantic 模型）。
"""
from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    """创建顶级评论的请求体"""
    content: str = Field(min_length=1, max_length=1000)


class CommentReply(BaseModel):
    """回复评论的请求体"""
    content: str = Field(min_length=1, max_length=500)


class CommentItem(BaseModel):
    """
    评论条目响应模型。

    字段说明：
    - id: 评论 ID
    - content: 评论内容（被软删除的评论显示为"[已删除]"）
    - username: 评论者用户名
    - created_at: 评论时间
    - likes_count: 点赞数
    - is_liked: 当前用户是否已点赞
    - replies: 子回复列表（最多一层嵌套）
    """
    id: int
    content: str
    username: str
    created_at: datetime
    likes_count: int
    is_liked: bool = False
    replies: list['CommentItem'] = []

    model_config = {"from_attributes": True}


class CommentListResponse(BaseModel):
    """评论列表分页响应模型"""
    items: list[CommentItem]
    total: int
    page: int
    page_size: int
