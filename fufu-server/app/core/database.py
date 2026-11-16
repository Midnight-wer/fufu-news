"""
fufu新闻 - 数据库连接与会话管理
=====================================
负责：
1. 创建 SQLAlchemy 异步引擎和会话工厂
2. 提供 FastAPI 依赖注入式的数据库会话 get_db()
3. 数据库初始化（建表、FTS5 全文搜索索引、种子数据）
4. 预定义的稳定 RSS 源清单
5. 全量/增量爬取接口
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ========== 数据库引擎 ==========
# 使用 aiosqlite 异步驱动连接 SQLite 数据库
# check_same_thread=False: SQLite 默认只允许创建它的线程访问，设为 False 允许多线程
# timeout=30: 数据库锁定等待超时 30 秒
engine = create_async_engine(
    settings.database_url,
    echo=False,  # 不打印 SQL 日志（开发调试时可设为 True）
    connect_args={"check_same_thread": False, "timeout": 30},
)

# ========== 会话工厂 ==========
# async_sessionmaker 创建异步会话的工厂函数
# expire_on_commit=False: 提交后不过期已加载的对象（避免在 commit 后访问属性报错）
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """
    SQLAlchemy ORM 声明式基类。
    所有数据模型类必须继承此类，SQLAlchemy 通过它自动追踪模型元数据。
    """
    pass


async def get_db() -> AsyncSession:
    """
    FastAPI 依赖注入：为每个请求提供独立的数据库会话。

    使用 async with 确保会话的正确生命周期管理：
    - 正常退出时自动 commit
    - 发生异常时自动 rollback
    - 无论如何都会 close

    用法（在路由函数中）:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session() as session:
        try:
            yield session  # 将会话交给路由函数使用
            await session.commit()  # 正常返回后提交事务
        except Exception:
            await session.rollback()  # 发生异常时回滚
            raise  # 重新抛出异常让 FastAPI 处理
        finally:
            await session.close()  # 确保会话关闭


# ========== 数据库版本迁移 ==========
# 当前期望的数据库 schema 版本号
# 每次添加新表/新字段/新索引时递增此数字，并在 _run_migrations() 中添加迁移逻辑
CURRENT_SCHEMA_VERSION = 9


async def _ensure_schema_version_table(conn):
    """确保 schema_version 表存在（用于跟踪数据库版本）"""
    await conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "  version INTEGER PRIMARY KEY,"
        "  applied_at DATETIME DEFAULT (datetime('now'))"
        ")"
    )


async def _get_schema_version(conn) -> int:
    """获取当前数据库的 schema 版本号（新数据库返回 0）"""
    await _ensure_schema_version_table(conn)
    result = await conn.exec_driver_sql("SELECT MAX(version) FROM schema_version")
    row = result.fetchone()
    return row[0] if row and row[0] is not None else 0


