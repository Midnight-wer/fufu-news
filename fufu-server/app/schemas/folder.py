"""
fufu新闻 - 收藏夹文件夹 Pydantic Schema
============================================
定义收藏夹文件夹相关的请求/响应数据结构（Pydantic 模型）。
"""
from datetime import datetime
from pydantic import BaseModel, Field


class FolderCreate(BaseModel):
    """创建文件夹的请求体模型"""
    name: str = Field(..., min_length=1, max_length=100)
    icon: str = Field(default="📁", max_length=10)
    is_public: bool = False


class FolderUpdate(BaseModel):
    """更新文件夹的请求体模型（所有字段可选）"""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=10)
    is_public: bool | None = None
    sort_order: int | None = None


class FolderResponse(BaseModel):
    """文件夹详情响应模型"""
    id: int
    user_id: int
    name: str
    icon: str
    is_public: bool
    sort_order: int
    article_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class FolderListResponse(BaseModel):
    """文件夹列表响应模型"""
    folders: list[FolderResponse]
    total: int


class FolderArticlesResponse(BaseModel):
    """文件夹内文章列表分页响应模型"""
    items: list[dict]  # 使用 dict 以兼容 ArticleResponse 的灵活性
    total: int
    page: int
    page_size: int


class MoveArticleRequest(BaseModel):
    """移动文章到另一个文件夹的请求体模型"""
    article_id: int
    from_folder_id: int
    to_folder_id: int
