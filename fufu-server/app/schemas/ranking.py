"""
fufu新闻 - 排行榜 Pydantic Schema
=====================================
定义排行榜相关的请求/响应数据结构（Pydantic 模型）。
"""
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class RankingItem(BaseModel):
    """
    单条排行榜条目。

    字段说明：
    - rank: 排名序号（从 1 开始）
    - article_id: 文章 ID
    - title: 文章标题
    - source_name: 来源订阅源名称
    - image_url: 文章封面图
    - hot_score: 热度分（越大越热）
    - view_count: 浏览数
    - comment_count: 评论数
    - collect_count: 收藏数
    - trend: 趋势标识（"up" / "down" / "same" / "new"）
    - hot_label: 热度标签（"爆" / "热" / "新"）
    """
    rank: int
    article_id: int
    title: str
    source_name: str
    image_url: Optional[str] = None
    hot_score: float
    view_count: int
    comment_count: int
    collect_count: int
    trend: Optional[str] = None
    hot_label: Optional[str] = None


class RankingResponse(BaseModel):
    """
    排行榜响应模型。

    字段说明：
    - items: 排行榜条目列表
    - updated_at: 排行榜更新时间
    """
    items: list[RankingItem]
    updated_at: datetime


class HitResponse(BaseModel):
    """
    点击记录响应模型。

    字段说明：
    - recorded: 是否成功记录（去重时可能返回 False）
    - message: 提示信息
    """
    recorded: bool
    message: str
