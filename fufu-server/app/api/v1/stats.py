"""
fufu新闻 - 访问统计接口
=========================
提供站点访问规模统计相关的 REST API 端点：

- GET    /stats/visits      → 站内实时访问统计（PV / UV / 趋势 / 热门页面）
- GET    /stats/baselines   → 外部统计口径基线列表（如托管平台访问统计）
- POST   /stats/baselines   → 登记一条外部统计口径基线
- DELETE /stats/baselines/{id} → 删除基线

统计口径：
- PV = 计入页面访问的请求数（is_page_view=True，剔除静态资源与接口请求）
- UV = 独立访客数，按客户端 IP 去重
- 外部基线与站内实时日志分开存放、分开呈现，各自标注来源，不做混合计算
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.access_log import AccessLog, VisitBaseline
from app.models.user import User
from app.schemas.response import success

logger = logging.getLogger("fufu.stats")

router = APIRouter(prefix="/stats", tags=["访问统计"])


class BaselineInput(BaseModel):
    """登记外部统计口径基线的请求体。"""

    pv: int = Field(..., ge=0, description="总访问量（页面访问次数）")
    uv: int = Field(..., ge=0, description="独立访客数（按 IP 去重）")
    period_start: str = Field("", description="统计周期起始日期 YYYY-MM-DD")
    period_end: str = Field("", description="统计周期结束日期 YYYY-MM-DD")
    source: str = Field("", description="数据来源说明")
    note: str = Field("", description="口径备注")


def mask_ip(ip: str) -> str:
    """
    IP 脱敏——展示时保留网段，隐藏主机位。

    IPv4 → 203.0.x.x；IPv6 → 前三段 + x。
    """
    if not ip:
        return "未知"
    if "." in ip and ip.count(".") == 3:
        parts = ip.split(".")
        return f"{parts[0]}.{parts[1]}.x.x"
    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:3]) + ":x"
    return ip


def _device_of(user_agent: str) -> str:
    """从 UA 判断访问设备类型。"""
    ua = (user_agent or "").lower()
    if not ua:
        return "未知"
    if "micromessenger" in ua or "wxwork" in ua:
        return "微信内置浏览器"
    if any(k in ua for k in ("iphone", "android", "mobile", "harmony")):
        return "移动端"
    if any(k in ua for k in ("ipad", "tablet")):
        return "平板"
    return "桌面端"


def _browser_of(user_agent: str) -> str:
    """从 UA 判断浏览器。"""
    ua = (user_agent or "").lower()
    if not ua:
        return "未知"
    if "edg/" in ua or "edge" in ua:
        return "Edge"
    if "chrome" in ua:
        return "Chrome"
    if "firefox" in ua:
        return "Firefox"
    if "safari" in ua:
        return "Safari"
    if "micromessenger" in ua:
        return "微信"
    return "其他"


@router.get("/visits")
async def get_visit_stats(
    days: int = Query(30, ge=1, le=365, description="统计最近多少天"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """
    站内实时访问统计。

    返回：
    - totals: 区间内 PV / UV / 人均访问深度
    - today: 今日 PV / UV
    - daily: 按天分布的 PV / UV
    - top_paths: 访问最多的页面
    - top_ips: 访问最多的 IP（脱敏）
    - devices / browsers: 设备与浏览器分布
    - baselines: 外部统计口径基线
    - combined: 基线合计 + 站内实时合计（分别标注，不混淆来源）
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ---- 区间总量 ----
    total_pv = await db.scalar(
        select(func.count(AccessLog.id)).where(
            AccessLog.created_at >= cutoff, AccessLog.is_page_view.is_(True)
        )
    )
    total_uv = await db.scalar(
        select(func.count(func.distinct(AccessLog.ip_address))).where(
            AccessLog.created_at >= cutoff, AccessLog.is_page_view.is_(True)
        )
    )

    # ---- 今日 ----
    today_pv = await db.scalar(
        select(func.count(AccessLog.id)).where(
            AccessLog.created_at >= today_start, AccessLog.is_page_view.is_(True)
        )
    )
    today_uv = await db.scalar(
        select(func.count(func.distinct(AccessLog.ip_address))).where(
            AccessLog.created_at >= today_start, AccessLog.is_page_view.is_(True)
        )
    )

    # ---- 按天分布（SQLite 按 UTC 日期分组） ----
    daily_rows = await db.execute(
        select(
            func.date(AccessLog.created_at).label("day"),
            func.count(AccessLog.id).label("pv"),
            func.count(func.distinct(AccessLog.ip_address)).label("uv"),
        )
        .where(AccessLog.created_at >= cutoff, AccessLog.is_page_view.is_(True))
        .group_by("day")
        .order_by("day")
    )
    daily = [
        {"date": row[0], "pv": row[1], "uv": row[2]} for row in daily_rows.fetchall()
    ]

    # ---- 热门页面 ----
    path_rows = await db.execute(
        select(AccessLog.path, func.count(AccessLog.id).label("pv"))
        .where(AccessLog.created_at >= cutoff, AccessLog.is_page_view.is_(True))
        .group_by(AccessLog.path)
        .order_by(func.count(AccessLog.id).desc())
        .limit(10)
    )
    top_paths = [{"path": row[0], "pv": row[1]} for row in path_rows.fetchall()]

    # ---- 来源 IP（脱敏） ----
    ip_rows = await db.execute(
        select(AccessLog.ip_address, func.count(AccessLog.id).label("pv"))
        .where(AccessLog.created_at >= cutoff, AccessLog.is_page_view.is_(True))
        .group_by(AccessLog.ip_address)
        .order_by(func.count(AccessLog.id).desc())
        .limit(10)
    )
    top_ips = [
        {"ip": mask_ip(row[0]), "pv": row[1]} for row in ip_rows.fetchall()
    ]

    # ---- 设备与浏览器分布 ----
    ua_rows = await db.execute(
        select(AccessLog.user_agent, func.count(AccessLog.id).label("pv"))
        .where(AccessLog.created_at >= cutoff, AccessLog.is_page_view.is_(True))
        .group_by(AccessLog.user_agent)
    )
    device_counter: dict[str, int] = {}
    browser_counter: dict[str, int] = {}
    for ua, pv in ua_rows.fetchall():
        device_counter[_device_of(ua)] = device_counter.get(_device_of(ua), 0) + pv
        browser_counter[_browser_of(ua)] = browser_counter.get(_browser_of(ua), 0) + pv

    # ---- 最近访问记录（实时日志流） ----
    recent_rows = await db.execute(
        select(
            AccessLog.created_at,
            AccessLog.method,
            AccessLog.path,
            AccessLog.status_code,
            AccessLog.ip_address,
            AccessLog.user_agent,
            AccessLog.is_page_view,
        )
        .order_by(AccessLog.created_at.desc(), AccessLog.id.desc())
        .limit(20)
    )
    recent = [
        {
            "time": row[0].isoformat() if row[0] else "",
            "method": row[1],
            "path": row[2],
            "status": row[3],
            "ip": mask_ip(row[4]),
            "device": _device_of(row[5]),
            "is_page_view": bool(row[6]),
        }
        for row in recent_rows.fetchall()
    ]

    # ---- 外部统计口径基线 ----
    baseline_rows = await db.execute(
        select(VisitBaseline).order_by(VisitBaseline.period_end.desc(), VisitBaseline.id.desc())
    )
    baselines = [
        {
            "id": b.id,
            "pv": b.pv,
            "uv": b.uv,
            "period_start": b.period_start,
            "period_end": b.period_end,
            "source": b.source,
            "note": b.note,
            "depth": round(b.pv / b.uv, 2) if b.uv else 0,
            "created_at": b.created_at.isoformat() if b.created_at else "",
        }
        for b in baseline_rows.scalars().all()
    ]
    baseline_pv = sum(b.pv for b in baselines)
    baseline_uv = sum(b.uv for b in baselines)

    pv = int(total_pv or 0)
    uv = int(total_uv or 0)
    data = {
        "totals": {
            "pv": pv,
            "uv": uv,
            "depth": round(pv / uv, 2) if uv else 0,
            "days": days,
        },
        "today": {"pv": int(today_pv or 0), "uv": int(today_uv or 0)},
        "daily": daily,
        "top_paths": top_paths,
        "top_ips": top_ips,
        "devices": [{"name": k, "value": v} for k, v in sorted(device_counter.items(), key=lambda x: -x[1])],
        "browsers": [{"name": k, "value": v} for k, v in sorted(browser_counter.items(), key=lambda x: -x[1])],
        "recent": recent,
        "baselines": baselines,
        "combined": {
            "pv": baseline_pv + pv,
            "uv": baseline_uv + uv,
            "baseline_pv": baseline_pv,
            "baseline_uv": baseline_uv,
            "live_pv": pv,
            "live_uv": uv,
        },
        "generated_at": now.isoformat(),
    }
    return success(data)


@router.get("/baselines")
async def list_baselines(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """列出所有外部统计口径基线。"""
    rows = await db.execute(select(VisitBaseline).order_by(VisitBaseline.id.desc()))
    items = [
        {
            "id": b.id,
            "pv": b.pv,
            "uv": b.uv,
            "period_start": b.period_start,
            "period_end": b.period_end,
            "source": b.source,
            "note": b.note,
            "depth": round(b.pv / b.uv, 2) if b.uv else 0,
            "created_at": b.created_at.isoformat() if b.created_at else "",
        }
        for b in rows.scalars().all()
    ]
    return success(items)


@router.post("/baselines")
async def create_baseline(
    payload: BaselineInput,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """登记一条外部统计口径基线。"""
    baseline = VisitBaseline(
        pv=payload.pv,
        uv=payload.uv,
        period_start=payload.period_start,
        period_end=payload.period_end,
        source=payload.source,
        note=payload.note,
    )
    db.add(baseline)
    await db.commit()
    logger.info(
        f"登记访问统计基线: PV={payload.pv}, UV={payload.uv}, 来源={payload.source or '未填写'}"
    )
    return success({"id": baseline.id}, "基线已登记")
