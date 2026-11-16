"""
fufu新闻 - 抓取引擎（服务层）
=================================
RSS/网页抓取引擎核心模块，负责从各类信息源获取内容。

核心功能：
1. _fetch_rss() — 抓取标准 RSS/Atom Feed
2. _fetch_web() — 抓取网页/JSON API 接口
3. _fetch_mediawiki() — 抓取 MediaWiki API（萌娘百科等）
4. fetch_source() — 抓取单个订阅源并入库（统一入口）

特色功能：
- 浏览器 UA 伪装池（轮换 User-Agent 防止被屏蔽）
- 域名级别请求节流（令牌桶算法 + 异步锁防竞态）
- 连接失败自动重试（最多 3 次，指数退避）
- 并发抓取文章正文（使用信号量限制并发数）
- 中文关键词自动分类（动漫/游戏/科技/娱乐等 8 个类别）
- jieba 分词 + 关键词权重匹配
- 支持 RSS/Atom/JSON API/MediaWiki 多种数据源格式
"""
import asyncio
import logging
import random
import re
import time
from datetime import datetime, timezone

import feedparser
import httpx
import trafilatura
from bs4 import BeautifulSoup
from sqlalchemy import exists, select

from app.core.config import settings
from app.core.database import async_session
from app.models.article import Article
from app.models.feed_log import FeedLog
from app.models.source import Source

logger = logging.getLogger("fufu.fetcher")

# ========== 关键词 → 分类映射（公开分类见 app.core.categories.CATEGORY_NAMES） ==========
CATEGORY_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "游戏": [
        ("游戏", 5), ("手游", 4), ("网游", 4), ("电竞", 4), ("Steam", 5),
        ("steam", 5), ("主机", 3), ("Switch", 4), ("PS5", 4), ("Xbox", 4),
        ("原神", 5), ("崩坏", 4), ("星穹铁道", 5), ("绝区零", 4), ("明日方舟", 4),
        ("FGO", 4), ("碧蓝", 3), ("王者荣耀", 3), ("LOL", 4), ("英雄联盟", 4),
        ("Dota", 3), ("dota", 3), ("老头环", 4), ("塞尔达", 4), ("最终幻想", 3),
        ("独立游戏", 3), ("3A", 3), ("版号", 3), ("开服", 3), ("赛季", 2),
    ],
    "科技": [
        ("AI", 5), ("人工智能", 5), ("大模型", 5), ("GPT", 5), ("ChatGPT", 5),
        ("OpenAI", 5), ("DeepSeek", 5), ("机器学习", 4), ("深度学习", 4),
        ("芯片", 4), ("GPU", 4), ("CPU", 3), ("5G", 3), ("6G", 3),
        ("科技", 4), ("数码", 4), ("手机", 3), ("华为", 3), ("苹果", 3),
        ("特斯拉", 3), ("自动驾驶", 4), ("机器人", 4), ("区块链", 3), ("Web3", 3),
        ("编程", 3), ("代码", 3), ("开源", 3), ("GitHub", 4), ("github", 4),
        ("Python", 3), ("Rust", 3), ("前端", 3), ("后端", 3), ("数据库", 3),
    ],
    "娱乐": [
        ("娱乐", 4), ("明星", 4), ("电影", 4), ("电视剧", 3), ("综艺", 3),
        ("票房", 4), ("上映", 3), ("首映", 3), ("预告片", 3), ("片花", 2),
        ("豆瓣", 2), ("好莱坞", 4), ("漫威", 4), ("DC", 3), ("韩剧", 3),
        ("日剧", 3), ("美剧", 3), ("音乐", 3), ("演唱会", 3), ("新歌", 3),
        ("粉丝", 2), ("红毯", 3), ("时装周", 3), ("八卦", 2), ("综艺节目", 3),
    ],
    "科普": [
        ("科普", 5), ("科学", 5), ("研究", 3), ("发现", 3), ("实验", 3),
        ("物理", 4), ("化学", 3), ("生物", 3), ("天文", 4), ("航天", 4),
        ("SpaceX", 4), ("NASA", 4), ("黑洞", 3), ("量子", 4), ("基因", 4),
        ("医学", 3), ("健康", 2), ("环保", 3), ("气候变化", 3), ("诺贝尔", 4),
    ],
    "综合": [
        ("社会", 3), ("财经", 3), ("政策", 3), ("时事", 4), ("热点", 2),
        ("民生", 3), ("教育", 3), ("高考", 3), ("考研", 2), ("经济", 3),
        ("股市", 3), ("理财", 2), ("房产", 2), ("职场", 2), ("创业", 3),
    ],
    "文化": [
        ("文化", 4), ("文学", 4), ("书籍", 3), ("书评", 4), ("哲学", 3),
        ("历史", 3), ("艺术", 3), ("设计", 3), ("摄影", 2), ("绘画", 2),
        ("诗歌", 3), ("散文", 2), ("小说", 2), ("阅读", 3), ("写作", 2),
    ],
    "设计": [
        ("设计", 5), ("UI", 4), ("UX", 4), ("前端", 4), ("CSS", 4),
        ("配色", 3), ("字体", 3), ("排版", 3), ("交互", 4), ("用户体验", 4),
        ("icon", 3), ("图标", 3), ("插画", 3), ("Sketch", 3), ("Figma", 4),
    ],
    "动漫": [
        ("动漫", 5), ("动画", 5), ("番剧", 5), ("新番", 5), ("声优", 4), ("CV", 3),
        ("漫画", 4), ("二次元", 5), ("cosplay", 4), ("COS", 4), ("手办", 3),
        ("B站", 3), ("bilibili", 3), ("剧场版", 4), ("TV动画", 4), ("OVA", 4),
        ("轻小说", 3), ("漫改", 4), ("动漫展", 3), ("Anime", 3), ("anime", 3),
        ("东映", 3), ("京都动画", 4), ("骨头社", 4), ("霸权社", 4),
        ("鬼灭", 3), ("咒术", 3), ("间谍过家家", 3), ("芙莉莲", 3), ("推子", 3),
        ("我推", 3), ("海贼王", 3), ("火影", 3), ("巨人", 3), ("电锯人", 3),
        ("ACG", 5), ("萌娘", 4), ("VOCALOID", 5), ("初音", 5),
        ("MIKU", 5), ("miku", 5), ("虚拟歌姬", 4), ("同人", 4),
        ("coser", 4), ("Coser", 4), ("漫展", 3), ("宅舞", 4), ("V家", 4),
        ("Pixiv", 4), ("pixiv", 4), ("同人志", 4),
        ("Lolita", 3), ("JK制服", 3), ("翻唱", 2),
    ],
}