async def _run_migrations(conn):
    """
    按版本号顺序执行数据库迁移。
    每个迁移只在版本号大于当前数据库版本时执行。

    迁移历史：
    v1 → FTS5 虚拟表 + source 表新增字段（enrich_content/use_proxy/priority/etag/last_modified/consecutive_failures/last_error_at）
    v2 → 成就系统表（AchievementDef/AchievementRecord）——已由 ORM create_all 处理
    v3 → feed_log 表索引优化
    v4 → 排行榜系统（article_stats + view_log）
    v5 → article 表新增 deep_summary 字段（深度摘要体系）
    v6 → 阅读历史表（read_history）
    v7 → 收藏夹文件夹系统（favorite_folder + favorite_folder_item）
    v8 → 评论系统（article_comment + comment_like）
    """
    current_version = await _get_schema_version(conn)
    logger = logging.getLogger("fufu.db")

    # ---- v1: FTS5 + source 扩展字段 ----
    if current_version < 1:
        logger.info("数据库迁移 v1: 创建 FTS5 全文搜索索引")
        await conn.exec_driver_sql(
            "CREATE VIRTUAL TABLE IF NOT EXISTS article_fts USING fts5(title, content, content_rowid='id')"
        )
        # 为旧 source 表补充新字段
        migration_columns = [
            ("enrich_content", "INTEGER DEFAULT 1"),
            ("use_proxy", "INTEGER DEFAULT 0"),
            ("priority", "INTEGER DEFAULT 2"),
            ("etag", "VARCHAR(500)"),
            ("last_modified", "VARCHAR(200)"),
            ("consecutive_failures", "INTEGER DEFAULT 0"),
            ("last_error_at", "DATETIME"),
        ]
        for col_name, col_def in migration_columns:
            try:
                await conn.exec_driver_sql(
                    f"ALTER TABLE source ADD COLUMN {col_name} {col_def}"
                )
            except Exception:
                pass  # 列已存在
        await conn.exec_driver_sql("INSERT INTO schema_version (version) VALUES (1)")
        logger.info("迁移 v1 完成")

    # ---- v2: 成就系统（已由 ORM 自动建表，此处记录版本） ----
    if current_version < 2:
        logger.info("数据库迁移 v2: 成就系统")
        await conn.exec_driver_sql("INSERT INTO schema_version (version) VALUES (2)")
        logger.info("迁移 v2 完成")

    # ---- v3: feed_log 索引（提升查询性能） ----
    if current_version < 3:
        logger.info("数据库迁移 v3: feed_log 索引优化")
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_feed_log_source_id ON feed_log(source_id)"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_feed_log_created_at ON feed_log(created_at)"
            )
        except Exception:
            pass
        await conn.exec_driver_sql("INSERT INTO schema_version (version) VALUES (3)")
        logger.info("迁移 v3 完成")

    # ---- v4: 排行榜系统（article_stats + view_log） ----
    if current_version < 4:
        logger.info("数据库迁移 v4: 排行榜系统")
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS article_stats ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  article_id INTEGER NOT NULL UNIQUE REFERENCES article(id) ON DELETE CASCADE,"
                "  view_count INTEGER DEFAULT 0,"
                "  comment_count INTEGER DEFAULT 0,"
                "  collect_count INTEGER DEFAULT 0,"
                "  hot_score REAL DEFAULT 0.0,"
                "  calculated_at DATETIME"
                ")"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_article_stats_hot_score ON article_stats(hot_score)"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_article_stats_article_id ON article_stats(article_id)"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS view_log ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  article_id INTEGER NOT NULL REFERENCES article(id) ON DELETE CASCADE,"
                "  ip_address VARCHAR(45) DEFAULT '',"
                "  viewed_at DATETIME DEFAULT (datetime('now'))"
                ")"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_view_log_article_ip_time ON view_log(article_id, ip_address, viewed_at)"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_view_log_article_id ON view_log(article_id)"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_view_log_viewed_at ON view_log(viewed_at)"
            )
        except Exception:
            pass
        await conn.exec_driver_sql("INSERT INTO schema_version (version) VALUES (4)")
        logger.info("迁移 v4 完成")

    # ---- v5: article 深度摘要字段 ----
    if current_version < 5:
        logger.info("数据库迁移 v5: 为 article 表添加 deep_summary 字段")
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE article ADD COLUMN deep_summary TEXT"
            )
        except Exception:
            pass  # 列已存在
        await conn.exec_driver_sql("INSERT INTO schema_version (version) VALUES (5)")
        logger.info("迁移 v5 完成")

    # ---- v6: 阅读历史表 ----
    if current_version < 6:
        logger.info("数据库迁移 v6: 创建 read_history 阅读历史表")
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS read_history ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,"
                "  article_id INTEGER NOT NULL REFERENCES article(id) ON DELETE CASCADE,"
                "  read_at DATETIME DEFAULT (datetime('now')),"
                "  read_duration INTEGER DEFAULT 0,"
                "  UNIQUE(user_id, article_id)"
                ")"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_read_history_user_id ON read_history(user_id)"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_read_history_article_id ON read_history(article_id)"
            )
        except Exception:
            pass
        await conn.exec_driver_sql("INSERT INTO schema_version (version) VALUES (6)")
        logger.info("迁移 v6 完成")

    # ---- v7: 收藏夹文件夹系统 ----
    if current_version < 7:
        logger.info("数据库迁移 v7: 创建收藏夹文件夹系统 (favorite_folder + favorite_folder_item)")
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS favorite_folder ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,"
                "  name VARCHAR(100) NOT NULL,"
                "  icon VARCHAR(10) DEFAULT '\U0001F4C1',"
                "  is_public BOOLEAN DEFAULT 0,"
                "  sort_order INTEGER DEFAULT 0,"
                "  created_at DATETIME DEFAULT (datetime('now')),"
                "  UNIQUE(user_id, name)"
                ")"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS favorite_folder_item ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  folder_id INTEGER NOT NULL REFERENCES favorite_folder(id) ON DELETE CASCADE,"
                "  article_id INTEGER NOT NULL REFERENCES article(id) ON DELETE CASCADE,"
                "  added_at DATETIME DEFAULT (datetime('now')),"
                "  UNIQUE(folder_id, article_id)"
                ")"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_fav_folder_user_id ON favorite_folder(user_id)"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_fav_item_folder_id ON favorite_folder_item(folder_id)"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_fav_item_article_id ON favorite_folder_item(article_id)"
            )
        except Exception:
            pass
        await conn.exec_driver_sql("INSERT INTO schema_version (version) VALUES (7)")
        logger.info("迁移 v7 完成")

    # ---- v8: 评论系统 ----
    if current_version < 8:
        logger.info("数据库迁移 v8: 创建评论系统 (article_comment + comment_like)")
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS article_comment ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  article_id INTEGER NOT NULL REFERENCES article(id) ON DELETE CASCADE,"
                "  user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,"
                "  parent_id INTEGER REFERENCES article_comment(id) ON DELETE CASCADE,"
                "  content TEXT NOT NULL,"
                "  created_at DATETIME DEFAULT (datetime('now')),"
                "  updated_at DATETIME,"
                "  likes_count INTEGER DEFAULT 0"
                ")"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_comment_article ON article_comment(article_id, created_at)"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_comment_parent ON article_comment(parent_id)"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS comment_like ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  comment_id INTEGER NOT NULL REFERENCES article_comment(id) ON DELETE CASCADE,"
                "  user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,"
                "  created_at DATETIME DEFAULT (datetime('now')),"
                "  UNIQUE(comment_id, user_id)"
                ")"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_comment_like_comment ON comment_like(comment_id)"
            )
        except Exception:
            pass
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_comment_like_user ON comment_like(user_id)"
            )
        except Exception:
            pass
        await conn.exec_driver_sql("INSERT INTO schema_version (version) VALUES (8)")
        logger.info("迁移 v8 完成")

    # ---- v9: 文章立场投票 ----
    if current_version < 9:
        logger.info("数据库迁移 v9: 创建文章立场投票表 (article_poll)")
        # 说明：文章页的「你怎么看？」投票原先是纯前端 localStorage 假数据，
        # 刷新/换设备即丢失，且统计时未按文章过滤（在第 5 篇投票，第 100 篇也显示
        # "已有 1 人参与"）。现在改为真实落库，一人一票、可改票。
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS article_poll ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  article_id INTEGER NOT NULL REFERENCES article(id) ON DELETE CASCADE,"
                "  user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,"
                "  option TEXT NOT NULL,"
                "  created_at DATETIME DEFAULT (datetime('now')),"
                "  updated_at DATETIME,"
                "  UNIQUE(article_id, user_id)"
                ")"
            )
        except Exception as e:
            logger.warning(f"迁移 v9 创建 article_poll 失败: {e}")
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_poll_article ON article_poll(article_id)"
            )
        except Exception as e:
            logger.warning(f"迁移 v9 创建索引失败: {e}")
        await conn.exec_driver_sql("INSERT INTO schema_version (version) VALUES (9)")
        logger.info("迁移 v9 完成")

    await conn.commit()


