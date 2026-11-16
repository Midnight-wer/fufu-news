"""
fufu新闻 - 访问日志中间件
===========================
为每个 HTTP 请求记录一条访问日志，用于后台统计 PV / UV 与访问趋势。

两路落地：
1. 数据库：access_log 表（由后台任务批量写入，避免每请求一个事务）
2. 日志文件：logs/access.log，nginx combined 格式，
   可直接用 scripts/visit_stats.py 复算 PV / UV，作为对外可复核的原始凭据

设计取舍：
- 静态资源与接口请求同样记录，但 is_page_view=False，不计入 PV 口径；
- 入库走内存缓冲 + 定时批量 flush，写库失败只记 warning，不影响请求；
- 文件写入用 RotatingFileHandler，10MB × 5 份轮转。
"""
import asyncio
import ipaddress
import logging
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("fufu.access")

# 日志文件与轮转参数
LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "logs"
ACCESS_LOG_FILE = LOG_DIR / "access.log"

# 批量入库的刷新间隔（秒）与单批上限
FLUSH_INTERVAL = 2.0
FLUSH_BATCH_SIZE = 500

# 不计入 PV 的静态资源后缀
STATIC_SUFFIXES = (
    ".js", ".mjs", ".css", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".webm", ".json",
)

# 不计入 PV 的接口/探活前缀
NON_PAGE_PREFIXES = ("/api/", "/docs", "/redoc", "/openapi.json")


def _ensure_file_logger() -> logging.Logger:
    """
    准备专用的访问日志文件记录器。

    单独建 logger 并关闭 propagate，避免访问日志同时写进 fufu.log
    （那里是应用运行日志，不是访问日志，混在一起会污染统计口径）。
    """
    access_logger = logging.getLogger("fufu.access.file")
    if access_logger.handlers:
        return access_logger
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        ACCESS_LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    access_logger.addHandler(handler)
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False
    return access_logger


def _is_public_ip(value: str) -> bool:
    """判断字符串是否为可路由的公网 IP（排除回环、内网、保留地址）。"""
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def client_ip(request: Request) -> str:
    """
    解析访客 IP。

    经反向代理 / CDN 时取 X-Forwarded-For 中第一个公网地址，
    否则回落到直连地址。
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    for candidate in forwarded.split(","):
        ip = candidate.strip()
        if ip and _is_public_ip(ip):
            return ip
    if forwarded.strip():
        return forwarded.split(",")[0].strip()[:45]
    host = request.client.host if request.client else ""
    return host[:45]


def is_page_view(path: str) -> bool:
    """判断该路径是否计入 PV（页面访问）口径。"""
    lowered = path.lower()
    if lowered.startswith(NON_PAGE_PREFIXES):
        return False
    if lowered.endswith(STATIC_SUFFIXES):
        return False
    if lowered in {"/health", "/favicon.ico", "/robots.txt", "/sitemap.xml"}:
        return False
    return True


# ========== 内存缓冲与批量写入 ==========
_BUFFER: list[dict] = []
_FLUSH_TASK: asyncio.Task | None = None
_FLUSH_LOCK = asyncio.Lock()


async def flush_access_logs() -> int:
    """
    把缓冲区里的访问记录批量写入数据库。

    返回本次写入的条数；写库失败时保留记录并记录 warning，不抛出异常
    （统计失败不应影响正常请求）。
    """
    global _BUFFER
    if not _BUFFER:
        return 0
    async with _FLUSH_LOCK:
        pending, _BUFFER = _BUFFER, []
    if not pending:
        return 0

    try:
        from app.core.database import async_session
        from app.models.access_log import AccessLog

        async with async_session() as session:
            session.add_all([AccessLog(**item) for item in pending])
            await session.commit()
        return len(pending)
    except Exception as e:
        logger.warning(f"访问日志入库失败（{len(pending)} 条已丢弃）: {e}")
        return 0


async def _flush_loop() -> None:
    """后台定时刷新缓冲区的循环任务。"""
    while True:
        try:
            await asyncio.sleep(FLUSH_INTERVAL)
            await flush_access_logs()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"访问日志刷新循环异常: {e}")


def _ensure_flush_task() -> None:
    """确保后台刷新任务已启动（幂等）。"""
    global _FLUSH_TASK
    if _FLUSH_TASK is None or _FLUSH_TASK.done():
        _FLUSH_TASK = asyncio.get_running_loop().create_task(_flush_loop())


def log_access_line(
    ip: str,
    method: str,
    path: str,
    status_code: int,
    user_agent: str,
    referer: str,
    moment: datetime,
) -> None:
    """
    往 logs/access.log 追加一行 nginx combined 格式的访问记录。

    页面访问上报（POST /stats/hit）也走这里，
    这样文件里的记录与数据库 access_log 表一一对应，可直接复算 PV / UV。
    """
    file_logger = _ensure_file_logger()
    file_logger.info(
        '%s - - [%s] "%s %s HTTP/1.1" %d %d "%s" "%s"',
        ip,
        moment.strftime("%d/%b/%Y:%H:%M:%S +0000"),
        method,
        path,
        status_code,
        0,
        user_agent.replace('"', "'"),
        referer.replace('"', "'"),
    )


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    访问日志中间件——记录每次请求的 IP、路径、状态码与 UA。

    - 请求结束后才记录，拿到真实状态码与耗时；
    - 异常请求（未捕获异常）同样记录，状态码记 500；
    - 记录失败不影响响应。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            try:
                self._record(request, status_code, started)
            except Exception as e:  # pragma: no cover - 记录失败不影响主流程
                logger.debug(f"访问日志记录跳过: {e}")

    def _record(self, request: Request, status_code: int, started: float) -> None:
        duration_ms = (time.perf_counter() - started) * 1000
        path = request.url.path
        ip = client_ip(request)
        user_agent = (request.headers.get("user-agent") or "")[:512]
        referer = (request.headers.get("referer") or "")[:512]
        page_view = is_page_view(path)
        now = datetime.now(timezone.utc)

        item = {
            "path": path[:512],
            "method": request.method,
            "status_code": status_code,
            "ip_address": ip,
            "user_agent": user_agent,
            "referer": referer,
            "is_page_view": page_view,
            "duration_ms": round(duration_ms, 2),
            "created_at": now,
        }

        _BUFFER.append(item)
        _ensure_flush_task()

        log_access_line(
            ip, request.method, path, status_code, user_agent, referer, now
        )