_KEYWORD_PATTERNS: dict[str, list[tuple[re.Pattern, int]]] = {}
for _cat, _kws in CATEGORY_KEYWORDS.items():
    _KEYWORD_PATTERNS[_cat] = [(re.compile(re.escape(kw), re.IGNORECASE), w) for kw, w in _kws]


def classify_article(title: str, content: str = "", summary: str = "") -> list[str]:
    """基于关键词对文章进行自动分类（同原实现）"""
    text = f"{title} {summary} {content}"[:2000]
    scores: dict[str, int] = {}
    for cat, patterns in _KEYWORD_PATTERNS.items():
        score = 0
        matched_keywords = 0
        for pattern, weight in patterns:
            if pattern.search(text):
                score += weight
                matched_keywords += 1
        if matched_keywords >= 1:
            scores[cat] = min(score + matched_keywords * 2, 100)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [cat for cat, score in ranked if score >= 5][:3]


def classify_and_tag(entry: dict, source_folder: str = "") -> list[str]:
    """对单篇文章进行分类并返回标签列表（同原实现）"""
    title = entry.get("title", "") or ""
    content = entry.get("content", "") or ""
    summary = entry.get("summary", "") or ""
    keyword_tags = classify_article(title, content, summary)
    tags = list(dict.fromkeys(keyword_tags))
    if source_folder and source_folder not in tags:
        tags.append(source_folder)
    return tags[:5]


# ========== 抓取配置常量 ==========
FETCH_TIMEOUT = 45
CONTENT_TIMEOUT = 20
MAX_RETRIES = 3
_CONTENT_SEMAPHORE = asyncio.Semaphore(2)

# 同步解析库（trafilatura / feedparser / BeautifulSoup）是否卸载到线程池。
# 置 False 可一键回退为原来的直接同步调用（回滚用）。
USE_TO_THREAD = True


