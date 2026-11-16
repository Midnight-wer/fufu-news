"""
fufu新闻 - 应用入口
=====================
FastAPI 主入口文件，负责：
1. 创建和配置 FastAPI 应用实例
2. 配置日志系统（同时输出到控制台和文件）
3. 注册 CORS 中间件（允许跨域请求）
4. 注册 v1 路由（所有 API 端点）
5. 管理应用生命周期（启动时初始化数据库、启动定时调度器）
6. 启动后自动执行全量 RSS 爬取
7. 生产模式下挂载前端静态文件（SPA 回退路由）
"""
import logging
import sys
from pathlib import Path

# 将项目根目录加入 Python 模块搜索路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# ========== 日志配置 ==========
# 日志文件存放在项目根目录下的 logs/ 文件夹
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.INFO,  # 日志级别：INFO 及以上
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  # 日志格式：时间 [级别] 模块名: 消息
    datefmt="%Y-%m-%d %H:%M:%S",  # 时间格式
    handlers=[
        logging.StreamHandler(sys.stdout),  # 控制台输出
        # 文件输出：改为按大小轮转（单文件 20MB × 保留 5 份）。
        # 原先是无上限的单 FileHandler，日志已涨到 37MB / 31 万行。
        RotatingFileHandler(
            LOG_DIR / "fufu.log",
            maxBytes=20 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("fufu")  # 全局日志记录器

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import router as v1_router  # v1 路由聚合器
from app.core.access_log import AccessLogMiddleware
from app.core.anti_crawl import AntiCrawlMiddleware
from app.core.config import settings  # 全局配置单例
from app.core.database import init_db  # 数据库初始化函数
from app.core.rate_limit import RateLimitMiddleware

# 前端构建产物目录（fufu-web 的 Vite 打包输出，可选）
# 开发态前端由 Vite 独立运行在 localhost:3000，不依赖此目录。
BUILT_DIR = Path(__file__).parent.parent.parent / "fufu-web" / "dist"

# 启动期创建的后台任务引用集合。
# 修复：原先 asyncio.create_task() 的返回值被丢弃，任务可能在运行中被 GC 回收，
# 导致启动抓取静默中断；同时关闭阶段也无从取消。
_BACKGROUND_TASKS: set = set()


async def _auto_fetch_on_startup():
    """
    启动后延迟 3 秒自动执行全量爬取。
    使用延迟是为了确保数据库和调度器已完全就绪。
    在后台任务中执行，不会阻塞应用启动。
    """
    import asyncio
    await asyncio.sleep(3)  # 等待 3 秒让数据库完全初始化
    try:
        from app.core.database import fetch_all_sources
        result = await fetch_all_sources()  # 全量抓取所有订阅源
        logger.info(f"启动自动爬取完成: 成功 {result['success']}, 失败 {result['fail']}")
    except asyncio.CancelledError:
        logger.info("启动自动爬取已取消（应用正在关闭）")
    except Exception as e:
        logger.warning(f"启动自动爬取失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期管理器。

    启动阶段（yield 之前）：
    - 初始化数据库（创建表、FTS5 索引、种子数据）
    - 启动定时调度器（含重复启动守卫）
    - 启动 FTS5 后台索引线程（把 jieba 分词移出事件循环）
    - 后台启动全量 RSS 爬取任务
    - 弱密钥安全告警（仅提示，不改变认证行为）

    关闭阶段（yield 之后）：
    - 取消后台任务
    - 停止定时调度器
    """
    import asyncio

    # ---- 启动阶段 ----
    await init_db()  # 初始化数据库（建表 + 播种）
    from app.services.scheduler import start_scheduler, stop_scheduler
    start_scheduler()  # 启动 APScheduler 定时任务

    # FTS5 后台索引线程：让 jieba 分词在独立线程完成，不阻塞事件循环
    try:
        from app.services import fts_worker
        fts_worker.start()
    except Exception as e:
        logger.warning(f"FTS5 后台索引线程启动失败（将退化为同步索引）: {e}")

    logger.info("fufu已苏醒，正在为你打开新闻花园...")

    # 安全告警：JWT 仍为默认/示例密钥时提示更换（不改变任何认证行为）
    if settings.using_default_secret:
        logger.warning(
            "⚠️ 当前 SECRET_KEY 仍是默认值，任何人都可以离线伪造 JWT。"
            "建议在 fufu-server/.env 中设置一个随机字符串后重启。"
        )

    # 启动后自动全量爬取（后台执行，不阻塞应用启动）
    task = asyncio.create_task(_auto_fetch_on_startup())
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    yield  # 应用运行中...

    # ---- 关闭阶段 ----
    for t in list(_BACKGROUND_TASKS):
        t.cancel()
    _BACKGROUND_TASKS.clear()
    stop_scheduler()  # 停止定时任务调度器
    # 把缓冲区里尚未入库的访问日志刷进数据库，避免关机丢数据
    try:
        from app.core.access_log import flush_access_logs
        flushed = await flush_access_logs()
        if flushed:
            logger.info(f"已刷新 {flushed} 条访问日志到数据库")
    except Exception as e:
        logger.debug(f"关闭前刷新访问日志失败: {e}")


# ========== 创建 FastAPI 应用实例 ==========
app = FastAPI(
    title=settings.app_name,  # 应用名称（显示在 Swagger 文档中）
    version=settings.app_version,  # 应用版本
    lifespan=lifespan,  # 生命周期管理
)

# ========== CORS 中间件配置 ==========
# 安全修复：原先 allow_origins=["*"] + allow_credentials=True 是无效且危险的组合
# （浏览器会拒绝 * + 凭据，同时任意站点都可发起跨域请求）。
# 现在改为显式来源白名单，通过 .env 的 CORS_ORIGINS 配置，
# 默认放行本地 Vite 开发端口（3000 / 5173）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)
logger.info(f"CORS 白名单: {settings.cors_origins_list}")

# ========== 安全响应头中间件 ==========
# 为所有 HTTP 响应添加安全加固响应头
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """为所有响应添加基础安全响应头。"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ========== 频率限制中间件 ==========
# 滑动窗口频率限制，防止 API 滥用
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)
    logger.info(
        f"频率限制中间件已启用: {settings.rate_limit_requests_per_minute} req/min "
        f"+ {settings.rate_limit_burst_size} burst"
    )

# ========== 访问日志中间件 ==========
# 记录每次请求的 IP / 路径 / 状态码 / UA，落到 access_log 表与 logs/access.log，
# 供「访问统计」后台页展示 PV / UV，也是对外可复核的原始凭据。
app.add_middleware(AccessLogMiddleware)
logger.info("访问日志中间件已启用: 数据库 access_log + logs/access.log")

# ========== 反爬虫中间件 ==========
# 三层防御：UA 验证 + 蜜罐陷阱 + 行为分析
if settings.anti_crawl_enabled:
    app.add_middleware(AntiCrawlMiddleware)
    logger.info("反爬虫中间件已启用")

# ========== 全局异常处理（必须在路由注册之前） ==========
# 把 HTTPException / 参数校验失败 / 未捕获异常统一成约定信封，
# 并保证 HTTP 状态码与业务 code 一致（不再出现 code=500 却返回 200）。
# 此前完全没有注册异常处理器，未捕获异常会返回纯文本让前端解析崩溃。
from app.core.exceptions import register_exception_handlers

register_exception_handlers(app)

# ========== 路由注册 ==========
# 所有 v1 API 端点挂载在 /api/v1 路径前缀下
app.include_router(v1_router, prefix="/api/v1")

# ========== 前端服务 ==========
# 默认以纯 API 模式运行（开发态前端由 Vite 独立跑在 localhost:3000）。
# 若在 .env 中设置 SERVE_STATIC=true 且 fufu-web/dist/index.html 存在，
# 则由后端一并托管已构建的前端产物。

from fastapi.responses import FileResponse, JSONResponse

if settings.serve_static and (BUILT_DIR / "index.html").exists():
    # ===== 模式A：挂载已构建的前端产物 =====
    app.mount("/assets", StaticFiles(directory=str(BUILT_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """
        SPA 回退路由：把所有非 API 路径交给前端 React Router 处理。

        安全修复：原先直接 `BUILT_DIR / full_path` 拼接，而 FastAPI 会先把
        %2e%2e 解码，`/..%2f..%2f.env` 这类请求可以穿越到构建目录之外。
        现在先规范化路径并校验其必须仍在 BUILT_DIR 内。
        """
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)


        requested = (BUILT_DIR / full_path).resolve()
        root = BUILT_DIR.resolve()
        if requested == root or root in requested.parents:
            if requested.is_file():
                return FileResponse(requested)
        # 其余情况（含穿越尝试、不存在的路径）统一回退到首页
        return FileResponse(root / "index.html")

    logger.info(f"前端已挂载: {BUILT_DIR}")

else:
    # ===== 模式B：纯 API 模式（前端未构建时）=====

    @app.get("/")
    async def root():
        """API 根路径 — 前端未构建时返回 API 信息"""
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "docs": "/docs",
            "endpoints": {
                "health": "/api/v1/health",
                "auth": "/api/v1/auth/token",
                "sources": "/api/v1/sources",
                "articles": "/api/v1/articles",
                "search": "/api/v1/search/web",
                "ai": "/api/v1/ai/chat/stream",
            },
            "frontend": "http://localhost:3000",
            "note": "新版前端请访问 http://localhost:3000；如需恢复原版 Miku UI，请构建旧版前端"
        }

    logger.info("旧版前端未构建，后端以纯 API 模式运行")


# ========== 直接运行入口 ==========
if __name__ == "__main__":
    import uvicorn
    # 使用 uvicorn 启动 ASGI 服务器。
    # 端口修复：原先硬编码 8000，与 vite proxy / launch.py / docker 的 8800 不一致，
    # 直接 `python app/main.py` 会让所有 /api 请求 404。
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.server_port,
        reload=False,  # 默认关闭热重载：reload 会重复触发 lifespan 导致调度器重复启动
    )
