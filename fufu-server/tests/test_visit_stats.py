"""访问日志复算脚本的单元测试。"""
from scripts.visit_stats import analyze, is_page_view, is_public_ip, parse_line

NGINX_LINE = (
    '93.184.216.34 - - [16/Nov/2026:13:55:36 +0800] "GET /articles HTTP/1.1" 200 512 '
    '"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36" "-"'
)

PAGEVIEW_LINE = (
    '93.184.216.35 - - [16/Nov/2026:14:01:02 +0800] "PAGEVIEW /articles/12 HTTP/1.1" 200 0 '
    '"Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1" "-"'
)

UVICORN_LINE = 'INFO:     93.184.216.36:59258 - "GET /articles HTTP/1.1" 200 OK'


def test_parse_nginx_line():
    record = parse_line(NGINX_LINE)
    assert record is not None
    assert record["ip"] == "93.184.216.34"
    assert record["method"] == "GET"
    assert record["path"] == "/articles"
    assert record["status"] == 200
    assert record["day"] == "2026-11-16"


def test_parse_pageview_line():
    record = parse_line(PAGEVIEW_LINE)
    assert record is not None
    assert record["method"] == "PAGEVIEW"
    assert record["path"] == "/articles/12"


def test_parse_uvicorn_line():
    record = parse_line(UVICORN_LINE)
    assert record is not None
    assert record["ip"] == "93.184.216.36"
    assert record["path"] == "/articles"


def test_parse_invalid_line_returns_none():
    assert parse_line("这不是一行访问日志") is None


def test_public_ip_detection():
    assert is_public_ip("93.184.216.34")
    assert not is_public_ip("127.0.0.1")
    assert not is_public_ip("192.168.1.10")
    assert not is_public_ip("10.0.0.3")
    assert not is_public_ip("203.0.113.7")  # 文档保留段，不算真实访客
    assert not is_public_ip("::1")


def test_page_view_rules():
    assert is_page_view("GET", "/articles")
    assert is_page_view("PAGEVIEW", "/articles/12")
    assert not is_page_view("GET", "/api/v1/articles")
    assert not is_page_view("GET", "/assets/index-a1b2.js")
    assert not is_page_view("GET", "/favicon.ico")


def test_analyze_counts_pv_uv_and_depth():
    records = [
        parse_line(NGINX_LINE),
        parse_line(NGINX_LINE),
        parse_line(PAGEVIEW_LINE),
    ]
    result = analyze(records)
    # 两条 /articles + 一条 PAGEVIEW，都是公网地址
    assert result["pv"] == 3
    assert result["uv"] == 2
    assert result["depth"] == 1.5


def test_analyze_excludes_bot_and_private_ip():
    bot_line = (
        '93.184.216.40 - - [16/Nov/2026:13:00:00 +0800] "GET /articles HTTP/1.1" 200 512 '
        '"Mozilla/5.0 (compatible; Googlebot/2.1)" "-"'
    )
    private_line = (
        '192.168.1.10 - - [16/Nov/2026:13:00:00 +0800] "GET /articles HTTP/1.1" 200 512 '
        '"Mozilla/5.0 Chrome/120.0" "-"'
    )
    result = analyze([parse_line(bot_line), parse_line(private_line)])
    assert result["pv"] == 0
    assert result["excluded"]["爬虫 UA"] == 1
    assert result["excluded"]["内网/回环地址"] == 1


def test_analyze_can_keep_private_ip_for_local_logs():
    private_line = (
        '127.0.0.1 - - [16/Nov/2026:13:00:00 +0800] "PAGEVIEW /articles HTTP/1.1" 200 0 '
        '"Mozilla/5.0 Chrome/120.0" "-"'
    )
    result = analyze([parse_line(private_line)], exclude_private=False)
    assert result["pv"] == 1
    assert result["uv"] == 1


def test_analyze_excludes_high_frequency_ip():
    records = [parse_line(NGINX_LINE) for _ in range(6)]
    result = analyze(records, max_daily=5)
    assert result["pv"] == 0
    assert result["excluded"]["单日高频 IP"] == 6
