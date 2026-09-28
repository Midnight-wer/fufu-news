"""
fufu新闻 - 蜜罐端点
====================
伪装成普通 API 端点的陷阱，用于诱捕爬虫和扫描器。

正常用户不会访问这些路径（前端不会调用），但爬虫/扫描器会通过
路径枚举发现并请求它们。任何访问这些端点的 IP 将被自动封禁。

端点列表（均返回 403）：
- /api/v1/feed          — 伪装成 RSS feed 端点
- /api/v1/admin/users   — 伪装成管理端点
- /api/v1/wp-admin      — 伪装成 WordPress 管理入口
- /api/v1/.env          — 伪装成环境配置文件泄露
- /api/v1/debug         — 伪装成调试端点
- /api/v1/backup        — 伪装成备份端点
"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.anti_crawl import get_anti_crawl

logger = logging.getLogger("fufu.security")

router = APIRouter(tags=["蜜罐"])

# 蜜罐路径列表（爬虫扫描器常探测的路径）
_HONEYPOT_PATHS = [
    "/feed",
    "/admin/users",
    "/wp-admin",
    "/.env",
    "/debug",
    "/backup",
    "/config",
    "/phpinfo",
    "/api",
    "/admin",
    "/wp-login",
    "/console",
    "/actuator",
    "/swagger",
    "/graphql",
    "/api/v1/feed",
    "/api/v1/admin",
    "/api/v1/.env",
    "/api/v1/debug",
    "/api/v1/backup",
    "/api/v1/config",
    "/api/v1/phpinfo",
    "/api/v1/console",
    "/api/v1/actuator",
    "/api/v1/swagger",
    "/api/v1/graphql",
]


def _get_client_ip(request: Request) -> str:
    """从请求中提取客户端真实 IP。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"


@router.get("/feed")
async def honeypot_feed(request: Request):
    """蜜罐：伪装 RSS feed 端点。"""
    return await _honeypot_response(request, "feed")


@router.get("/admin/users")
async def honeypot_admin_users(request: Request):
    """蜜罐：伪装管理用户列表。"""
    return await _honeypot_response(request, "admin/users")


@router.get("/wp-admin")
async def honeypot_wp_admin(request: Request):
    """蜜罐：伪装 WordPress 管理入口。"""
    return await _honeypot_response(request, "wp-admin")


@router.get("/.env")
async def honeypot_env(request: Request):
    """蜜罐：伪装 .env 文件泄露。"""
    return await _honeypot_response(request, ".env")


@router.get("/debug")
async def honeypot_debug(request: Request):
    """蜜罐：伪装调试端点。"""
    return await _honeypot_response(request, "debug")


@router.get("/backup")
async def honeypot_backup(request: Request):
    """蜜罐：伪装备份端点。"""
    return await _honeypot_response(request, "backup")


@router.get("/config")
async def honeypot_config(request: Request):
    """蜜罐：伪装配置端点。"""
    return await _honeypot_response(request, "config")


@router.get("/phpinfo")
async def honeypot_phpinfo(request: Request):
    """蜜罐：伪装 PHP info。"""
    return await _honeypot_response(request, "phpinfo")


@router.get("/api")
async def honeypot_api(request: Request):
    """蜜罐：伪装旧版 API 入口。"""
    return await _honeypot_response(request, "api")


@router.get("/admin")
async def honeypot_admin(request: Request):
    """蜜罐：伪装管理入口。"""
    return await _honeypot_response(request, "admin")


@router.get("/wp-login")
async def honeypot_wp_login(request: Request):
    """蜜罐：伪装 WordPress 登录。"""
    return await _honeypot_response(request, "wp-login")


@router.get("/console")
async def honeypot_console(request: Request):
    """蜜罐：伪装管理控制台。"""
    return await _honeypot_response(request, "console")


@router.get("/actuator")
async def honeypot_actuator(request: Request):
    """蜜罐：伪装 Spring Actuator。"""
    return await _honeypot_response(request, "actuator")


@router.get("/swagger")
async def honeypot_swagger(request: Request):
    """蜜罐：伪装 Swagger 文档。"""
    return await _honeypot_response(request, "swagger")


@router.get("/graphql")
async def honeypot_graphql(request: Request):
    """蜜罐：伪装 GraphQL 端点。"""
    return await _honeypot_response(request, "graphql")


# POST 变体（部分扫描器会用 POST 探测）
@router.post("/feed")
@router.post("/admin/users")
@router.post("/wp-admin")
@router.post("/.env")
@router.post("/debug")
@router.post("/backup")
@router.post("/config")
@router.post("/phpinfo")
@router.post("/api")
@router.post("/admin")
@router.post("/wp-login")
@router.post("/console")
@router.post("/actuator")
@router.post("/swagger")
@router.post("/graphql")
async def honeypot_post(request: Request):
    """蜜罐：POST 请求变体（通用）。"""
    return await _honeypot_response(request, request.url.path)


async def _honeypot_response(request: Request, trap_name: str) -> JSONResponse:
    """
    处理蜜罐请求：封禁 IP 并返回 403。

    Args:
        request: FastAPI Request 对象
        trap_name: 触发的陷阱名称（用于日志）

    Returns:
        403 JSON 响应
    """
    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "(无)")

    logger.warning(
        f"蜜罐触发: IP={ip} UA={ua[:100]} 陷阱={trap_name} 路径={request.url.path}"
    )

    # 通知反爬虫中间件封禁此 IP
    anti_crawl = get_anti_crawl()
    if anti_crawl:
        await anti_crawl.block_ip(ip, reason=f"honeypot:{trap_name}")

    return JSONResponse(
        status_code=403,
        content={
            "code": 403,
            "data": [],
            "message": "访问被拒绝",
        },
    )