async def init_db():
    """
    数据库初始化——在应用启动时调用，执行以下步骤：
    1. 创建所有 ORM 模型对应的数据库表（如果不存在）
    2. 启用 SQLite WAL 模式（提升并发读写性能）
    3. 启用外键约束
    4. 执行版本化数据库迁移（FTS5 / 新增字段 / 索引）
    5. 播种成就定义数据（如果为空）
    6. 播种默认订阅源列表
    7. 创建默认用户账号（如果不存在）
    """
    # 导入所有模型，确保 Base.metadata 中包含所有表定义
    from app.models import (  # noqa: F401
        achievement,
        article,
        comment,
        favorite,
        feed_log,
        history,
        ranking,
        source,
        user,
    )

    # 创建所有数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # WAL 模式：写操作不阻塞读操作，提升并发性能
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        # 启用外键约束（SQLite 默认不启用）
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    # 执行版本化数据库迁移
    async with engine.connect() as conn:
        await _run_migrations(conn)

    # 播种成就数据（如果成就定义表为空）
    from app.models.achievement import ACHIEVEMENT_SEEDS, AchievementDef
    async with async_session() as session:
        from sqlalchemy import select as _select
        ach_result = await session.execute(_select(AchievementDef))
        if not ach_result.scalars().first():
            for seed in ACHIEVEMENT_SEEDS:
                session.add(AchievementDef(**seed))
            await session.commit()

    # 播种默认订阅源列表
    await _seed_default_sources()

    # 创建默认用户（如果不存在）
    from passlib.context import CryptContext

    from app.models.user import User
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.username == settings.default_username)
        )
        if not result.scalar_one_or_none():
            session.add(User(
                username=settings.default_username,
                password_hash=pwd_context.hash(settings.default_password),  # 对密码做 bcrypt 哈希
                settings={},
            ))
            await session.commit()


