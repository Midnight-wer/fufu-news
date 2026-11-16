"""
fufu新闻 - 订阅源数据模型
=============================
定义 Source（订阅源/RSS源）ORM 模型。
每个订阅源对应一个 RSS Feed URL 或网页数据接口。
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Source(Base):
    """
    订阅源 ORM 模型——对应数据库中的 source 表。

    字段说明：
    - id: 主键，自增
    - name: 订阅源名称（如"少数派"、"36氪"）
    - url: 订阅源 URL（唯一，不可为空）
    - source_type: 源类型（"rss" 表示 RSS Feed，"web" 表示网页/API）
    - fetch_interval: 抓取间隔（分钟），默认 30
    - last_fetched_at: 上次成功抓取的时间
    - status: 源状态（"active" 活跃 / "paused" 暂停 / "error" 错误）
    - error_message: 最后一次抓取失败的错误信息
    - folder: 所属文件夹/分组名称
    - created_at: 订阅源创建时间
    """
    __tablename__ = "source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), default="rss")
    fetch_interval: Mapped[int] = mapped_column(Integer, default=30)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    folder: Mapped[str] = mapped_column(String(100), default="默认分组")
    # 抓取策略字段
    enrich_content: Mapped[bool] = mapped_column(default=True)  # 是否抓取全文（False=仅用摘要）
    use_proxy: Mapped[bool] = mapped_column(default=False)      # 是否通过代理访问
    priority: Mapped[int] = mapped_column(Integer, default=2)   # 1=高频 2=中频 3=低频
    etag: Mapped[str | None] = mapped_column(String(500), nullable=True)  # HTTP ETag 缓存
    last_modified: Mapped[str | None] = mapped_column(String(200), nullable=True)  # HTTP Last-Modified
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
