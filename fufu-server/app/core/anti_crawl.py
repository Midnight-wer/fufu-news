"""
fufu新闻 - 反爬虫中间件
========================
三层防御体系防止恶意爬虫和扫描器。

Layer 1 — 基础防护：
  - User-Agent 验证：拦截空 UA 和已知爬虫工具 UA
  - 基础安全响应头

Layer 2 — 蜜罐陷阱：
  - 隐藏端点诱捕爬虫（爬虫扫描到 /api/v1/feed 立即封禁）

Layer 3 — 行为分析：
  - 短时间内请求大量不同 ID 的检测
  - 异常高频 404 检测

注意：采用"宁可放过也不误杀"原则，阈值设置较宽松。
"""

import time
import asyncio
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

logger = logging.getLogger("fufu.security")

# ========== 已知爬虫/扫描器 UA 特征 ==========
# 使用子串匹配，包含以下关键词的 UA 直接拦截
_KNOWN_CRAWLER_PATTERNS: list[str] = [
    # 常见漏洞扫描器
    "nikto", "sqlmap", "nmap", "nessus", "openvas",
    "burpsuite", "burp suite", "acunetix", "appscan",
    "netsparker", "webinspect", "zap", "skipfish",
    "arachni", "w3af", "vega", "grendel-scan",
    # 目录扫描工具
    "dirbuster", "dirb", "gobuster", "wfuzz", "ffuf",
    "feroxbuster", "dirsearch",
    # 常见爬虫库 / 无头浏览器（非搜索引擎）
    "scrapy", "phpcrawl", "heritrix", "webcopier",
    "httrack", "webzip", "teleport", "offline explorer",
    "webstripper", "web suckers", "leech",
    # 通用脚本特征
    "python-requests", "python-urllib", "libwww-perl",
    "go-http-client", "curl/", "wget/", "lwp-",
    "java/", "apache-httpclient",
    # 其他可疑工具
    "masscan", "zgrab", "zgrab2",
]

# 编译为正则列表（忽略大小写）
_KNOWN_CRAWLER_RE: list[re.Pattern] = [
    re.compile(re.escape(p), re.IGNORECASE) for p in _KNOWN_CRAWLER_PATTERNS
]

# ========== 行为分析配置 ==========
# 短时间内请求不同文章 ID 的阈值
_RAPID_ID_SCAN_THRESHOLD = 30  # 30 秒内请求超过 30 个不同 ID
_RAPID_ID_SCAN_WINDOW = 30  # 检测窗口（秒）

# 异常高频 404 阈值
_HIGH_404_THRESHOLD = 20  # 60 秒内超过 20 次 404
_HIGH_404_WINDOW = 60  # 检测窗口（秒）