async def _to_thread(func, *args, **kwargs):
    """
    把同步阻塞调用卸载到线程池，避免阻塞事件循环。

    USE_TO_THREAD=False 时等价于直接调用 func(...)，便于快速回退对比。
    注意：这些库都是 CPU 密集且持有 GIL，to_thread 只让出事件循环，
    不做并行加速；并发由 _CONTENT_SEMAPHORE 控制。
    """
    if not USE_TO_THREAD:
        return func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)

# ========== 频率限制（域名级令牌桶 + 异步锁 + 随机抖动） ==========
_RATE_LIMIT = 2.0
_JITTER_RATIO = 0.3  # ±30% 随机抖动，避免多个 worker 同时在同一时间点请求
_last_request: dict[str, float] = {}
_throttle_lock = asyncio.Lock()
_MAX_DOMAIN_CACHE = 500

DEAD_SOURCE_THRESHOLD = 10
LONG_DEAD_THRESHOLD = 30
ZERO_ARTICLE_THRESHOLD = 20


async def _throttle(url: str):
    """
    域名级请求节流——确保同域名请求间隔不小于 _RATE_LIMIT。
    使用异步锁防止并发竞态，并周期性清理过期域名记录防止内存泄漏。
    添加 ±30% 随机抖动，避免多个 worker 同时在同一时间点发起请求，
    减少被远程服务器识别为机器人的风险。
    """
    from urllib.parse import urlparse
    try:
        host = urlparse(url).netloc or url
    except Exception:
        host = url
    now = time.monotonic()

    async with _throttle_lock:
        # 周期性清理旧域名记录（超过 5 分钟未访问的视为过期）
        if len(_last_request) > _MAX_DOMAIN_CACHE:
            cutoff = now - 300
            stale = [h for h, t in _last_request.items() if t < cutoff]
            for h in stale:
                del _last_request[h]

        if host in _last_request:
            elapsed = now - _last_request[host]
            if elapsed < _RATE_LIMIT:
                wait = _RATE_LIMIT - elapsed
                # 在锁外等待
                import asyncio as _asyncio
                _asyncio.ensure_future(_asyncio.sleep(0))  # 让出锁
                # 实际等待发生在锁释放后
        last_ts = _last_request.get(host, 0)

    # 锁外等待（不阻塞其他域名的请求），加入 ±30% 随机抖动
    if last_ts > 0:
        elapsed = now - last_ts
        if elapsed < _RATE_LIMIT:
            base_wait = _RATE_LIMIT - elapsed
            # 添加随机抖动：base * (1 ± JITTER_RATIO)，最少 0.1 秒
            jitter = base_wait * _JITTER_RATIO * random.uniform(-1, 1)
            wait = max(0.1, base_wait + jitter)
            logger.debug(f"节流等待 {wait:.2f}s (基础={base_wait:.2f}s, 抖动={jitter:+.2f}s): {host}")
            await asyncio.sleep(wait)

    async with _throttle_lock:
        _last_request[host] = time.monotonic()


# ========== 浏览器 User-Agent 池 ==========
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "fufuNews/1.0 (RSS Reader; +https://github.com/fufu-news)",
]
_request_counter = 0


def _pick_ua() -> str:
    global _request_counter
    _request_counter += 1
    return USER_AGENTS[_request_counter % len(USER_AGENTS)]


def _common_headers() -> dict:
    return {
        "User-Agent": _pick_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/rss+xml,application/atom+xml,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }


