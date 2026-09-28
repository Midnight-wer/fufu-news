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
import sys
import logging
from pathlib import Path

# 将项目根目录加入 Python 模块搜索路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# ========== 日志配置 ==========
# 日志文件存放在项目根目录下的 logs/ 文件夹
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,  # 日志级别：INFO 及以上
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  # 日志格式：时间 [级别] 模块名: 消息
    datefmt="%Y-%m-%d %H:%M:%S",  # 时间格式
    handlers=[
        logging.StreamHandler(sys.stdout),  # 控制台输出
        logging.FileHandler(LOG_DIR / "fufu.log", encoding="utf-8"),  # 文件输出（UTF-8 编码）
    ],
)
logger = logging.getLogger("fufu")  # 全局日志记录器

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings  # 全局配置单例
from app.core.database import init_db  # 数据库初始化函数
from app.core.rate_limit import RateLimitMiddleware
from app.core.anti_crawl import AntiCrawlMiddleware
from app.api.v1.router import router as v1_router  # v1 路由聚合器

# 前端构建产物目录（旧版 Vite 打包输出，可选）
# 新版 Next.js 前端独立运行在 localhost:3000，不依赖此目录
BUILT_DIR = Path(__file__).parent.parent.parent / "fufu-web-legacy" / "dist"


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
    except Exception as e:
        logger.warning(f"启动自动爬取失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期管理器。

    启动阶段（yield 之前）：
    - 初始化数据库（创建表、FTS5 索引、种子数据）
    - 启动定时调度器（每 3 分钟全局抓取）
    - 后台启动全量 RSS 爬取任务

    关闭阶段（yield 之后）：
    - 停止定时调度器
    """
    # ---- 启动阶段 ----
    await init_db()  # 初始化数据库（建表 + 播种）
    from app.services.scheduler import start_scheduler, stop_scheduler
    start_scheduler()  # 启动 APScheduler 定时任务
    logger.info("fufu已苏醒，正在为你打开新闻花园...")

    # 启动后自动全量爬取（后台执行，不阻塞应用启动）
    import asyncio
    asyncio.create_task(_auto_fetch_on_startup())

    yield  # 应用运行中...

    # ---- 关闭阶段 ----
    stop_scheduler()  # 停止定时任务调度器


# ========== 创建 FastAPI 应用实例 ==========
app = FastAPI(
    title=settings.app_name,  # 应用名称（显示在 Swagger 文档中）
    version=settings.app_version,  # 应用版本
    lifespan=lifespan,  # 生命周期管理
)

# ========== CORS 中间件配置 ==========
# 允许所有来源的跨域请求（开发环境宽松配置）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有域名访问
    allow_credentials=True,  # 允许携带 Cookie
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
    expose_headers=["*"],  # 暴露所有响应头给前端
)

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

# ========== 反爬虫中间件 ==========
# 三层防御：UA 验证 + 蜜罐陷阱 + 行为分析
if settings.anti_crawl_enabled:
    app.add_middleware(AntiCrawlMiddleware)
    logger.info("反爬虫中间件已启用")

# ========== 路由注册 ==========
# 所有 v1 API 端点挂载在 /api/v1 路径前缀下
app.include_router(v1_router, prefix="/api/v1")

# ========== 前端服务 ==========
# 优先使用旧版前端构建产物（初音主题 Miku UI）
# 如果 dist 不存在，回退到 API 信息页

from fastapi.responses import FileResponse, JSONResponse

if BUILT_DIR.exists():
    # ===== 模式A：挂载旧版前端（完整的 Miku 主题 UI）=====
    app.mount("/assets", StaticFiles(directory=str(BUILT_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """
        SPA 回退路由：把所有非 API 路径交给前端 React Router 处理。
        路径 / 返回 index.html（Miku 主题首页）。
        路径 /api/* 不拦截，走 FastAPI 路由。
        """
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        file_path = BUILT_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(BUILT_DIR / "index.html")

    logger.info(f"前端已挂载 (Miku UI): {BUILT_DIR}")

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
    # 使用 uvicorn 启动 ASGI 服务器，监听所有网卡接口的 8000 端口
    # reload=True 启用热重载（开发时文件修改后自动重启）
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
