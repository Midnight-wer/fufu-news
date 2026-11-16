"""
fufu新闻 - 全局异常处理
==========================
把三类异常统一成约定信封，并**保持 HTTP 状态码与业务 code 一致**。

背景：此前 main.py 未注册任何 exception_handler，导致
1. 未捕获异常由 Starlette 返回纯文本 `Internal Server Error`，前端按 JSON 解析直接崩；
2. 多处 `return error(code=500)` 却带着 HTTP 200，前端按状态码判断的分支全部失效。

统一后的错误响应：
    HTTP <status> + {"code": <status>, "data": [], "message": "<中文提示>", "detail": <原文>}

关键兼容点：
- **保留 `detail` 字段** —— 前端 useAI.ts / SourcesPage.tsx 读的是 `err.response.data.detail`，
  去掉会让所有中文错误提示退化成通用文案。
- HTTP 状态码 == code，与 app/core/rate_limit.py 已用的 429 信封格式完全一致。
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("fufu.exceptions")

# 未捕获异常是否把摘要回传给前端。生产环境建议置 False。
EXPOSE_ERROR_DETAIL = True

# 需要静默处理的噪声异常（对端断连等，不必打 ERROR）
_QUIET_EXC_NAMES = {"ConnectionResetError", "ClientDisconnect"}


def _body(code: int, message: str, detail=None) -> dict:
    """构造统一错误信封。data 恒为 []，符合项目约定。"""
    return {"code": code, "data": [], "message": message, "detail": detail}


def _message_of(detail, fallback: str) -> str:
    """detail 可能是 str，也可能是 dict/list，message 只取字符串形式。"""
    return detail if isinstance(detail, str) and detail else fallback


def register_exception_handlers(app: FastAPI) -> None:
    """
    在 app 上注册异常处理器。幂等，可重复调用。

    注册顺序无关：FastAPI/Starlette 会按异常类型分派。
    """
    # ---- 业务 HTTPException（含 401/403/404/502 等） ----
    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException):
        code = exc.status_code
        message = _message_of(exc.detail, "请求没有成功呢～")
        log = logger.error if code >= 500 else logger.info
        log(f"业务异常 {request.method} {request.url.path} -> {code}: {exc.detail}")
        return JSONResponse(
            status_code=code,
            content=_body(code, message, exc.detail),
            headers=getattr(exc, "headers", None),
        )

    # ---- 路由不存在等 Starlette 原生 HTTP 异常 ----
    @app.exception_handler(StarletteHTTPException)
    async def _starlette_http_handler(request: Request, exc: StarletteHTTPException):
        code = exc.status_code
        message = _message_of(exc.detail, "找不到这个页面呢～")
        if code >= 500:
            logger.error(f"HTTP 异常 {request.method} {request.url.path} -> {code}")
        return JSONResponse(
            status_code=code,
            content=_body(code, message, exc.detail),
            headers=getattr(exc, "headers", None),
        )

    # ---- 请求参数校验失败 ----
    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        errors = jsonable_encoder(exc.errors())
        logger.info(f"参数校验失败 {request.method} {request.url.path}: {errors}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_body(422, "请求参数不完整或格式不对哦～", errors),
        )

    # ---- 兜底：任何未捕获异常 ----
    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        name = type(exc).__name__
        if name in _QUIET_EXC_NAMES:
            logger.debug(f"连接中断 {request.method} {request.url.path}: {exc}")
        else:
            logger.error(
                f"未捕获异常 {request.method} {request.url.path}: {name}: {exc}",
                exc_info=exc,
            )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_body(
                500,
                "服务器开小差了～",
                f"{name}: {exc}"[:500] if EXPOSE_ERROR_DETAIL else None,
            ),
        )
