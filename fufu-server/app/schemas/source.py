"""
fufu新闻 - 订阅源 Pydantic Schema
=====================================
定义订阅源相关的请求/响应数据结构（Pydantic 模型）。
用于订阅源的创建、更新和查询接口。
"""
from datetime import datetime
from pydantic import BaseModel, Field


class SourceCreate(BaseModel):
    """
    创建订阅源的请求体模型。

    字段说明：
    - name: 订阅源名称（最大 200 字符，默认空字符串）
    - url: 订阅源 URL（必填，最大 2048 字符）
    - source_type: 源类型，只能是 "rss" 或 "web"
    - fetch_interval: 抓取间隔（分钟），范围 5 ~ 1440（1天）
    - folder: 所属文件夹名称（最大 100 字符）
    """
    name: str = Field(default="", max_length=200)
    url: str = Field(..., max_length=2048)  # ... 表示必填
    source_type: str = Field(default="rss", pattern=r"^(rss|web)$")  # 正则校验：只能是 rss 或 web
    fetch_interval: int = Field(default=30, ge=5, le=1440)  # 5 分钟 ~ 24 小时
    folder: str = Field(default="默认分组", max_length=100)


class SourceUpdate(BaseModel):
    """
    更新订阅源的请求体模型——所有字段均为可选（PATCH 语义）。

    字段说明：
    - status: 源状态，只能是 "active"（活跃）、"paused"（暂停）、"error"（错误）
    """
    name: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2048)
    source_type: str | None = Field(default=None, pattern=r"^(rss|web)$")
    fetch_interval: int | None = Field(default=None, ge=5, le=1440)
    status: str | None = Field(default=None, pattern=r"^(active|paused|error)$")
    folder: str | None = Field(default=None, max_length=100)


class SourceResponse(BaseModel):
    """
    订阅源详情响应模型。
    包含订阅源的所有字段，用于 API 返回。
    """
    id: int
    name: str
    url: str
    source_type: str
    fetch_interval: int
    last_fetched_at: datetime | None  # 上次抓取时间，可能为空
    status: str
    error_message: str | None  # 错误信息，正常时为空
    folder: str
    created_at: datetime

    model_config = {"from_attributes": True}  # 允许从 ORM 模型实例直接创建
