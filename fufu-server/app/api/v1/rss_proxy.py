"""
RSS 代理 + 订阅源验证 + 健康监控

端点:
- POST /api/v1/sources/proxy — 代理抓取 RSS，绕过 CORS/UA 限制
- POST /api/v1/sources/validate — 验证单个订阅源可用性
- POST /api/v1/sources/validate-all — 批量验证所有订阅源
- POST /api/v1/sources/opml-export — 导出 OPML
- POST /api/v1/sources/opml-import — 导入 OPML
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

import feedparser
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.url_policy import validate_public_url
from app.models.source import Source
from app.models.user import User

logger = logging.getLogger("fufu.proxy")
router = APIRouter(tags=["RSS代理"])

# 浏览器 UA 轮换池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]
_ua_idx = 0


def _next_ua() -> str:
    global _ua_idx
    ua = USER_AGENTS[_ua_idx % len(USER_AGENTS)]
    _ua_idx += 1
    return ua


# ====== 健康统计内存存储 ======
_feed_health: dict[int, dict] = {}


def _record_health(source_id: int, success: bool, latency: float):
    h = _feed_health.get(source_id, {"success": 0, "fail": 0, "latencies": [], "consecutive_fails": 0, "last_ok": None})
    if success:
        h["success"] += 1
        h["latencies"].append(latency)
        h["consecutive_fails"] = 0
        h["last_ok"] = datetime.now(timezone.utc).isoformat()
    else:
        h["fail"] += 1
        h["consecutive_fails"] += 1
    _feed_health[source_id] = h


def get_feed_health(source_id: int) -> dict:
    h = _feed_health.get(source_id, {"success": 0, "fail": 0, "latencies": [], "consecutive_fails": 0, "last_ok": None})
    total = h["success"] + h["fail"]
    lats = h["latencies"][-20:]
    return {
        **h,
        "total": total,
        "success_rate": round(h["success"] / total * 100, 1) if total > 0 else 0,
        "avg_latency": round(sum(lats) / len(lats), 2) if lats else 0,
        "is_healthy": h["consecutive_fails"] < 3,
    }


# ====== 请求模型 ======

class ProxyRequest(BaseModel):
    url: str
    timeout: int = 15


class ValidateRequest(BaseModel):
    url: str
    timeout: int = 15


class OpmlImportRequest(BaseModel):
    xml: str


# ====== 地址安全校验（SSRF 防护） ======

def _guard_url(raw_url: str) -> None:
    """
    校验用户提供的待抓取地址，拦截内网 / 云元数据 / 非 http(s) 协议。

    修复 P0：/proxy 原本把任意 URL 的响应体**原文回显**给前端，
    认证用户即可读取内网任意 HTTP 资源（Redis、ES、管理后台、169.254.169.254）；
    /validate 用状态码差异还能当端口扫描器用。

    公网 RSS 地址不受影响，添加订阅源的既有流程完全保留。
    """
    ok, reason = validate_public_url(raw_url)
    if not ok:
        logger.warning(f"订阅源地址被拒绝: {str(raw_url)[:120]!r} — {reason}")
        raise HTTPException(status_code=400, detail=reason)


# ====== RSS 代理 ======

@router.post("/proxy")
async def proxy_feed(
    req: ProxyRequest,
    _user: User = Depends(get_current_user),
):
    """代理抓取 RSS — 绕过前端 CORS/UA 限制"""
    start = time.time()
    _guard_url(req.url)
    try:
        async with httpx.AsyncClient(timeout=req.timeout) as client:
            resp = await client.get(
                req.url,
                headers={
                    "User-Agent": _next_ua(),
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
                    "Referer": "https://www.google.com/",
                },
                follow_redirects=True,
            )
            resp.raise_for_status()
            latency = time.time() - start
            return {
                "content": resp.text,
                "status_code": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "latency": round(latency, 2),
            }
    except httpx.TimeoutException:
        return {"error": "timeout", "detail": f"请求超时 ({req.timeout}s)"}
    except httpx.HTTPStatusError as e:
        return {"error": "http_error", "status_code": e.response.status_code, "detail": str(e)}
    except Exception as e:
        return {"error": "connection_error", "detail": str(e)[:300]}


# ====== 源验证 ======

@router.post("/validate")
async def validate_source(
    req: ValidateRequest,
    _user: User = Depends(get_current_user),
):
    """验证单个 RSS 源 — 连通性 + 格式 + 字段完整性"""
    issues = []
    start = time.time()
    _guard_url(req.url)

    # 1. 连通性测试
    try:
        async with httpx.AsyncClient(timeout=req.timeout) as client:
            resp = await client.get(
                req.url,
                headers={"User-Agent": _next_ua()},
                follow_redirects=True,
            )
            status = resp.status_code
            latency = round(time.time() - start, 2)
            if status == 404:
                issues.append({"type": "not_found", "detail": "链接 404 — 源已失效"})
            elif status == 403:
                issues.append({"type": "blocked", "detail": "403 禁止访问 — 可能被 WAF 拦截"})
            elif status == 429:
                issues.append({"type": "rate_limited", "detail": "429 请求过频 — 需要降低频率"})
            elif status >= 500:
                issues.append({"type": "server_error", "detail": f"服务器错误 {status}"})
            elif status != 200:
                issues.append({"type": "http_error", "detail": f"HTTP {status}"})

            raw = resp.text
    except httpx.TimeoutException:
        return {"status": "timeout", "issues": [{"type": "timeout", "detail": "连接超时"}], "fields_ok": False}
    except httpx.ConnectError:
        return {"status": "unreachable", "issues": [{"type": "unreachable", "detail": "无法建立连接 — DNS/网络问题"}], "fields_ok": False}
    except Exception as e:
        return {"status": "error", "issues": [{"type": "error", "detail": str(e)[:200]}], "fields_ok": False}

    # 2. XML/RSS 格式校验
    # feedparser 是同步解析，且此端点在用户请求路径上（点「检测」即触发），
    # 阻塞事件循环的影响比后台抓取更直接，故同样卸载到线程池。
    parsed = await asyncio.to_thread(feedparser.parse, raw)
    if parsed.bozo:
        issues.append({"type": "parse_error", "detail": f"格式解析异常: {str(parsed.bozo_exception)[:200]}"})

    entries = parsed.entries
    if not entries:
        issues.append({"type": "no_entries", "detail": "Feed 中没有文章条目"})

    # 3. 字段完整性检查
    fields_ok = True
    missing_fields = set()
    for entry in entries[:5]:
        if not entry.get("title"):
            missing_fields.add("title")
        if not entry.get("link"):
            missing_fields.add("link")
        if not entry.get("published") and not entry.get("updated"):
            missing_fields.add("published")
    if missing_fields:
        fields_ok = False
        issues.append({"type": "missing_fields", "detail": f"缺少字段: {', '.join(sorted(missing_fields))}"})

    status = "ok" if not issues else "warning"
    return {
        "status": status,
        "issues": issues,
        "entry_count": len(entries),
        "latency": latency,
        "fields_ok": fields_ok,
    }


# ====== 批量验证 ======

@router.post("/validate-all")
async def validate_all_sources(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """批量验证所有订阅源，更新健康状态"""
    result = await db.execute(select(Source))
    sources = result.scalars().all()
    results = []

    for src in sources:
        start = time.time()
        # 库里的源理论上都是公网地址，仍做一次校验，避免历史脏数据
        # 或手工改库后把 validate-all 变成内网扫描器
        ok_url, reason = validate_public_url(src.url)
        if not ok_url:
            results.append({
                "id": src.id, "name": src.name, "url": src.url,
                "status": "error", "detail": f"地址被安全策略拒绝: {reason}",
                "health": get_feed_health(src.id),
            })
            continue
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    src.url,
                    headers={"User-Agent": _next_ua()},
                    follow_redirects=True,
                )
                latency = round(time.time() - start, 2)
                ok = resp.status_code == 200
                _record_health(src.id, ok, latency)
                results.append({
                    "id": src.id, "name": src.name, "url": src.url,
                    "status": "ok" if ok else f"HTTP {resp.status_code}",
                    "latency": latency,
                    "health": get_feed_health(src.id),
                })
        except Exception as e:
            _record_health(src.id, False, 0)
            results.append({
                "id": src.id, "name": src.name, "url": src.url,
                "status": "error",
                "detail": str(e)[:150],
                "health": get_feed_health(src.id),
            })

    # 标记连续失败 3+ 次的源
    unhealthy = [r for r in results if r["health"].get("consecutive_fails", 0) >= 3]
    return {"total": len(results), "unhealthy": len(unhealthy), "results": results}


@router.get("/health/{source_id}")
async def source_health(
    source_id: int,
    _user: User = Depends(get_current_user),
):
    """
    获取单个源的运行状况统计。

    前端订阅源卡片的状态指示灯会用到它（此前 UI 上写死了 "unknown"）。
    """
    return get_feed_health(source_id)


# ====== OPML 导出 ======

@router.post("/opml-export")
async def opml_export(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """导出所有订阅源为 OPML XML"""
    result = await db.execute(select(Source))
    sources = result.scalars().all()

    # 安全修复：原先直接用 f-string 拼接 XML，而订阅源名称/地址由用户可控，
    # 名称里带引号或 `><outline ...` 就能注入任意节点（可指向攻击者的 xmlUrl）。
    # 这里改用 xml.sax.saxutils.escape 做属性转义。
    from urllib.parse import urlparse as _urlparse
    from xml.sax.saxutils import escape as _xml_escape

    def _attr(v) -> str:
        return _xml_escape(str(v or ""), {'"': "&quot;", "'": "&apos;"})

    outlines = []
    for src in sources:
        url = str(src.url or "")
        # 只导出 http/https，避免把 file:// 之类的危险地址写进 OPML
        if _urlparse(url).scheme not in ("http", "https"):
            continue
        outlines.append(
            f'      <outline text="{_attr(src.name)}" title="{_attr(src.name)}" '
            f'type="rss" xmlUrl="{_attr(url)}" />'
        )

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<opml version="2.0">\n'
    xml += '  <head><title>fufu新闻 订阅导出</title></head>\n'
    xml += '  <body>\n'
    xml += '\n'.join(outlines)
    xml += '\n  </body>\n</opml>'

    return {"xml": xml, "count": len(outlines)}


# ====== OPML 导入 ======

@router.post("/opml-import")
async def opml_import(
    req: OpmlImportRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """从 OPML XML 批量导入订阅源"""
    import re
    pattern = re.compile(r'<outline[^>]*xmlUrl="([^"]*)"[^>]*text="([^"]*)"')
    matches = pattern.findall(req.xml)
    if not matches:
        pattern2 = re.compile(r'<outline[^>]*text="([^"]*)"[^>]*xmlUrl="([^"]*)"')
        matches = [(url, name) for name, url in pattern2.findall(req.xml)]

    imported = 0
    skipped = 0
    for url, name in matches:
        existing = (await db.execute(select(Source).where(Source.url == url))).scalar_one_or_none()
        if existing:
            skipped += 1
            continue
        src = Source(name=name, url=url, source_type="rss", folder="导入")
        db.add(src)
        imported += 1

    await db.commit()
    return {"imported": imported, "skipped": skipped, "total": len(matches)}
