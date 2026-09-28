"""
fufu新闻 - 多源聚合对比 Pydantic Schema
===========================================
定义多源聚合对比 API 的请求/响应数据结构。
"""
from datetime import datetime
from pydantic import BaseModel, Field


class RelatedArticleBrief(BaseModel):
    """相关文章的简要信息（用于聚合对比列表）"""
    id: int
    title: str
    source_id: int
    source_name: str | None = None
    summary: str | None = None
    published_at: str | None = None
    image_url: str | None = None
    url: str = ""
    tags: list[str] = Field(default_factory=list)


class RelatedSourceItem(BaseModel):
    """单个相关来源条目"""
    article: RelatedArticleBrief
    perspective: str = "相关报道"  # 同一事件 / 相关报道 / 补充视角
    overlap_keywords: list[str] = Field(default_factory=list)
    similarity_score: float = 0.0


class AggregatedArticleResponse(BaseModel):
    """
    多源聚合对比响应模型。

    字段说明：
    - main_article: 主文章详情
    - related_sources: 来自其他来源的相关文章列表（含视角分类和相似度）
    - common_points: 多篇报道的共同关注点
    - different_points: 不同来源的视角差异
    """
    main_article: dict | None = None
    related_sources: list[RelatedSourceItem] = Field(default_factory=list)
    common_points: list[str] = Field(default_factory=list)
    different_points: list[str] = Field(default_factory=list)


class AggregatedResponse(BaseModel):
    """
    聚合对比 API 统一响应格式。
    """
    code: int = 200
    data: AggregatedArticleResponse | None = None
    message: str = "ok"
