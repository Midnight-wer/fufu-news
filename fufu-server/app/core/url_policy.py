"""
fufu新闻 - URL 安全策略（SSRF 防护）
======================================
对「由用户提供的、服务端会去请求的外网地址」做校验，阻断：
- 非 http/https 协议（file://、gopher://、ftp:// 等）
- 回环地址、私有网段、链路本地、云元数据地址、IPv6 私有地址
- 缺少主机名、空地址

用途：
- app/api/v1/rss_proxy.py 的 /proxy、/validate、/validate-all（订阅源地址本应是公网，但仍需拦内网）
- app/api/v1/ai.py 的自定义 base_url（防止把服务端真实 Key 打向任意地址）

设计取舍（用户要求「功能保留 + 加约束」）：
公网 RSS / 已登记域名一律放行，只拦内网与危险协议，不破坏正常订阅源添加。
"""
import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger("fufu.security.url")

# 允许通过校验的协议
_ALLOWED_SCHEMES = ("http", "https")

# 私有 / 保留网段（IPv4）
_BLOCKED_V4_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),        # 本网络
    ipaddress.ip_network("10.0.0.0/8"),       # 私有 A 类
    ipaddress.ip_network("100.64.0.0/10"),    # CGNAT
    ipaddress.ip_network("127.0.0.0/8"),      # 回环
    ipaddress.ip_network("169.254.0.0/16"),   # 链路本地（含云元数据 169.254.169.254）
    ipaddress.ip_network("172.16.0.0/12"),    # 私有 B 类
    ipaddress.ip_network("192.0.0.0/24"),     # IETF 协议分配
    ipaddress.ip_network("192.168.0.0/16"),   # 私有 C 类
    ipaddress.ip_network("198.18.0.0/15"),    # 基准测试
    ipaddress.ip_network("224.0.0.0/4"),      # 组播
    ipaddress.ip_network("240.0.0.0/4"),      # 保留（含广播）
)

# 明确的主机名黑名单（云厂商元数据服务）
_BLOCKED_HOSTNAMES = frozenset({"metadata", "metadata.google.internal", "instance-data"})


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    """判断 IP 是否落在需要阻断的范围内。"""
    if isinstance(ip, ipaddress.IPv4Address):
        return any(ip in net for net in _BLOCKED_V4_NETWORKS)
    if isinstance(ip, ipaddress.IPv6Address):
        # ::1 回环、fc00::/7 唯一本地、fe80::/10 链路本地、::ffff:x 映射的 IPv4
        if ip == ipaddress.IPv6Address("::1"):
            return True
        if ip in ipaddress.ip_network("fc00::/7"):
            return True
        if ip in ipaddress.ip_network("fe80::/10"):
            return True
        mapped = getattr(ip, "ipv4_mapped", None)
        if mapped is not None:
            return _is_blocked_ip(mapped)
        return False
    return True


def validate_public_url(raw_url: str) -> tuple[bool, str]:
    """
    校验一个用户提供的 URL 是否允许被服务端请求。

    返回:
        (是否通过, 说明文案)。未通过时说明文案可直接作为 400 的 message。
    """
    if not raw_url or not isinstance(raw_url, str):
        return False, "地址不能为空"

    url = raw_url.strip()
    if len(url) > 2048:
        return False, "地址太长了（上限 2048 字符）"

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "地址格式无法解析"

    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        return False, f"仅支持 http/https 协议（当前是 {scheme or '空'}）"

    host = parsed.hostname
    if not host:
        return False, "地址缺少主机名"

    host_l = host.lower().strip("[]")
    if host_l in _BLOCKED_HOSTNAMES or host_l.endswith(".internal"):
        return False, "不允许访问内网或云元数据地址"

    # 直接是 IP 字面量：立刻判定
    try:
        ip = ipaddress.ip_address(host_l)
    except ValueError:
        ip = None

    if ip is not None:
        if _is_blocked_ip(ip):
            return False, "不允许访问内网、回环或云元数据地址"
        return True, "ok"

    # 是域名：解析后判定（防 DNS rebinding / 域名指向内网）
    try:
        infos = socket.getaddrinfo(host_l, None)
    except Exception:
        # 解析失败可能是境外源 + 当前网络不通，交给后续真实请求报错，此处放行
        logger.debug(f"URL 解析失败，交由请求阶段处理: {host_l}")
        return True, "ok"

    for info in infos:
        try:
            resolved = ipaddress.ip_address(info[4][0])
        except (ValueError, IndexError):
            continue
        if _is_blocked_ip(resolved):
            return False, "该域名解析到内网地址，已拒绝"

    return True, "ok"


def assert_public_url(raw_url: str) -> None:
    """
    校验失败时直接抛 ValueError，供调用方转成 HTTPException(400)。
    """
    ok, reason = validate_public_url(raw_url)
    if not ok:
        raise ValueError(reason)


def host_allowed_for_ai(raw_url: str, allowed_hosts: list[str]) -> tuple[bool, str]:
    """
    AI 自定义 base_url 的额外校验：必须通过 SSRF 检查 **且** 主机名在白名单内。

    这是「功能保留 + 加约束」的关键：用户仍能自定义 AI 后端，
    但只能指向显式登记过的域名，且不允许把服务端 Key 送到未登记地址。
    """
    ok, reason = validate_public_url(raw_url)
    if not ok:
        return False, reason

    parsed = urlparse(raw_url.strip())
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "地址缺少主机名"

    for allowed in allowed_hosts:
        a = (allowed or "").strip().lower()
        if not a:
            continue
        # 精确匹配，或 *.example.com 形式的后缀匹配
        if host == a:
            return True, "ok"
        if a.startswith("*.") and host.endswith(a[1:]):
            return True, "ok"
        if a.startswith(".") and host.endswith(a):
            return True, "ok"

    return False, (
        f"AI 后端域名 {host} 未在白名单中，"
        f"请在 .env 的 AI_ALLOWED_HOSTS 中登记后重试"
    )