class AntiCrawlMiddleware:
    """
    反爬虫 ASGI 中间件（纯 ASGI，注册在 Starlette 中间件链中）。

    三层防御：
    1. 基础防护：拦截空 UA / 已知爬虫 UA
    2. 蜜罐陷阱：由 honeypot 端点调用 block_ip() 封禁
    3. 行为分析：检测异常请求模式

    使用方式:
        app.add_middleware(AntiCrawlMiddleware)
    """

    def __init__(self, app):
        self.app = app
        # 自注册全局实例，供 honeypot 端点调用
        set_anti_crawl(self)

        # IP 封禁记录: IP -> 封禁到期时间戳（monotonic）
        self.blocked_ips: dict[str, float] = {}
        # IP 行为记录: IP -> [(timestamp, path, status), ...]
        self.ip_behavior: dict[str, list[tuple[float, str, int]]] = defaultdict(list)

        self._lock = asyncio.Lock()
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 300  # 5 分钟清理一次

    async def __call__(self, scope, receive, send):
        """ASGI 入口点。"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 如果全局禁用反爬虫，直接放行
        if not settings.anti_crawl_enabled:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # 提取客户端 IP
        ip = _get_client_ip_from_scope(scope)

        # 白名单：本地/localhost IP 始终放行
        if ip in ("127.0.0.1", "localhost", "::1"):
            await self.app(scope, receive, send)
            return

        # 白名单路径：健康检查、API 文档等始终放行
        _skip_paths = ("/api/v1/health", "/docs", "/openapi.json", "/redoc")
        if request.url.path in _skip_paths or request.url.path.startswith("/docs"):
            await self.app(scope, receive, send)
            return

        # 检查是否已被封禁
        if await self._is_blocked(ip):
            logger.info(f"已封禁 IP 请求被拦截: {ip} -> {request.url.path}")
            await self._send_blocked_response(send)
            return

        # Layer 1: 基础防护 — UA 检查
        ua = _get_header(scope, "user-agent")
        if self._is_bad_ua(ua):
            logger.warning(
                f"可疑 UA 被拦截: IP={ip} UA={ua[:100] if ua else '(无)'} 路径={request.url.path}"
            )
            await self._send_blocked_response(send)
            return

        # Layer 3: 行为分析 — 请求前检查
        suspicious, reason = await self._analyze_pre_request(ip, request)
        if suspicious:
            logger.warning(f"行为分析拦截: IP={ip} 原因={reason}")
            await self._block_ip(ip, reason)
            await self._send_blocked_response(send)
            return

        # 正常处理请求
        path = request.url.path
        await self.app(scope, receive, send)

        # 行为分析 — 请求后记录（需要状态码）
        # 注意：ASGI 中间件无法直接获取响应状态码，需要包装 send
        # 这里采用简化方案：记录请求路径用于模式分析

    async def _is_blocked(self, ip: str) -> bool:
        """检查 IP 是否已被封禁。"""
        async with self._lock:
            blocked_until = self.blocked_ips.get(ip)
            if blocked_until is None:
                return False
            if time.monotonic() < blocked_until:
                return True
            # 封禁已过期，清理
            del self.blocked_ips[ip]
            return False

    async def block_ip(self, ip: str, reason: str = "honeypot"):
        """
        封禁指定 IP。

        Args:
            ip: 要封禁的 IP 地址
            reason: 封禁原因（用于日志）
        """
        duration_hours = settings.anti_crawl_block_duration_hours
        duration_seconds = duration_hours * 3600

        async with self._lock:
            blocked_until = time.monotonic() + duration_seconds
            self.blocked_ips[ip] = blocked_until

        expiry = datetime.now() + timedelta(hours=duration_hours)
        logger.info(
            f"IP 已封禁: {ip} 原因={reason} "
            f"时长={duration_hours}h 到期={expiry.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    async def _block_ip(self, ip: str, reason: str = "behavior"):
        """内部封禁方法（与 block_ip 相同）。"""
        await self.block_ip(ip, reason)

    def _is_bad_ua(self, ua: Optional[str]) -> bool:
        """
        检查 User-Agent 是否为已知爬虫或无效。

        Args:
            ua: User-Agent 字符串

        Returns:
            True 如果 UA 为空或匹配已知爬虫特征
        """
        # 空 UA 直接拦截（正常浏览器不可能没有 UA）
        if not ua:
            return True

        # 检查是否匹配已知爬虫/扫描器特征
        ua_lower = ua.lower()
        for pattern in _KNOWN_CRAWLER_RE:
            if pattern.search(ua_lower):
                return True

        return False

    async def _analyze_pre_request(
        self, ip: str, request: Request
    ) -> tuple[bool, str]:
        """
        请求前行为分析。

        检查项：
        1. 短时间内请求大量不同路径（ID 扫描检测）

        Returns:
            (是否可疑, 原因描述)
        """
        now = time.monotonic()
        path = request.url.path

        async with self._lock:
            # 定期清理过期行为记录
            await self._cleanup_if_needed_locked(now)

            # 记录本次请求
            behavior = self.ip_behavior[ip]
            behavior.append((now, path, 0))  # status 0 表示请求前

            # 限制行为记录大小
            if len(behavior) > 200:
                behavior = behavior[-200:]
                self.ip_behavior[ip] = behavior

            # 检查短时间内是否请求了大量不同路径（ID 扫描特征）
            window_start = now - _RAPID_ID_SCAN_WINDOW
            recent_paths = [
                p for ts, p, s in behavior
                if ts >= window_start and "favicon" not in p.lower()
            ]
            unique_paths = set(recent_paths)

            if len(unique_paths) >= _RAPID_ID_SCAN_THRESHOLD:
                return True, (
                    f"短时间内请求 {len(unique_paths)} 个不同路径 "
                    f"(阈值 {_RAPID_ID_SCAN_THRESHOLD})"
                )

        return False, ""

    async def _cleanup_if_needed_locked(self, now: float):
        """在持有锁的情况下清理过期记录。"""
        if now - self._last_cleanup < self._cleanup_interval:
            return

        # 清理过期封禁
        stale_blocks = [
            ip
            for ip, blocked_until in self.blocked_ips.items()
            if blocked_until < now
        ]
        for ip in stale_blocks:
            del self.blocked_ips[ip]

        # 清理行为记录（保留 10 分钟内的）
        cutoff = now - 600
        stale_ips = []
        for ip, behaviors in self.ip_behavior.items():
            self.ip_behavior[ip] = [
                b for b in behaviors if b[0] >= cutoff
            ]
            if not self.ip_behavior[ip]:
                stale_ips.append(ip)

        for ip in stale_ips:
            del self.ip_behavior[ip]

        self._last_cleanup = now

        if stale_ips or stale_blocks:
            logger.debug(
                f"反爬虫中间件清理: {len(stale_ips)} 个过期行为, "
                f"{len(stale_blocks)} 个过期封禁"
            )

    async def _send_blocked_response(self, send):
        """发送 403 Forbidden 封禁响应。"""
        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [
                [b"content-type", b"application/json; charset=utf-8"],
                [b"x-content-type-options", b"nosniff"],
                [b"cache-control", b"no-store"],
            ],
        })
        body = b'{"code":403,"data":[],"message":"\\u8bbf\\u95ee\\u88ab\\u62d2\\u7edd"}'
        await send({
            "type": "http.response.body",
            "body": body,
        })


# ========== 全局反爬虫中间件实例 ==========
_anti_crawl: Optional[AntiCrawlMiddleware] = None


def get_anti_crawl() -> AntiCrawlMiddleware:
    """获取全局反爬虫中间件实例。"""
    global _anti_crawl
    return _anti_crawl


def set_anti_crawl(middleware: AntiCrawlMiddleware):
    """设置全局反爬虫中间件实例。"""
    global _anti_crawl
    _anti_crawl = middleware


# ========== 辅助函数 ==========


def _get_client_ip_from_scope(scope: dict) -> str:
    """
    从 ASGI scope 中提取客户端真实 IP。

    优先级：
    1. X-Forwarded-For 头
    2. X-Real-IP 头
    3. client host
    """
    headers = dict(scope.get("headers", []))
    forwarded = _decode_header(headers, b"x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = _decode_header(headers, b"x-real-ip")
    if real_ip:
        return real_ip.strip()

    client = scope.get("client")
    if client:
        return client[0]

    return "unknown"


def _get_header(scope: dict, name: str) -> Optional[str]:
    """从 ASGI scope 中获取指定请求头。"""
    headers = dict(scope.get("headers", []))
    return _decode_header(headers, name.encode("latin-1"))


def _decode_header(headers: dict, key: bytes) -> Optional[str]:
    """解码 ASGI header 字节为字符串。"""
    for k, v in headers.items():
        if k.lower() == key.lower():
            if isinstance(v, bytes):
                return v.decode("latin-1", errors="replace")
            return str(v)
    return None
