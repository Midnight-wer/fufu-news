"""
fufu新闻 - 阅读历史 Pydantic Schema
=======================================
定义阅读历史相关的请求/响应数据结构（Pydantic 模型）。
"""
from datetime import datetime
from pydantic import BaseModel, Field


class ReadHistoryRecord(BaseModel):
    """记录阅读历史的请求体模型"""
    read_duration: int | None = Field(default=None, ge=0, description="阅读时长（秒）")


class HistoryItem(BaseModel):
    """
    阅读历史条目响应模型。
    包含文章基本信息和阅读历史元数据。
    """
    article_id: int
    title: str
    source_name: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None
    read_at: datetime
    read_duration: int = 0

    model_config = {"from_attributes": True}


class HistoryListResponse(BaseModel):
    """
    阅读历史分页响应模型。
    """
    items: list[HistoryItem]
    total: int
    page: int
    page_size: int