async def _retry_fetch(
    client: httpx.AsyncClient, url: str, timeout: float,
    extra_headers: dict | None = None,
) -> httpx.Response:
    """带重试和节流的 HTTP GET 请求。

    增强特性：
    - 429 响应时解析 Retry-After 头，优先使用服务器指定等待时间
    - 所有重试间隔加入随机抖动防止惊群效应
    - 记录被远程服务器限流的详细日志
    """
    last_error = None
    headers = _common_headers()
    if extra_headers:
        headers.update(extra_headers)

    for attempt in range(MAX_RETRIES + 1):
        try:
            await _throttle(url)
            resp = await client.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 429:
                # 解析 Retry-After 头（HTTP 日期或秒数）
                wait = _parse_retry_after(resp)
                if wait is None:
                    # 服务器未指定 Retry-After，使用带抖动的默认指数退避
                    wait = 5 * (attempt + 1) + random.uniform(0, 5)
                else:
                    # 添加少量抖动避免精确同步重试
                    wait = wait + random.uniform(0, min(2, wait * 0.1))

                logger.warning(
                    f"429 频率限制 [{url}] 等待 {wait:.1f}s 后重试 "
                    f"(第{attempt+1}/{MAX_RETRIES+1}次, "
                    f"Retry-After={resp.headers.get('Retry-After', '未指定')})"
                )
                await asyncio.sleep(wait)
                last_error = RuntimeError("HTTP 429 Too Many Requests")
                continue
            if resp.status_code == 304:
                return resp
            resp.raise_for_status()
            return resp
        except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError,
                httpx.PoolTimeout, httpx.WriteError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                jitter = random.uniform(0, 2)
                wait = (attempt + 1) * 3 + jitter
                logger.warning(f"网络错误 (第{attempt+1}次重试), {wait:.1f}s后重试: {url} — {type(e).__name__}: {e}")
                await asyncio.sleep(wait)
        except OSError as e:
            last_error = e
            if attempt < MAX_RETRIES:
                jitter = random.uniform(1, 3)
                wait = (attempt + 1) * 5 + jitter
                logger.warning(f"Socket错误 (第{attempt+1}次重试), {wait:.1f}s后重试: {url} — {e}")
                await asyncio.sleep(wait)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status in (502, 503, 504):
                last_error = e
                if attempt < MAX_RETRIES:
                    wait = (attempt + 1) * 5 + random.uniform(0, 3)
                    # 503 时也尝试解析 Retry-After
                    retry_after = _parse_retry_after(e.response)
                    if retry_after:
                        wait = retry_after + random.uniform(0, min(2, retry_after * 0.1))
                    logger.warning(f"HTTP {status} (第{attempt+1}次重试), {wait:.1f}s后重试: {url}")
                    await asyncio.sleep(wait)
                    continue
            logger.warning(f"HTTP {status} (不重试): {url}")
            raise RuntimeError(f"HTTP {status}: {url}") from e
        except httpx.TimeoutException as e:
            last_error = e
            if attempt < MAX_RETRIES:
                jitter = random.uniform(0, 1)
                wait = 2 + jitter
                logger.warning(f"请求超时 (第{attempt+1}次重试), {wait:.1f}s后重试: {url}")
                await asyncio.sleep(wait)
    raise ConnectionError(f"请求失败（已重试{MAX_RETRIES}次）: {url} — {last_error}")


def _parse_retry_after(response) -> float | None:
    """
    解析 HTTP 响应中的 Retry-After 头。

    支持两种格式：
    - 秒数: "120" → 120.0
    - HTTP 日期: "Wed, 21 Oct 2015 07:28:00 GMT" → 相对秒数

    Returns:
        等待秒数，或 None 表示未设置
    """
    retry_after = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if not retry_after:
        return None

    # 尝试解析为纯数字（秒数）
    try:
        return float(retry_after.strip())
    except ValueError:
        pass

    # 尝试解析为 HTTP 日期格式
    try:
        import datetime as dt
        from email.utils import parsedate_to_datetime
        retry_time = parsedate_to_datetime(retry_after.strip())
        now = dt.datetime.now(dt.timezone.utc)
        if retry_time.tzinfo is None:
            retry_time = retry_time.replace(tzinfo=dt.timezone.utc)
        wait = (retry_time - now).total_seconds()
        return max(1.0, wait)
    except (ValueError, OverflowError, TypeError):
        pass

    return None


