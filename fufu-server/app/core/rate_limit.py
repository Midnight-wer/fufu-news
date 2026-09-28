"""
fufu新闻 - API 频率限制中间件
==============================
基于滑动窗口算法的内存级频率限制器，无需 Redis 依赖。

核心功能：
1. 每 IP 每分钟限制请求数（可配置）
2. 支持突发流量（burst size）
3. IP 白名单（本地地址默认放行）
4. 返回标准 RateLimit 响应头
5. 定期清理过期记录防止内存泄漏
6. 线程安全（asyncio.Lock）

请求头返回：
- X-RateLimit-Limit: 每分钟最大请求数
- X-RateLimit-Remaining: 剩余可用请求数
- X-RateLimit-Reset: 窗口重置时间（Unix 时间戳）
- Retry-After: 被限流时建议等待秒数
"""

import time
import asyncio
import logging
from collections import defaultdict
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger("fufu.security")

# ========== 频率限制器核心 ==========


class RateLimiter:
    """
    滑动窗口频率限制器。

    使用滑动窗口算法（而非固定窗口）来平滑限制流量。
    每个 IP 维护一个请求时间戳队列，每次请求时清理过期记录并检查是否超限。

    使用示例:
        limiter = RateLimiter(requests_per_minute=60, burst_size=10)
        allowed = await limiter.is_allowed("192.168.1.1")
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        whitelist: Optional[list[str]] = None,
    ):
        """
        Args:
            requests_per_minute: 每分钟允许的最大请求数
            burst_size: 突发流量额外允许的请求数（短时超过限制的缓冲）
            whitelist: 不受限流影响的 IP 列表
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.whitelist: set[str] = set(whitelist or [])
        self._window_size: float = 60.0  # 窗口大小（秒）

        # IP -> 请求时间戳列表（滑动窗口内的记录）
        self._requests: dict[str, list[float]] = defaultdict(list)
        # IP -> 被限流的时间（用于返回 Retry-After）
        self._blocked_until: dict[str, float] = {}

        self._lock = asyncio.Lock()
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 300  # 每 5 分钟清理一次

    async def _cleanup_if_needed(self):
        """定期清理过期 IP 记录，防止内存泄漏。"""
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        async with self._lock:
            cutoff = now - self._window_size * 2  # 保留两倍窗口时间的数据
            # 清理请求记录
            stale_ips = [
                ip
                for ip, timestamps in self._requests.items()
                if not timestamps or timestamps[-1] < cutoff
            ]
            for ip in stale_ips:
                del self._requests[ip]

            # 清理已过期的封禁记录
            stale_blocks = [
                ip for ip, blocked_until in self._blocked_until.items()
                if blocked_until < now
            ]
            for ip in stale_blocks:
                del self._blocked_until[ip]

            self._last_cleanup = now

            if stale_ips:
                logger.debug(f"频率限制器清理了 {len(stale_ips)} 个过期 IP 记录")

    async def is_allowed(self, ip: str) -> bool:
        """
        检查指定 IP 的请求是否在频率限制内。

        Args:
            ip: 客户端 IP 地址

        Returns:
            True 如果请求被允许，False 如果超过限制
        """
        # 白名单直接放行
        if ip in self.whitelist:
            return True

        await self._cleanup_if_needed()

        now = time.monotonic()
        window_start = now - self._window_size
        max_requests = self.requests_per_minute + self.burst_size

        async with self._lock:
            timestamps = self._requests[ip]

            # 移除窗口外的旧记录（滑动窗口核心逻辑）
            while timestamps and timestamps[0] < window_start:
                timestamps.pop(0)

            if len(timestamps) >= max_requests:
                # 被限流，记录恢复时间
                if timestamps:
                    self._blocked_until[ip] = timestamps[0] + self._window_size
                return False

            timestamps.append(now)
            return True

    async def get_remaining(self, ip: str) -> int:
        """
        获取指定 IP 的剩余可用请求数。

        Args:
            ip: 客户端 IP 地址

        Returns:
            剩余可用请求数
        """
        if ip in self.whitelist:
            return self.requests_per_minute + self.burst_size

        now = time.monotonic()
        window_start = now - self._window_size
        max_requests = self.requests_per_minute + self.burst_size

        async with self._lock:
            timestamps = self._requests.get(ip, [])
            # 清理过期记录
            while timestamps and timestamps[0] < window_start:
                timestamps.pop(0)
            used = len(timestamps)
            return max(0, max_requests - used)

    async def get_retry_after(self, ip: str) -> int:
        """
        获取被限流后的建议等待秒数。

        Args:
            ip: 客户端 IP 地址

        Returns:
            建议等待秒数，未限流时返回 0
        """
        now = time.monotonic()
        blocked_until = self._blocked_until.get(ip, 0)
        if blocked_until > now:
            return max(1, int(blocked_until - now))
        return 0


# ========== 全局频率限制器实例 ==========
# 从 settings 读取配置，在应用启动时初始化
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """获取全局频率限制器实例（懒初始化）。"""
    global _rate_limiter
    if _rate_limiter is None:
        whitelist = [
            ip.strip()
            for ip in settings.rate_limit_whitelist.split(",")
            if ip.strip()
        ]
        _rate_limiter = RateLimiter(
            requests_per_minute=settings.rate_limit_requests_per_minute,
            burst_size=settings.rate_limit_burst_size,
            whitelist=whitelist,
        )
        logger.info(
            f"频率限制器已初始化: {settings.rate_limit_requests_per_minute} req/min "
            f"+ {settings.rate_limit_burst_size} burst, 白名单: {whitelist}"
        )
    return _rate_limiter


# ========== FastAPI 中间件 ==========


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI 频率限制中间件。

    对每个请求检查 IP 频率限制，超限时返回 429 Too Many Requests。
    添加标准的 RateLimit 响应头。
    """

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # 跳过文档页面和健康检查
        path = request.url.path
        if path in ("/docs", "/redoc", "/openapi.json") or path.startswith(
            "/api/v1/health"
        ):
            return await call_next(request)

        # 如果全局禁用频率限制，直接放行
        if not settings.rate_limit_enabled:
            return await call_next(request)

        limiter = get_rate_limiter()
        ip = _get_client_ip(request)

        allowed = await limiter.is_allowed(ip)
        remaining = await limiter.get_remaining(ip)
        retry_after = await limiter.get_retry_after(ip)

        if not allowed:
            logger.warning(
                f"频率限制触发: IP={ip} 路径={path} 剩余={remaining} 等待={retry_after}s"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "data": [],
                    "message": f"请求过于频繁，请等待 {retry_after} 秒后重试",
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(
                        limiter.requests_per_minute + limiter.burst_size
                    ),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(
                        int(time.time() + retry_after)
                    ),
                    "Cache-Control": "no-cache",
                },
            )

        response = await call_next(request)

        # 添加速率限制响应头
        response.headers["X-RateLimit-Limit"] = str(
            limiter.requests_per_minute + limiter.burst_size
        )
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(
            int(time.time() + 60)
        )

        return response


def _get_client_ip(request: Request) -> str:
    """
    从请求中提取客户端真实 IP。

    优先级：
    1. X-Forwarded-For 头（取第一个，即原始客户端 IP）
    2. X-Real-IP 头
    3. request.client.host（直连 IP）
    """
    # X-Forwarded-For 可能包含多个 IP（由代理链追加），取第一个
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"
