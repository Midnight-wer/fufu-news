"""
fufu新闻 - 文章数据模型
==========================
定义 Article（文章）ORM 模型，以及 SQLAlchemy 事件监听器，
用于在文章插入/更新/删除时自动同步 FTS5 全文搜索索引。

FTS5 索引使用 jieba 分词处理中文内容，提升中文全文搜索的准确性。
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

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
    import re

    import jieba
    # 去除 HTML 标签（保留纯文本）
    clean = re.sub(r"<[^>]+>", "", content)
    # 规范化空白字符
    clean = re.sub(r"\s+", " ", clean).strip()
    # jieba.cut_for_search: 搜索引擎模式，会同时切出精确模式和细粒度模式的词
    return " ".join(jieba.cut_for_search(clean))


# 进 FTS5 索引的字段：只有这两个真的变了才需要重建索引
_FTS_INDEXED_ATTRS = ("title", "content")

# 清洗后正文长度 <= 该值则在事件内同步分词（约 10~20ms，保持强一致）；
# 超过则移交后台线程，避免长文（50KB 可达 2s）阻塞事件循环。
FTS_INLINE_TOKENIZE_LIMIT = 4000

# 总开关：置 False 可一键退化为「全同步」行为（回滚用）
FTS_ASYNC_ENABLED = True


def _fts_fields_changed(target) -> bool:
    """
    判断本次 UPDATE 是否真的修改了进 FTS5 索引的字段（title / content）。

    使用 SQLAlchemy 的 attribute history：
    get_history(obj, key) 返回 History(added, unchanged, deleted)，
    只有 added/deleted 非空时 has_changes() 才为 True。

    实测（SQLAlchemy 2.0.30 + async session，after_update 内）：
      只改 is_read        → title=False, content=False  ← 直接跳过，jieba 不再被调用
      改 content          → content=True                ← 重建索引

    返回:
        bool: 是否需要重建索引
    """
    from sqlalchemy.orm.attributes import get_history

    for name in _FTS_INDEXED_ATTRS:
        try:
            hist = get_history(target, name)
        except Exception:
            # 取不到 history 时保守起见认为有变化，避免漏更新索引
            return True
        if hist is not None and hist.has_changes():
            return True
    return False


@event.listens_for(Article, "after_insert")
def article_after_insert(mapper, connection, target):
    """
    文章插入后的 SQLAlchemy 事件处理器。
    在文章成功插入数据库后，自动将分词后的标题和正文同步到 FTS5 索引表。

    短文本在事件内同步写入（强一致）；长文本移交后台线程，
    避免批量入库时 jieba 分词长时间占用事件循环。

    参数:
        mapper: SQLAlchemy mapper
        connection: 数据库连接
        target: 刚插入的 Article 实例
    """
    import logging
    logger = logging.getLogger("fufu.models.article")
    content = target.content or ""

    if FTS_ASYNC_ENABLED and len(content) > FTS_INLINE_TOKENIZE_LIMIT:
        try:
            from app.services import fts_worker

            fts_worker.submit("insert", target.id, target.title or "", content)
            return
        except Exception:
            logger.debug("FTS5 后台入队失败，回退同步写入", exc_info=True)

    try:
        tokenized = _tokenize_content(content)
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

    关键修复：原实现**没有做任何脏值判断**，任何 UPDATE 都会跑一次
    jieba 全量分词。而标记已读（is_read）、更新阅读进度（read_progress）、
    收藏（is_favorite）、稍后读（is_later）是最高频的操作，
    每次都要对整篇正文重新分词 —— 实测 1 万字约 38ms、5 万字约 200ms、
    50KB 可达 2s，且全程同步阻塞事件循环，并发稍高即整体卡顿。

    现在只有 title / content 真的变化时才重建索引。

    参数:
        mapper: SQLAlchemy mapper
        connection: 数据库连接
        target: 刚更新的 Article 实例
    """
    import logging
    logger = logging.getLogger("fufu.models.article")

    if not _fts_fields_changed(target):
        logger.debug(f"FTS5 跳过（索引字段未变更）article_id={target.id}")
        return

    content = target.content or ""

    if FTS_ASYNC_ENABLED and len(content) > FTS_INLINE_TOKENIZE_LIMIT:
        try:
            from app.services import fts_worker

            fts_worker.submit("update", target.id, target.title or "", content)
            return
        except Exception:
            logger.debug("FTS5 后台入队失败，回退同步写入", exc_info=True)

    try:
        tokenized = _tokenize_content(content)
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