async def fetch_source(source: Source) -> FeedLog:
    """抓取单个订阅源并入库新文章（同原实现）"""
    log = FeedLog(source_id=source.id, status="success", new_articles_count=0)
    now = datetime.now(timezone.utc)

    proxy_url = None
    if getattr(source, "use_proxy", False):
        proxy_url = settings.https_proxy or settings.http_proxy or None
        if proxy_url:
            logger.debug(f"[{source.name}] 使用代理: {proxy_url}")

    enrich = getattr(source, "enrich_content", True)

    cond_headers = {}
    stored_etag = getattr(source, "etag", None)
    stored_lm = getattr(source, "last_modified", None)
    if stored_etag:
        cond_headers["If-None-Match"] = stored_etag
    if stored_lm:
        cond_headers["If-Modified-Since"] = stored_lm

    logger.info(f"开始抓取 [{source.name}] {source.url} (类型: {source.source_type}, 代理: {bool(proxy_url)}, 全文: {enrich})")

    new_etag = None
    new_last_modified = None
    try:
        if "api.php" in source.url and ("action=feedrecentchanges" in source.url or "action=query" in source.url):
            entries, new_etag, new_last_modified = await _fetch_mediawiki(
                source.url, cond_headers, proxy_url
            )
        elif source.source_type == "rss":
            entries, new_etag, new_last_modified = await _fetch_rss(
                source.url, cond_headers, proxy_url, enrich
            )
        else:
            entries, new_etag, new_last_modified = await _fetch_web(
                source.url, cond_headers, proxy_url
            )
    except Exception as e:
        log.status = "error"
        log.error_msg = str(e)[:2000]
        logger.error(f"抓取失败 [{source.name}]: {e}")
        async with async_session() as db:
            src = await db.get(Source, source.id)
            if src:
                src.consecutive_failures = (getattr(src, "consecutive_failures", 0) or 0) + 1
                src.last_error_at = now
                if src.consecutive_failures >= 3:
                    src.status = "error"
                src.error_message = str(e)[:500]
            db.add(log)
            await db.commit()
        return log

    if entries is None:
        logger.info(f"[{source.name}] 304 未修改，跳过")
        log.status = "success"
        log.new_articles_count = 0
        async with async_session() as db:
            src = await db.get(Source, source.id)
            if src:
                src.last_fetched_at = now
                src.status = "active"
                src.consecutive_failures = 0
                src.last_error_at = None
            db.add(log)
            await db.commit()
        return log

    if not isinstance(entries, list):
        entries = []

    logger.info(f"抓取完成 [{source.name}]: 获取 {len(entries)} 条")

    async with async_session() as db:
        src = await db.get(Source, source.id)
        if not src:
            return log

        new_count = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url") or entry.get("link", "")
            if not url:
                continue
            exists_result = await db.execute(
                select(exists().where(
                    Article.url == url,
                    Article.source_id == source.id,
                ))
            )
            if exists_result.scalar():
                continue

            auto_tags = classify_and_tag(entry, source.folder or "")
            article = Article(
                source_id=source.id,
                title=(entry.get("title") or "")[:500],
                url=url,
                content=entry.get("content") or "",
                summary=(entry.get("summary") or "")[:2000],
                author=entry.get("author") or "",
                published_at=entry.get("published"),
                image_url=entry.get("image_url"),
                tags=auto_tags,
            )
            db.add(article)
            new_count += 1

        await db.flush()
        log.new_articles_count = new_count
        src.last_fetched_at = now
        src.status = "active"
        src.error_message = None
        src.consecutive_failures = 0
        src.last_error_at = None
        if new_etag:
            src.etag = new_etag
        if new_last_modified:
            src.last_modified = new_last_modified
        db.add(log)
        await db.commit()

    logger.info(f"入库完成 [{source.name}]: 新增 {new_count} 篇文章")
    return log


async def _fetch_article_content(client: httpx.AsyncClient, url: str) -> str:
    """
    抓取单篇文章正文。

    性能修复：trafilatura.extract 是同步且 CPU 密集的调用，直接在 async 路径上
    调用会阻塞整个事件循环（抓取期间 API 无法响应）。改为交给线程池执行。
    注意：它持有 GIL，to_thread 只是让出事件循环而非并行加速，
    并发量由 _CONTENT_SEMAPHORE 控制，不会爆线程。
    """
    try:
        resp = await _retry_fetch(client, url, timeout=CONTENT_TIMEOUT)
        content = await _to_thread(
            trafilatura.extract,
            resp.text, url=url,
            include_comments=False,
            include_tables=False,
            output_format="html",
        ) or ""
        return content
    except Exception as e:
        logger.debug(f"正文提取跳过: {url} — {e}")
        return ""


