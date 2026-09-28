"""
fufu新闻 - 个性化推荐 Pydantic Schema
=====================================
定义推荐系统相关的请求/响应数据结构。
"""
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class RecommendationItem(BaseModel):
    """
    单条推荐条目。

    字段说明：
    - article_id: 文章 ID
    - title: 文章标题
    - source_name: 来源订阅源名称
    - image_url: 文章封面图
    - published_at: 文章发布时间
    - hot_score: 热度分（用于展示热度标签）
    - reason: 推荐理由（"因为你阅读过..." / "热门趋势" / "标签匹配" / "常读来源"）
    - score: 综合推荐分（用于内部排序，前端可忽略）
    - tags: 文章标签列表
    """
    article_id: int
    title: str
    source_name: str = ""
    image_url: Optional[str] = None
    published_at: Optional[datetime] = None
    hot_score: float = 0.0
    reason: str = ""
    score: float = 0.0
    tags: list[str] = []


class PersonalizedResponse(BaseModel):
    """
    个性化推荐响应模型。

    字段说明：
    - items: 推荐条目列表
    - reasons: 以 article_id 为 key 的推荐理由映射（前端可用此展示原因标签）
    """
    items: list[RecommendationItem]
    reasons: dict[int, str] = {}


class SimilarResponse(BaseModel):
    """
    相似文章响应模型。
    """
    items: list[RecommendationItem]
    reasons: dict[int, str] = {}


class TrendingResponse(BaseModel):
    """
    热门趋势响应模型。
    """
    items: list[RecommendationItem]
    reasons: dict[int, str] = {}
