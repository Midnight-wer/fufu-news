"""
fufu新闻 - 站点访问日志数据模型
=================================
定义 AccessLog（访问日志）和 VisitBaseline（访问规模基线）ORM 模型。

AccessLog: 每条 HTTP 页面请求一行，记录访客 IP、路径、状态码与 UA，
           用于统计 PV / UV、日访问趋势、热门页面与来源分布。
VisitBaseline: 登记托管平台等外部统计口径给出的访问规模基线
           （例如平台统计后台导出的 PV / UV），与站内实时日志分开存放，
           展示时明确标注数据来源，避免与站内日志数据混淆。
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccessLog(Base):
    """
    访问日志 ORM 模型——对应数据库中的 access_log 表。

    字段说明：
    - id: 主键，自增
    - path: 请求路径（不含查询串）
    - method: HTTP 方法
    - status_code: 响应状态码
    - ip_address: 访客 IP（经反向代理时取 X-Forwarded-For 首个公网地址）
    - user_agent: 浏览器 UA（截断存储）
    - referer: 来源页（截断存储）
    - is_page_view: 是否计入 PV 的页面访问（静态资源与接口请求记 False）
    - duration_ms: 请求耗时（毫秒）
    - created_at: 访问时间（默认当前 UTC 时间）
    """
    __tablename__ = "access_log"
    __table_args__ = (
        Index("idx_access_log_created_at", "created_at"),
        Index("idx_access_log_ip_time", "ip_address", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(512), default="", index=True)
    method: Mapped[str] = mapped_column(String(10), default="GET")
    status_code: Mapped[int] = mapped_column(Integer, default=200)
    ip_address: Mapped[str] = mapped_column(String(45), default="", index=True)
    user_agent: Mapped[str] = mapped_column(String(512), default="")
    referer: Mapped[str] = mapped_column(String(512), default="")
    is_page_view: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )


class VisitBaseline(Base):
    """
    访问规模基线 ORM 模型——对应数据库中的 visit_baseline 表。

    用于登记外部统计口径（例如托管平台统计后台）给出的访问规模，
    与 AccessLog 的站内实时统计分开呈现，各自标注来源与统计周期。

    字段说明：
    - id: 主键，自增
    - pv: 总访问量（页面访问次数）
    - uv: 独立访客数（按 IP 去重）
    - period_start / period_end: 统计周期起止日期
    - source: 数据来源说明（如「托管平台访问统计」）
    - note: 备注（口径说明、导出方式等）
    - created_at: 登记时间
    """
    __tablename__ = "visit_baseline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pv: Mapped[int] = mapped_column(Integer, default=0)
    uv: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[str] = mapped_column(String(20), default="")
    period_end: Mapped[str] = mapped_column(String(20), default="")
    source: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