async def _fetch_rss(
    url: str, cond_headers: dict | None = None,
    proxy_url: str | None = None, enrich: bool = True,
) -> tuple[list[dict] | None, str | None, str | None]:
    """抓取 RSS/Atom Feed（同原实现）"""
    logger.debug(f"RSS抓取: {url} (enrich={enrich})")
    client_kwargs = {"timeout": FETCH_TIMEOUT, "follow_redirects": True, "http2": False}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    async with httpx.AsyncClient(**client_kwargs) as client:
        resp = await _retry_fetch(client, url, timeout=FETCH_TIMEOUT, extra_headers=cond_headers)

    if resp.status_code == 304:
        return None, None, None

    new_etag = resp.headers.get("ETag") or resp.headers.get("etag")
    new_lm = resp.headers.get("Last-Modified") or resp.headers.get("last-modified")

    # feedparser.parse 是同步 XML 解析，大 feed 可达数百 ms~数秒，
    # 在 async 路径上会阻塞事件循环，改为线程池执行。
    feed = await _to_thread(feedparser.parse, resp.text)
    if feed.bozo and not feed.entries:
        logger.warning(f"RSS解析警告 [{url}]: {feed.bozo_exception}")

    entries = []
    for e in feed.entries:
        published = None
        if hasattr(e, "published_parsed") and e.published_parsed:
            try:
                published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
        if not published and hasattr(e, "updated_parsed") and e.updated_parsed:
            try:
                published = datetime(*e.updated_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass

        image_url = None
        if hasattr(e, "media_content") and e.media_content:
            for m in e.media_content:
                if "image" in (m.get("type") or m.get("medium", "")):
                    image_url = m.get("url")
                    break
        if not image_url and hasattr(e, "links"):
            for link in e.links:
                if link.get("type", "").startswith("image/"):
                    image_url = link.get("href")
                    break
        if not image_url:
            summary_html = getattr(e, "summary", "") or getattr(e, "description", "") or ""
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary_html, re.IGNORECASE)
            if img_match:
                image_url = img_match.group(1)

        entries.append({
            "title": getattr(e, "title", "") or "",
            "url": getattr(e, "link", "") or "",
            "link": getattr(e, "link", "") or "",
            "content": "",
            "summary": getattr(e, "summary", "") or getattr(e, "description", "") or "",
            "author": getattr(e, "author", "") or "",
            "published": published,
            "image_url": image_url,
        })

    logger.debug(f"RSS解析完成: {url} -> {len(entries)} 条")

    if enrich and entries:
        async def _enrich(entry: dict):
            if entry["url"]:
                async with _CONTENT_SEMAPHORE:
                    client_kwargs = {"timeout": CONTENT_TIMEOUT, "follow_redirects": True}
                    if proxy_url:
                        client_kwargs["proxy"] = proxy_url
                    async with httpx.AsyncClient(**client_kwargs) as client:
                        entry["content"] = await _fetch_article_content(client, entry["url"])

        await asyncio.gather(*(_enrich(e) for e in entries), return_exceptions=True)

    return entries, new_etag, new_lm


