"""
fufu新闻 - FTS5 后台索引线程
==============================
SQLAlchemy 的 ORM 事件回调是**同步上下文**，既不能 await，也不该阻塞事件循环：
- 写成 async def 没人 await，索引根本不会写；
- 回调跑在事件循环所在线程里，阻塞它等于阻塞整个服务。

因此采用「事件只入队（O(1)）+ 独立 worker 线程执行」的模式：
jieba 分词与 FTS5 写入全部在单一后台线程完成。

设计要点：
- 单线程 FIFO：天然串行化 SQLite 写操作，避免 "database is locked"。
- worker 线程自带 sqlite3 连接（WAL + busy_timeout），与主连接互不干扰。
- 启动时在 worker 线程内预热 jieba，把约 280ms 的模型载入也移出事件循环。
- 队列满时丢弃并告警：索引延迟可以容忍，请求阻塞不行。
- 索引内容与同步路径**完全一致**（同一分词函数、同一三条 SQL），
  所以搜索行为零变化，只是执行线程不同。
"""
import logging
import queue
import sqlite3
import threading

logger = logging.getLogger("fufu.fts_worker")

_q: "queue.Queue[tuple]" = queue.Queue(maxsize=5000)
_started = False
_start_lock = threading.Lock()

_SQL_INSERT = "INSERT OR REPLACE INTO article_fts(rowid, title, content) VALUES (?, ?, ?)"
_SQL_UPDATE = "UPDATE article_fts SET title=?, content=? WHERE rowid=?"
_SQL_DELETE = (
    "INSERT INTO article_fts(article_fts, rowid, title, content) VALUES('delete', ?, ?, ?)"
)


def _db_path() -> str:
    """从 SQLAlchemy URL 里取出 SQLite 文件路径。"""
    from app.core.config import settings

    url = settings.database_url
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if url.startswith(prefix):
            return url[len(prefix):]
    return url


def _tokenize(content: str) -> str:
    """在 worker 线程内做分词（jieba 首次载入也发生在这里）。"""
    from app.models.article import _tokenize_content

    return _tokenize_content(content)


def _worker_loop() -> None:
    """worker 主循环：自带连接，串行处理索引任务。"""
    conn = None
    try:
        conn = sqlite3.connect(_db_path(), timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")

        # 预热 jieba：把模型载入开销从事件循环挪到这里
        try:
            _tokenize("预热")
        except Exception:
            logger.debug("jieba 预热失败（不影响运行）", exc_info=True)

        logger.info("FTS5 后台索引线程已就绪")

        while True:
            op, rowid, title, content = _q.get()
            try:
                if op == "delete":
                    conn.execute(_SQL_DELETE, (rowid, title or "", content or ""))
                elif op == "insert":
                    conn.execute(_SQL_INSERT, (rowid, title or "", _tokenize(content)))
                else:  # update
                    conn.execute(_SQL_UPDATE, (rowid, title or "", _tokenize(content)))
                conn.commit()
                logger.debug(f"FTS5 后台索引完成 op={op} rowid={rowid}")
            except Exception as e:
                logger.warning(f"FTS5 后台索引失败 op={op} rowid={rowid}: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass
            finally:
                _q.task_done()
    except Exception as e:
        logger.error(f"FTS5 后台索引线程异常退出: {e}", exc_info=True)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def start() -> None:
    """启动后台索引线程（幂等）。"""
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
        threading.Thread(target=_worker_loop, name="fts-indexer", daemon=True).start()
        logger.info("FTS5 后台索引线程已启动")


def submit(op: str, rowid: int, title: str, content: str) -> None:
    """
    事件回调调用：O(1) 入队，绝不阻塞事件循环。

    参数:
        op: "insert" / "update" / "delete"
        rowid: 文章 ID
        title: 标题
        content: 正文
    """
    start()
    try:
        _q.put_nowait((op, rowid, title, content))
    except queue.Full:
        logger.warning(f"FTS5 索引队列已满，丢弃任务 op={op} rowid={rowid}")


def pending() -> int:
    """当前队列积压数量（便于排查索引延迟）。"""
    return _q.qsize()
