"""
fufu新闻 - 定时调度器（v2.2）
=============================
基于 APScheduler（AsyncIOScheduler）的智能定时任务调度器。

调度策略：
- 全局抓取：每 15 分钟，并发上限 3（避免触发源站反爬封禁）
- 错误重试：每 20 分钟，带指数退避
- 死源清理：每 60 分钟，自动暂停/标记长期无效源
- feed_log 清理：每 24 小时，保留最近 7 天
- 旧文章清理：每 24 小时，保留近 2 年
- 随机抖动：每次调度加 ±45s 随机偏移，避免惊群效应

调度器的生命周期由 main.py 的 lifespan 管理器控制：
- 启动时调用 start_scheduler()
- 关闭时调用 stop_scheduler()
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.core.database import async_session
from app.models.source import Source
from app.models.article import Article
from app.models.feed_log import FeedLog
from app.services.fetcher import fetch_source
from sqlalchemy import select, delete

logger = logging.getLogger("fufu.scheduler")

# 全局异步调度器实例
scheduler = AsyncIOScheduler()

# ========== 调度参数 ==========
_FETCH_SEMAPHORE = asyncio.Semaphore(3)   # 并发上限：3（降低避免触发反爬）
FETCH_ALL_INTERVAL = 15                    # 全局抓取间隔（分钟）
ERROR_RETRY_INTERVAL = 20                  # 错误源重试间隔（分钟）
CLEANUP_INTERVAL = 60                      # 死源清理间隔（分钟）
JITTER_MAX = 45                            # 最大随机抖动（秒）

# 数据保留策略
FEED_LOG_RETENTION_DAYS = 7               # feed_log 保留天数
ARTICLE_RETENTION_DAYS = 730              # 文章保留天数（2 年）

# 防止调度任务重叠：同一任务在上次未完成时不重复启动
_fetch_all_running = False
_retry_errors_running = False
_cleanup_running = False
_cleanup_logs_running = False
_cleanup_articles_running = False

# ========== 自清理阈值 ==========
DEAD_PAUSE_THRESHOLD = 10     # 连续失败 >= 此数 → 自动暂停
DEAD_DELETE_THRESHOLD = 30    # 连续失败 >= 此数 → 自动删除（含文章）


async def _fetch_sources_batch(sources: list[Source]):
    """
    并行抓取一批订阅源（受 _FETCH_SEMAPHORE 并发控制）。

    使用 asyncio.gather 并发执行，单个源失败不影响其他源。

    参数:
        sources: 要抓取的订阅源列表

    返回:
        dict: {"success": 成功数, "fail": 失败数}
    """
    success = 0
    fail = 0

    async def _fetch_one(src: Source):
        nonlocal success, fail
        async with _FETCH_SEMAPHORE:  # 并发控制在最外层
            try:
                log_entry = await fetch_source(src)
                if log_entry.status == "success":
                    success += 1
                else:
                    fail += 1
            except Exception as e:
                fail += 1
                logger.debug(f"抓取异常 [{src.name}]: {e}")

    # 并行启动所有任务，信号量控制实际并发
    await asyncio.gather(*(_fetch_one(s) for s in sources), return_exceptions=True)
    return {"success": success, "fail": fail}


async def _fetch_all_job():
    """
    全局抓取任务——遍历所有活跃源，分批并行抓取。
    使用 _fetch_all_running 标志防止任务重叠。
    """
    global _fetch_all_running
    if _fetch_all_running:
        logger.debug("上一次全局抓取尚未完成，跳过本次调度")
        return
    _fetch_all_running = True
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Source).where(Source.status == "active")
            )
            sources = result.scalars().all()

        if not sources:
            logger.debug("无活跃源，跳过全局抓取")
            return

        logger.info(f"全局抓取开始: {len(sources)} 个活跃源 (并发上限: 3)")
        result = await _fetch_sources_batch(list(sources))
        logger.info(f"全局抓取完成: 成功 {result['success']}, 失败 {result['fail']}")
    finally:
        _fetch_all_running = False


async def _retry_error_sources_job():
    """
    错误源重试任务——定期重试处于 error 状态的订阅源。
    使用 _retry_errors_running 标志防止任务重叠。
    """
    global _retry_errors_running
    if _retry_errors_running:
        return
    _retry_errors_running = True
    try:
        now = datetime.now(timezone.utc)
        async with async_session() as db:
            result = await db.execute(
                select(Source).where(Source.status == "error")
            )
            error_sources = result.scalars().all()

        if not error_sources:
            return

        retry_sources = []
        skipped = 0
        for src in error_sources:
            failures = getattr(src, "consecutive_failures", 0) or 0
            last_err = getattr(src, "last_error_at", None)

            if failures >= 10:
                backoff = timedelta(hours=6)
            elif failures >= 6:
                backoff = timedelta(hours=2)
            elif failures >= 3:
                backoff = timedelta(minutes=30)
            else:
                backoff = timedelta(minutes=ERROR_RETRY_INTERVAL)

            if last_err:
                if last_err.tzinfo is None:
                    last_err = last_err.replace(tzinfo=timezone.utc)
                if (now - last_err) < backoff:
                    skipped += 1
                    continue

            retry_sources.append(src)

        if retry_sources:
            logger.info(f"错误源重试: {len(retry_sources)} 个 (跳过 {skipped} 个在退避期)")
            result = await _fetch_sources_batch(retry_sources)
            logger.info(f"错误源重试完成: 成功 {result['success']}, 失败 {result['fail']}")
    finally:
        _retry_errors_running = False


async def _cleanup_dead_sources_job():
    """
    死源清理任务——自动暂停/删除长期无效的订阅源。
    使用 _cleanup_running 标志防止任务重叠。
    """
    global _cleanup_running
    if _cleanup_running:
        return
    _cleanup_running = True
    try:
        now = datetime.now(timezone.utc)
        paused_count = 0
        deleted_count = 0

        async with async_session() as db:
            result = await db.execute(
                select(Source).where(Source.status.in_(["error", "paused"]))
            )
            sources = result.scalars().all()

            for src in sources:
                failures = getattr(src, "consecutive_failures", 0) or 0
                last_fetched = getattr(src, "last_fetched_at", None)

                if failures >= DEAD_DELETE_THRESHOLD:
                    await db.execute(delete(Article).where(Article.source_id == src.id))
                    await db.delete(src)
                    deleted_count += 1
                    logger.info(f"死源已删除: [{src.name}] (连续失败 {failures} 次)")
                    continue

                if failures >= DEAD_PAUSE_THRESHOLD and src.status != "paused":
                    src.status = "paused"
                    src.error_message = f"自动暂停：连续失败 {failures} 次"
                    paused_count += 1
                    logger.warning(f"死源已暂停: [{src.name}] (连续失败 {failures} 次)")
                    continue

                if src.status == "error" and last_fetched:
                    if last_fetched.tzinfo is None:
                        last_fetched = last_fetched.replace(tzinfo=timezone.utc)
                    days_since = (now - last_fetched).days
                    if days_since >= 7:
                        src.status = "paused"
                        src.error_message = f"自动暂停：超过 {days_since} 天未成功抓取"
                        paused_count += 1
                        logger.warning(f"长期无效源已暂停: [{src.name}] ({days_since} 天)")

            await db.commit()

        if paused_count or deleted_count:
            logger.info(f"死源清理完成: 暂停 {paused_count} 个, 删除 {deleted_count} 个")
    finally:
        _cleanup_running = False


async def _cleanup_feed_logs_job():
    """
    feed_log 清理任务——删除超过保留期的抓取日志。
    使用 _cleanup_logs_running 标志防止任务重叠。
    """
    global _cleanup_logs_running
    if _cleanup_logs_running:
        return
    _cleanup_logs_running = True
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=FEED_LOG_RETENTION_DAYS)
        async with async_session() as db:
            result = await db.execute(
                delete(FeedLog).where(FeedLog.timestamp < cutoff)
            )
            await db.commit()
            deleted = result.rowcount
            if deleted:
                logger.info(f"feed_log 清理完成: 删除 {deleted} 条旧记录（保留 {FEED_LOG_RETENTION_DAYS} 天）")
    except Exception as e:
        logger.error(f"feed_log 清理失败: {e}")
    finally:
        _cleanup_logs_running = False


async def _cleanup_old_articles_job():
    """
    旧文章清理任务——删除超过保留期的文章及其关联数据。
    使用 _cleanup_articles_running 标志防止任务重叠。
    """
    global _cleanup_articles_running
    if _cleanup_articles_running:
        return
    _cleanup_articles_running = True
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=ARTICLE_RETENTION_DAYS)
        async with async_session() as db:
            # 先删除 FTS5 索引中对应的行（通过 rowid 关联）
            # 注意：FTS5 虚拟表不支持 CASCADE，需手动清理 orphan 条目
            try:
                conn = await db.connection()
                await conn.exec_driver_sql(
                    "DELETE FROM article_fts WHERE rowid IN "
                    "(SELECT id FROM article WHERE published_at < :cutoff)",
                    {"cutoff": cutoff.isoformat()},
                )
            except Exception:
                logger.debug("FTS5 索引清理跳过（可能无 orphan 条目）")

            # 删除旧文章（CASCADE 会连带删除 article_stats/read_history 等关联记录）
            result = await db.execute(
                delete(Article).where(Article.published_at < cutoff)
            )
            await db.commit()
            deleted = result.rowcount
            if deleted:
                logger.info(f"旧文章清理完成: 删除 {deleted} 条（保留 {ARTICLE_RETENTION_DAYS} 天）")
    except Exception as e:
        logger.error(f"旧文章清理失败: {e}")
    finally:
        _cleanup_articles_running = False


def start_scheduler():
    """
    启动定时调度器。

    注册五个定时任务：
    1. 全局抓取 — 每 15 分钟（+ 45s 随机抖动）
    2. 错误源重试 — 每 20 分钟（+ 45s 随机抖动）
    3. 死源清理 — 每 60 分钟（+ 45s 随机抖动）
    4. feed_log 清理 — 每 24 小时（保留 7 天）
    5. 旧文章清理 — 每 24 小时（保留 2 年）
    """
    # 主抓取任务：每 15 分钟
    scheduler.add_job(
        _fetch_all_job,
        trigger=IntervalTrigger(minutes=FETCH_ALL_INTERVAL, jitter=JITTER_MAX),
        id="fetch_all",
        name="全局抓取（活跃源）",
        replace_existing=True,
    )

    # 错误源重试任务：每 20 分钟
    scheduler.add_job(
        _retry_error_sources_job,
        trigger=IntervalTrigger(minutes=ERROR_RETRY_INTERVAL, jitter=JITTER_MAX),
        id="retry_errors",
        name="错误源重试",
        replace_existing=True,
    )

    # 死源清理任务：每 60 分钟
    scheduler.add_job(
        _cleanup_dead_sources_job,
        trigger=IntervalTrigger(minutes=CLEANUP_INTERVAL, jitter=JITTER_MAX),
        id="cleanup_dead",
        name="死源自动清理",
        replace_existing=True,
    )

    # feed_log 清理任务：每 24 小时
    scheduler.add_job(
        _cleanup_feed_logs_job,
        trigger=IntervalTrigger(hours=24, jitter=JITTER_MAX),
        id="cleanup_feed_logs",
        name="feed_log 自动清理",
        replace_existing=True,
    )

    # 旧文章清理任务：每 24 小时
    scheduler.add_job(
        _cleanup_old_articles_job,
        trigger=IntervalTrigger(hours=24, jitter=JITTER_MAX),
        id="cleanup_old_articles",
        name="旧文章自动清理",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        f"调度器已启动: 抓取间隔={FETCH_ALL_INTERVAL}min, "
        f"并发上限=3, 错误重试={ERROR_RETRY_INTERVAL}min, "
        f"死源清理={CLEANUP_INTERVAL}min, "
        f"feed_log保留={FEED_LOG_RETENTION_DAYS}天, 文章保留={ARTICLE_RETENTION_DAYS}天"
    )


def stop_scheduler():
    """
    停止定时调度器。

    在应用关闭时调用，优雅地停止所有定时任务。
    wait=False 表示不等待正在运行的任务完成。
    """
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("调度器已停止")