# ========== 稳定 RSS 订阅源清单 ==========
# 经过验证的 RSSHub 路由 + 直接 RSS 源，按分类组织
# 每个源包含：名称、URL、源类型（rss/web）、所属文件夹
STABLE_SOURCES = [
    # ===== 科技 (22个源) =====
    {"name": "💻 少数派", "url": "https://sspai.com/feed", "source_type": "rss", "folder": "科技"},
    {"name": "💻 36氪", "url": "https://36kr.com/feed", "source_type": "rss", "folder": "科技"},
    {"name": "💻 IT之家", "url": "https://www.ithome.com/rss/", "source_type": "rss", "folder": "科技"},
    {"name": "💻 InfoQ中文", "url": "https://www.infoq.cn/feed", "source_type": "rss", "folder": "科技"},
    {"name": "💻 Solidot", "url": "https://www.solidot.org/index.rss", "source_type": "rss", "folder": "科技"},
    {"name": "💻 OSChina", "url": "https://www.oschina.net/news/rss", "source_type": "rss", "folder": "科技"},
    {"name": "💻 SegmentFault", "url": "https://segmentfault.com/feeds", "source_type": "rss", "folder": "科技"},
    {"name": "💻 掘金", "url": "https://juejin.cn/rss", "source_type": "rss", "folder": "科技"},
    {"name": "💻 爱范儿", "url": "https://www.ifanr.com/feed", "source_type": "rss", "folder": "科技"},
    {"name": "💻 V2EX", "url": "https://www.v2ex.com/index.xml", "source_type": "rss", "folder": "科技"},
    {"name": "💻 CSDN", "url": "https://blog.csdn.net/nav/ai/rss", "source_type": "rss", "folder": "科技"},
    {"name": "💻 博客园", "url": "https://feed.cnblogs.com/blog/sitehome/rss", "source_type": "rss", "folder": "科技"},
    {"name": "💻 Node.js Blog", "url": "https://nodejs.org/en/feed/blog.xml", "source_type": "rss", "folder": "科技"},
    {"name": "💻 Go Blog", "url": "https://go.dev/blog/feed.atom", "source_type": "rss", "folder": "科技"},
    {"name": "💻 Rust Blog", "url": "https://blog.rust-lang.org/feed.xml", "source_type": "rss", "folder": "科技"},
    {"name": "💻 FreeBuf", "url": "https://www.freebuf.com/feed", "source_type": "rss", "folder": "科技"},
    {"name": "💻 TechCrunch", "url": "https://techcrunch.com/feed", "source_type": "rss", "folder": "科技"},
    {"name": "💻 Hacker News", "url": "https://hnrss.org/frontpage", "source_type": "rss", "folder": "科技"},
    # 以下从其他分类归位到科技
    {"name": "💻 The Verge", "url": "https://www.theverge.com/rss/index.xml", "source_type": "rss", "folder": "科技"},
    {"name": "💻 Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "source_type": "rss", "folder": "科技"},
    {"name": "💻 Wired", "url": "https://www.wired.com/feed/rss", "source_type": "rss", "folder": "科技"},
    {"name": "💻 Reddit 编程", "url": "https://www.reddit.com/r/programming/.rss", "source_type": "rss", "folder": "科技"},

    # ===== 游戏 (7个源) =====
    {"name": "🎮 机核网", "url": "https://www.gcores.com/rss", "source_type": "rss", "folder": "游戏"},
    {"name": "🎮 TapTap资讯", "url": "https://www.taptap.cn/rss/news", "source_type": "rss", "folder": "游戏"},
    {"name": "🎮 游研社", "url": "https://www.yystv.cn/rss/feed", "source_type": "rss", "folder": "游戏"},
    {"name": "🎮 触乐", "url": "https://www.chuapp.com/feed", "source_type": "rss", "folder": "游戏"},
    {"name": "🎮 B站游戏区排行", "url": "https://api.bilibili.com/x/web-interface/ranking/v2?rid=4&type=all", "source_type": "web", "folder": "游戏"},
    {"name": "🎮 Steam News", "url": "https://store.steampowered.com/feeds/news.xml", "source_type": "rss", "folder": "游戏"},
    {"name": "🎮 Polygon", "url": "https://www.polygon.com/rss/index.xml", "source_type": "rss", "folder": "游戏"},

    # ===== 动漫 (7个源) =====
    {"name": "🌸 ACG17动漫资讯", "url": "https://acg17.com/feed", "source_type": "rss", "folder": "动漫"},
    {"name": "🌸 萌娘百科更新", "url": "https://zh.moegirl.org.cn/api.php?action=feedrecentchanges&feedformat=rss", "source_type": "rss", "folder": "动漫"},
    {"name": "🌸 B站番剧排行", "url": "https://api.bilibili.com/x/web-interface/ranking/v2?rid=32&type=all", "source_type": "web", "folder": "动漫"},
    {"name": "🌸 B站热门视频", "url": "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all", "source_type": "web", "folder": "动漫"},
    {"name": "🌸 B站动画区排行", "url": "https://api.bilibili.com/x/web-interface/ranking/v2?rid=1&type=all", "source_type": "web", "folder": "动漫"},
    {"name": "🌸 B站鬼畜排行", "url": "https://api.bilibili.com/x/web-interface/ranking/v2?rid=119&type=all", "source_type": "web", "folder": "动漫"},
    {"name": "🌸 Anime News Network", "url": "https://www.animenewsnetwork.com/news/rss.xml", "source_type": "rss", "folder": "动漫"},

    # ===== 设计/创意 (5个源) =====
    {"name": "🎨 优设网", "url": "https://www.uisdc.com/feed", "source_type": "rss", "folder": "设计"},
    {"name": "🎨 小众软件", "url": "https://www.appinn.com/feed", "source_type": "rss", "folder": "设计"},
    {"name": "🎨 阮一峰的网络日志", "url": "https://feeds.feedburner.com/ruanyifeng", "source_type": "rss", "folder": "设计"},
    {"name": "🎨 酷壳 CoolShell", "url": "https://www.coolshell.cn/feed", "source_type": "rss", "folder": "设计"},
    {"name": "🎨 Smashing Magazine", "url": "https://www.smashingmagazine.com/feed", "source_type": "rss", "folder": "设计"},

    # ===== 科普 (5个源) =====
    {"name": "🌿 果壳网", "url": "https://www.guokr.com/rss/", "source_type": "rss", "folder": "科普"},
    {"name": "🌿 科学公园", "url": "https://www.scipark.net/feed", "source_type": "rss", "folder": "科普"},
    {"name": "🌿 NASA Breaking News", "url": "https://www.nasa.gov/feeds/iotd-feed/", "source_type": "rss", "folder": "科普"},
    {"name": "🌿 Nature Briefing", "url": "https://www.nature.com/nature.rss", "source_type": "rss", "folder": "科普"},
    {"name": "🌿 中国科普博览", "url": "https://www.kepu.net.cn/rss.xml", "source_type": "rss", "folder": "科普"},

    # ===== 综合 (7个源) =====
    {"name": "📰 人民网", "url": "http://www.people.com.cn/rss/politics.xml", "source_type": "rss", "folder": "综合"},
    {"name": "📰 月光博客", "url": "https://www.williamlong.info/rss.xml", "source_type": "rss", "folder": "综合"},
    {"name": "📰 什么值得买", "url": "https://www.smzdm.com/feed", "source_type": "rss", "folder": "综合"},
    {"name": "📰 知乎每日精选", "url": "https://www.zhihu.com/rss", "source_type": "rss", "folder": "综合"},
    {"name": "📰 BBC中文", "url": "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml", "source_type": "rss", "folder": "综合"},
    {"name": "📰 联合早报", "url": "https://www.zaobao.com.sg/rss", "source_type": "rss", "folder": "综合"},
    {"name": "📰 纽约时报中文", "url": "https://cn.nytimes.com/rss/", "source_type": "rss", "folder": "综合"},
]


async def _seed_default_sources():
    """
    播种默认订阅源——每次启动时同步稳定源清单。

    逻辑：
    1. 对比数据库中已有的源和 STABLE_SOURCES 清单
    2. 删除不在新清单中的旧源（同时删除关联的文章）
    3. 添加清单中的新源
    4. 已有源保持不变

    这确保了订阅源列表始终与代码中定义的 STABLE_SOURCES 保持一致。
    """
    import logging

    from sqlalchemy import delete, select

    from app.models.article import Article
    from app.models.source import Source
    logger = logging.getLogger("fufu")

    async with async_session() as session:
        # 获取数据库中现有的所有订阅源
        existing = await session.execute(select(Source))
        current = existing.scalars().all()
        current_urls = {s.url for s in current}  # 现有源 URL 集合
        wanted_urls = {s["url"] for s in STABLE_SOURCES}  # 期望的源 URL 集合

        # 同步：删除不在新清单中的旧源，更新已有源的字段，添加新源
        removed = 0
        updated = 0
        added = 0
        url_map = {s["url"]: s for s in STABLE_SOURCES}

        for s in current:
            if s.url not in wanted_urls:
                await session.execute(delete(Article).where(Article.source_id == s.id))
                await session.delete(s)
                removed += 1
            else:
                # 更新已有源的字段（包括新增的策略字段）
                wanted = url_map[s.url]
                changed = False
                if s.name != wanted["name"]:
                    s.name = wanted["name"]
                    changed = True
                if s.folder != wanted.get("folder", "默认分组"):
                    s.folder = wanted.get("folder", "默认分组")
                    changed = True
                if s.source_type != wanted["source_type"]:
                    s.source_type = wanted["source_type"]
                    changed = True
                # 同步策略字段（仅当 STABLE_SOURCES 中明确指定时才更新）
                for field in ("enrich_content", "use_proxy", "priority"):
                    if field in wanted and getattr(s, field, None) != wanted[field]:
                        setattr(s, field, wanted[field])
                        changed = True
                if changed:
                    updated += 1

        for s in STABLE_SOURCES:
            if s["url"] not in current_urls:
                session.add(Source(
                    name=s["name"], url=s["url"],
                    source_type=s["source_type"],
                    folder=s.get("folder", "默认分组"),
                    fetch_interval=30, status="active",
                    enrich_content=s.get("enrich_content", True),
                    use_proxy=s.get("use_proxy", False),
                    priority=s.get("priority", 2),
                ))
                added += 1

        if added or removed or updated:
            await session.commit()
            logger.info(f"订阅源已同步: 新增 {added} 个, 更新 {updated} 个, 移除 {removed} 个, 当前共 {len(STABLE_SOURCES)} 个")
        else:
            logger.info(f"订阅源清单无变化，当前 {len(STABLE_SOURCES)} 个")


async def fetch_all_sources():
    """
    全量爬取所有订阅源——带源间节流以避免被封禁。

    对每个活跃的订阅源依次调用 fetch_source()，
    源与源之间间隔 1 秒，避免短时间内大量请求同一服务器。

    返回:
        dict: {"success": 成功数, "fail": 失败数}
    """
    import asyncio
    import logging
    logger = logging.getLogger("fufu")
    from sqlalchemy import delete, select

    from app.models.article import Article
    from app.models.source import Source

    # 获取所有订阅源
    async with async_session() as session:
        result = await session.execute(select(Source))
        sources = result.scalars().all()

    from app.services.fetcher import fetch_source
    success = 0
    fail = 0

    # 逐个抓取，带 1 秒节流间隔
    for i, src in enumerate(sources):
        if i > 0:
            await asyncio.sleep(1)  # 源间节流：避免被封
        try:
            log_entry = await fetch_source(src)
            if log_entry.status == "success":
                success += 1
            else:
                fail += 1
                logger.warning(f"爬取失败 [{src.name}]: {log_entry.error_msg}")
        except Exception as e:
            fail += 1
            logger.warning(f"爬取异常 [{src.name}]: {e}")

    logger.info(f"全量爬取完成: 成功 {success}, 失败 {fail}")
    return {"success": success, "fail": fail}
