"""
fufu新闻 - 文章 Pydantic Schema
==================================
定义文章相关的请求/响应数据结构（Pydantic 模型）。
用于 FastAPI 的请求体验证和响应格式化。
"""
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ArticleUpdate(BaseModel):
    """
    文章部分更新的请求体模型。
    所有字段均为可选，只传递需要更新的字段即可（PATCH 语义）。

    字段说明：
    - is_read: 标记已读/未读
    - is_favorite: 标记收藏/取消收藏
    - is_later: 标记稍后阅读
    - read_progress: 阅读进度（0.0 ~ 1.0，表示已读百分比）
    """
    is_read: bool | None = None
    is_favorite: bool | None = None
    is_later: bool | None = None
    read_progress: float | None = Field(default=None, ge=0.0, le=1.0)  # 限定范围 0-1


class ArticleResponse(BaseModel):
    """
    文章详情响应模型。
    包含了文章的所有字段以及关联的订阅源名称和所属文件夹。

    字段说明：
    - source_name: 关联订阅源的名称（非数据库字段，由查询时填充）
    - source_folder: 关联订阅源所属文件夹（非数据库字段，由查询时填充）
    """
    id: int
    source_id: int
    title: str
    url: str
    content: str | None
    summary: str | None
    author: str | None
    published_at: datetime | None
    fetched_at: datetime
    image_url: str | None
    is_read: bool
    is_favorite: bool
    is_later: bool
    read_progress: float
    tags: list = Field(default_factory=list)  # 标签列表，默认为空列表
    deep_summary: dict | None = None  # AI 深度结构化摘要（JSON 字段）
    source_name: str | None = None  # 关联订阅源名称（非持久化字段）
    source_folder: str | None = None  # 关联订阅源文件夹（非持久化字段）

    model_config = {"from_attributes": True}  # 允许从 ORM 模型实例直接创建

    @field_validator('tags', mode='before')
    @classmethod
    def coerce_tags(cls, v):
        """
        标签字段的预处理器：如果从数据库读取到的 tags 为 None，
        自动转换为空列表，避免前端收到 null。
        """
        return v if v is not None else []


class ArticleListResponse(BaseModel):
    """
    文章列表分页响应模型。

    字段说明：
    - articles: 当前页的文章列表
    - total: 符合条件的文章总数
    - page: 当前页码
    - page_size: 每页条数
    """
    articles: list[ArticleResponse]
    total: int
    page: int
    page_size: int