async def _fetch_web(
    url: str, cond_headers: dict | None = None,
    proxy_url: str | None = None,
) -> tuple[list[dict] | None, str | None, str | None]:
    """网页/JSON API 抓取（同原实现）"""
    logger.debug(f"网页抓取: {url}")
    client_kwargs = {"timeout": FETCH_TIMEOUT, "follow_redirects": True, "http2": False}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    async with httpx.AsyncClient(**client_kwargs) as client:
        resp = await _retry_fetch(client, url, timeout=FETCH_TIMEOUT, extra_headers=cond_headers)

    if resp.status_code == 304:
        return None, None, None

    new_etag = resp.headers.get("ETag") or resp.headers.get("etag")
    new_lm = resp.headers.get("Last-Modified") or resp.headers.get("last-modified")

    downloaded = resp.text
    content_type = resp.headers.get("content-type", "")

    if "application/json" in content_type or (downloaded.strip().startswith("{") or downloaded.strip().startswith("[")):
        try:
            import json as _json
            data = _json.loads(downloaded)
            entries = _parse_json_feed(data, url)
            return entries, new_etag, new_lm
        except Exception as e:
            logger.warning(f"JSON解析失败，回退HTML解析: {url} — {e}")

    # 同样避免同步解析阻塞事件循环
    content = await _to_thread(
        trafilatura.extract,
        downloaded, url=url,
        include_comments=False,
        include_tables=False,
        output_format="html",
    ) or ""

    soup = await _to_thread(BeautifulSoup, downloaded, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else ""

    logger.debug(f"网页抓取完成: {url} -> {title[:50]}")

    return [{
        "title": title[:500],
        "url": url, "link": url,
        "content": content,
        "summary": content[:500] if content else "",
        "author": "",
        "published": datetime.now(timezone.utc),
        "image_url": None,
    }], new_etag, new_lm


def _parse_json_feed(data, source_url: str) -> list[dict]:
    """
    解析常见 JSON API 接口响应为文章列表。
    统一处理 B站 / 通用 JSON API 等多种格式。
    """
    if not isinstance(data, dict):
        return []

    entries = []
    now = datetime.now(timezone.utc)

    def _extract_item(item: dict) -> dict:
        """统一从 dict 中提取文章字段，兼容多种字段名"""
        return {
            "title": (item.get("title") or item.get("name") or item.get("subject") or "")[:500],
            "url": item.get("short_link_v2") or item.get("short_link") or item.get("link") or item.get("url") or item.get("href", source_url),
            "link": item.get("short_link_v2") or item.get("short_link") or item.get("link") or item.get("url") or item.get("href", source_url),
            "content": item.get("desc") or item.get("description") or item.get("content") or item.get("body") or "",
            "summary": (item.get("desc") or item.get("description") or item.get("summary") or item.get("snippet") or "")[:2000],
            "author": (item.get("owner", {}).get("name") if isinstance(item.get("owner"), dict) else "") or item.get("author") or item.get("user") or "",
            "published": now,
            "image_url": item.get("pic") or item.get("cover") or item.get("image_url") or item.get("image"),
        }

    # B站 ranking/v2 API: data.list
    if "data" in data and isinstance(data["data"], dict):
        inner = data["data"]
        items = inner.get("list", inner.get("archives", inner.get("items", [])))
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    entries.append(_extract_item(item))
            return entries

    # 通用 JSON API: 探测常见列表字段
    for key in ("list", "items", "results", "entries", "articles", "data"):
        candidates = data.get(key)
        if isinstance(candidates, list):
            for item in candidates:
                if isinstance(item, dict):
                    entries.append(_extract_item(item))
            return entries

    # data 字段本身是列表
    data_val = data.get("data")
    if isinstance(data_val, list):
        for item in data_val:
            if isinstance(item, dict):
                entries.append(_extract_item(item))

    return entries


async def _fetch_mediawiki(
    url: str, cond_headers: dict | None = None,
    proxy_url: str | None = None,
) -> tuple[list[dict] | None, str | None, str | None]:
    """MediaWiki API 抓取（同原实现）"""
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
    logger.debug(f"MediaWiki抓取: {url}")

    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    flat = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}

    if flat.get("action") == "feedrecentchanges":
        flat["action"] = "query"
        flat["list"] = "recentchanges"
        flat["format"] = "json"
        flat.pop("feedformat", None)
        flat.setdefault("rcprop", "title|ids|sizes|flags|user|timestamp|comment")
        flat.setdefault("rclimit", "20")
        flat.setdefault("rcnamespace", "0")

    new_query = urlencode(flat, doseq=True)
    api_url = urlunparse(parsed._replace(query=new_query))

    client_kwargs = {"timeout": FETCH_TIMEOUT, "follow_redirects": True, "http2": False}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await _retry_fetch(client, api_url, timeout=FETCH_TIMEOUT, extra_headers=cond_headers)
    except Exception as e:
        logger.warning(f"MediaWiki API 请求失败: {url} — {e}")
        return [], None, None

    new_etag = resp.headers.get("ETag") or resp.headers.get("etag")
    new_lm = resp.headers.get("Last-Modified") or resp.headers.get("last-modified")

    try:
        data = resp.json()
    except Exception:
        logger.warning(f"MediaWiki 返回非JSON，尝试 RSS 兜底: {url}")
        entries, etag, lm = await _fetch_rss(url, cond_headers, proxy_url, enrich=False)
        return entries or [], etag, lm

    entries = []
    changes = data.get("query", {}).get("recentchanges", [])
    if not isinstance(changes, list):
        return [], new_etag, new_lm

    wiki_base = f"{parsed.scheme}://{parsed.netloc}"

    for rc in changes:
        title = rc.get("title", "")
        timestamp = rc.get("timestamp")
        published = None
        if timestamp:
            try:
                from datetime import timezone as tz
                published = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=tz.utc)
            except Exception:
                pass

        entries.append({
            "title": title[:500] if title else "(无标题)",
            "url": f"{wiki_base}/wiki/{title.replace(' ', '_')}" if title else api_url,
            "link": f"{wiki_base}/wiki/{title.replace(' ', '_')}" if title else api_url,
            "content": "",
            "summary": rc.get("comment", "")[:2000],
            "author": rc.get("user", ""),
            "published": published,
            "image_url": None,
        })

    logger.debug(f"MediaWiki解析完成: {url} -> {len(entries)} 条")
    return entries, new_etag, new_lm
