"""
fufu新闻 - 文章数据模型
==========================
定义 Article（文章）ORM 模型，以及 SQLAlchemy 事件监听器，
用于在文章插入/更新/删除时自动同步 FTS5 全文搜索索引。

FTS5 索引使用 jieba 分词处理中文内容，提升中文全文搜索的准确性。
"""
from sqlalchemy import (
    String, Integer, DateTime, Text, Float, Boolean,
    JSON, ForeignKey, UniqueConstraint, event
)
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.core.database import Base


class Article(Base):
    """
    文章 ORM 模型——对应数据库中的 article 表。

    字段说明：
    - id: 主键，自增
    - source_id: 外键，关联 source 表的订阅源（级联删除）
    - title: 文章标题（最大 500 字符）
    - url: 文章链接（最大 2048 字符）
    - content: 文章正文（富文本 HTML）
    - summary: AI 生成的摘要
    - author: 作者名称
    - published_at: 文章原始发布时间
    - fetched_at: 抓取入库时间（默认当前 UTC 时间）
    - image_url: 文章封面/配图链接
    - is_read: 是否已读（带索引）
    - is_favorite: 是否收藏
    - is_later: 是否标记为稍后阅读
    - read_progress: 阅读进度（0.0 ~ 1.0）
    - tags: AI 生成的标签列表（JSON 数组）
    """
    __tablename__ = "article"
    __table_args__ = (
        # 同源 + 同 URL 唯一约束，防止重复入库
        UniqueConstraint("url", "source_id", name="uq_article_url_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), default="")
    url: Mapped[str] = mapped_column(String(2048), default="")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_later: Mapped[bool] = mapped_column(Boolean, default=False)
    read_progress: Mapped[float] = mapped_column(Float, default=0.0)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    deep_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    """
    深度摘要体系——AI 生成的结构化摘要（JSON 字段）。
    结构：
    {
        "one_liner": "一句话总结",
        "key_data": [{"label": "数据标签", "value": "数据值"}, ...],
        "core_points": ["核心观点1", "核心观点2", ...],
        "background": "背景补充说明",
        "reactions": {"support": "支持方", "oppose": "反对方", "neutral": "中立方"},
        "generated_at": "ISO 时间戳"
    }
    """


def _tokenize_content(content: str | None) -> str:
    """
    使用 jieba 对文章内容进行中文分词，输出空格分隔的 token 串。
    用于构建 FTS5 全文搜索索引。

    处理步骤：
    1. 去除 HTML 标签
    2. 规范化空白字符
    3. 使用 jieba 搜索引擎模式分词（兼顾精确度和召回率）
    4. 用空格连接所有 token

    参数:
        content: 文章正文 HTML 字符串（可为 None）

    返回:
        str: 空格分隔的分词结果字符串
    """
    if not content:
        return ""
    import jieba
    import re
    # 去除 HTML 标签（保留纯文本）
    clean = re.sub(r"<[^>]+>", "", content)
    # 规范化空白字符
    clean = re.sub(r"\s+", " ", clean).strip()
    # jieba.cut_for_search: 搜索引擎模式，会同时切出精确模式和细粒度模式的词
    return " ".join(jieba.cut_for_search(clean))


@event.listens_for(Article, "after_insert")
def article_after_insert(mapper, connection, target):
    """
    文章插入后的 SQLAlchemy 事件处理器。
    在文章成功插入数据库后，自动将分词后的标题和正文同步到 FTS5 索引表。
    如果 FTS5 同步失败（如测试环境），静默跳过，不影响文章入库。

    参数:
        mapper: SQLAlchemy mapper
        connection: 数据库连接
        target: 刚插入的 Article 实例
    """
    import logging
    logger = logging.getLogger("fufu.models.article")
    try:
        tokenized = _tokenize_content(target.content)
        connection.exec_driver_sql(
            "INSERT INTO article_fts(rowid, title, content) VALUES (?, ?, ?)",
            (target.id, target.title or "", tokenized),
        )
    except Exception:
        logger.debug(f"FTS5 索引同步跳过 (article_id={target.id})", exc_info=True)


@event.listens_for(Article, "after_update")
def article_after_update(mapper, connection, target):
    """
    文章更新后的 SQLAlchemy 事件处理器。
    当文章内容或标题发生变化时，自动更新 FTS5 索引中对应的条目。
    如果 FTS5 同步失败，静默跳过。

    参数:
        mapper: SQLAlchemy mapper
        connection: 数据库连接
        target: 刚更新的 Article 实例
    """
    import logging
    logger = logging.getLogger("fufu.models.article")
    try:
        tokenized = _tokenize_content(target.content)
        connection.exec_driver_sql(
            "UPDATE article_fts SET title=?, content=? WHERE rowid=?",
            (target.title or "", tokenized, target.id),
        )
    except Exception:
        logger.debug(f"FTS5 索引更新跳过 (article_id={target.id})", exc_info=True)


@event.listens_for(Article, "after_delete")
def article_after_delete(mapper, connection, target):
    """
    文章删除后的 SQLAlchemy 事件处理器。
    使用 FTS5 的 'delete' 命令从索引中移除已删除的文章。
    如果 FTS5 同步失败，静默跳过。

    参数:
        mapper: SQLAlchemy mapper
        connection: 数据库连接
        target: 即将被删除的 Article 实例
    """
    import logging
    logger = logging.getLogger("fufu.models.article")
    try:
        connection.exec_driver_sql(
            "INSERT INTO article_fts(article_fts, rowid, title, content) VALUES('delete', ?, ?, ?)",
            (target.id, target.title or "", target.content or ""),
        )
    except Exception:
        logger.debug(f"FTS5 索引删除跳过 (article_id={target.id})", exc_info=True)
