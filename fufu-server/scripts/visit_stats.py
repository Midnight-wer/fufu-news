"""
从访问日志复算 PV / UV —— 让「访问量、独立访客」可被第三方独立复核。

用法：
    python scripts/visit_stats.py logs/access.log
    python scripts/visit_stats.py logs/access.log --max-daily 500 --json out.json

支持格式：
- nginx / Apache combined：203.0.113.7 - - [16/Nov/2026:13:55:36 +0800] "GET /articles HTTP/1.1" 200 512 "UA" "referer"
- uvicorn：INFO:     203.0.113.7:59258 - "GET /articles HTTP/1.1" 200 OK
- 本项目自写的 PAGEVIEW 记录："203.0.113.7 - - [...] "PAGEVIEW /articles HTTP/1.1" 200 0 "UA" "referer"

统计口径（与后台「访问统计」页一致）：
- PV：计入页面访问的请求数（剔除静态资源与接口请求）
- UV：独立访客数，按客户端 IP 去重
- 清洗：剔除爬虫 UA、内网/回环地址、单日请求超过阈值的异常 IP
"""
import argparse
import ipaddress
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG = PROJECT_ROOT / "logs" / "access.log"

# nginx combined 格式
NGINX_PATTERN = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>[A-Z]+)\s+(?P<path>[^ "]+)(?:\s+HTTP/[\d.]+)?"\s+'
    r'(?P<status>\d{3})\s+(?P<size>\S+)\s+"(?P<ua>[^"]*)"(?:\s+"(?P<ref>[^"]*)")?'
)

# uvicorn 格式
UVICORN_PATTERN = re.compile(
    r'^(?:INFO:\s+)?(?P<ip>[0-9a-fA-F:.]+):\d+\s+-\s+'
    r'"(?P<method>[A-Z]+)\s+(?P<path>[^ "]+)(?:\s+HTTP/[\d.]+)?"\s+'
    r'(?P<status>\d{3})'
)

# 爬虫 UA 特征（不收录 headlesschrome：它仍是真实浏览器内核，
# 自查与自动化走查也用它，剔除会导致与后台统计口径对不上）
BOT_PATTERN = re.compile(
    r"bot|spider|crawler|slurp|bingpreview|lighthouse|curl|wget|python-requests|uptime|monitoring",
    re.IGNORECASE,
)

# 不计入 PV 的静态资源后缀与接口前缀
STATIC_SUFFIXES = (
    ".js", ".mjs", ".css", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".webm",
)
NON_PAGE_PREFIXES = ("/api/", "/docs", "/redoc", "/openapi.json")

NGINX_TIME_FORMAT = "%d/%b/%Y:%H:%M:%S %z"


def is_public_ip(value: str) -> bool:
    """判断是否为公网地址（排除回环、内网、保留段）。"""
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


def is_page_view(method: str, path: str) -> bool:
    """是否计入 PV 的页面访问。"""
    if method == "PAGEVIEW":
        return True
    lowered = path.lower()
    if lowered.startswith(NON_PAGE_PREFIXES):
        return False
    if lowered.endswith(STATIC_SUFFIXES):
        return False
    if lowered in {"/health", "/favicon.ico", "/robots.txt", "/sitemap.xml"}:
        return False
    return True


def parse_line(line: str) -> dict | None:
    """解析一行访问日志，解析不了返回 None。"""
    line = line.strip()
    if not line:
        return None

    match = NGINX_PATTERN.match(line)
    if match:
        data = match.groupdict()
        raw_time = data.get("time") or ""
        moment = None
        try:
            moment = datetime.strptime(raw_time, NGINX_TIME_FORMAT)
        except ValueError:
            moment = None
        return {
            "ip": data["ip"],
            "method": data["method"],
            "path": data["path"],
            "status": int(data["status"]),
            "ua": data.get("ua") or "",
            "day": moment.date().isoformat() if moment else "unknown",
        }

    match = UVICORN_PATTERN.match(line)
    if match:
        data = match.groupdict()
        return {
            "ip": data["ip"],
            "method": data["method"],
            "path": data["path"],
            "status": int(data["status"]),
            "ua": "",
            "day": "unknown",
        }

    return None


def analyze(
    records: list[dict],
    max_daily: int = 500,
    exclude_private: bool = True,
) -> dict:
    """
    按统计口径清洗并统计 PV / UV。

    参数:
        records: parse_line 产出的记录列表
        max_daily: 单日请求数超过该值的 IP 视为异常流量并剔除
        exclude_private: 是否剔除内网 / 回环地址（本地验证日志时可关闭）

    返回:
        统计结果字典（含剔除原因计数，便于复核）
    """
    excluded = Counter()
    cleaned: list[dict] = []

    for record in records:
        if BOT_PATTERN.search(record.get("ua") or ""):
            excluded["爬虫 UA"] += 1
            continue
        if exclude_private and not is_public_ip(record["ip"]):
            excluded["内网/回环地址"] += 1
            continue
        cleaned.append(record)

    # 剔除单日高频 IP
    per_day = Counter((r["day"], r["ip"]) for r in cleaned)
    noisy = {key for key, count in per_day.items() if count > max_daily}
    final = [r for r in cleaned if (r["day"], r["ip"]) not in noisy]
    excluded["单日高频 IP"] = len(cleaned) - len(final)

    page_views = [r for r in final if is_page_view(r["method"], r["path"])]
    excluded["非页面请求（接口/静态资源）"] = len(final) - len(page_views)

    ips = {r["ip"] for r in page_views}
    pv = len(page_views)
    uv = len(ips)

    daily_pv = Counter(r["day"] for r in page_views)
    daily_uv: Counter = Counter()
    seen: dict[str, set] = {}
    for r in page_views:
        seen.setdefault(r["day"], set()).add(r["ip"])
    for day, ip_set in seen.items():
        daily_uv[day] = len(ip_set)

    return {
        "pv": pv,
        "uv": uv,
        "depth": round(pv / uv, 2) if uv else 0,
        "total_lines": len(records),
        "excluded": dict(excluded),
        "daily": [
            {
                "date": day,
                "pv": daily_pv.get(day, 0),
                "uv": daily_uv.get(day, 0),
            }
            for day in sorted(daily_pv)
        ],
        "top_paths": [
            {"path": path, "pv": count}
            for path, count in Counter(r["path"] for r in page_views).most_common(10)
        ],
        "top_ips": [
            {"ip": ip, "pv": count}
            for ip, count in Counter(r["ip"] for r in page_views).most_common(10)
        ],
    }


def read_records(paths: list[Path]) -> list[dict]:
    """读取日志文件并解析为记录列表。"""
    records: list[dict] = []
    for path in paths:
        if not path.exists():
            print(f"[跳过] 日志文件不存在：{path}")
            continue
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                record = parse_line(line)
                if record:
                    records.append(record)
    return records


def format_report(result: dict, sources: list[Path]) -> str:
    """把统计结果格式化成可读报告。"""
    lines = [
        "fufu新闻 · 访问日志复算报告",
        "=" * 46,
        f"日志来源　：{', '.join(str(p) for p in sources)}",
        f"日志总行数：{result['total_lines']}",
        "",
        f"总访问量 PV　　　：{result['pv']}",
        f"独立访客 UV　　　：{result['uv']}",
        f"人均访问深度　　　：{result['depth']}",
        "",
        "清洗明细：",
    ]
    for reason, count in result["excluded"].items():
        lines.append(f"  - {reason}：剔除 {count} 条")
    if result["daily"]:
        lines.extend(["", "每日访问："])
        for day in result["daily"]:
            lines.append(f"  {day['date']}　PV {day['pv']}　UV {day['uv']}")
    if result["top_paths"]:
        lines.extend(["", "热门页面："])
        for item in result["top_paths"]:
            lines.append(f"  {item['pv']:>6}　{item['path']}")
    return "\n".join(lines)


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="从访问日志复算 fufu新闻 的 PV / UV")
    parser.add_argument(
        "logs",
        nargs="*",
        default=[str(DEFAULT_LOG)],
        help="访问日志文件路径（默认 logs/access.log）",
    )
    parser.add_argument(
        "--max-daily",
        type=int,
        default=500,
        help="单日请求数超过该值的 IP 视为异常流量并剔除（默认 500）",
    )
    parser.add_argument("--json", dest="json_path", default="", help="把结果另存为 JSON")
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="不剔除内网/回环地址（本地验证日志时用；公网统计请保持默认剔除）",
    )
    args = parser.parse_args()

    paths = [Path(p) for p in args.logs]
    records = read_records(paths)
    result = analyze(
        records, max_daily=args.max_daily, exclude_private=not args.include_private
    )
    print(format_report(result, paths))

    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nJSON 已写入：{args.json_path}")


if __name__ == "__main__":
    main()
