"""
fufu新闻 - 全网搜索服务
==========================
多层级搜索策略：ddgs → AI → 本地 FTS5 → LIKE 兜底。
带网络检测、结果缓存、重试机制。
"""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

logger = logging.getLogger("fufu.search")

TIMEOUT = 5  # ddgs 单次尝试超时（秒）

# ========== 网络可用性缓存 ==========
_network_state: dict[str, tuple[bool, float]] = {}

NETWORK_CHECK_TTL = 120  # 网络检测结果缓存 2 分钟


async def _check_tcp_async(host: str, port: int, timeout: float = 1.5) -> bool:
    """异步 TCP 端口连通性检测——不阻塞事件循环"""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False  # 任何网络异常都视为不可达，无需日志


async def is_ddgs_available() -> bool:
    """检测 DuckDuckGo 是否可达（带 2 分钟缓存，异步不阻塞）"""
    now = time.time()
    cached = _network_state.get("ddgs")
    if cached and (now - cached[1]) < NETWORK_CHECK_TTL:
        return cached[0]

    available = await _check_tcp_async("duckduckgo.com", 443, timeout=3.0)
    _network_state["ddgs"] = (available, now)
    if not available:
        logger.warning("DuckDuckGo 不可达（TCP 阻断），将跳过 ddgs 搜索")
    else:
        logger.info("DuckDuckGo 可达")
    return available


# ========== 搜索结果缓存 ==========
_search_cache: dict[str, tuple[list[dict], float]] = {}
CACHE_TTL = 300  # 缓存 5 分钟
MAX_CACHE_ENTRIES = 200


def _cache_key(keyword: str, source: str) -> str:
    return f"{source}:{keyword.lower().strip()}"


def _cache_get(keyword: str, source: str) -> list[dict] | None:
    key = _cache_key(keyword, source)
    entry = _search_cache.get(key)
    if entry:
        results, ts = entry
        if time.time() - ts < CACHE_TTL:
            logger.info(f"缓存命中: {key}")
            return results
        del _search_cache[key]
    return None


def _cache_set(keyword: str, source: str, results: list[dict]):
    if not results:  # 不缓存空结果，允许后续请求重试
        return
    key = _cache_key(keyword, source)
    _search_cache[key] = (results, time.time())
    # 淘汰最旧的缓存条目
    while len(_search_cache) > MAX_CACHE_ENTRIES:
        oldest = min(_search_cache, key=lambda k: _search_cache[k][1])
        del _search_cache[oldest]


# ========== DDGS 搜索 ==========


def _search_ddgs(keyword: str, max_results: int) -> list[dict]:
    """同步 DuckDuckGo 搜索——在独立线程中执行"""
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    results = []
    with DDGS(timeout=8) as ddgs:
        for r in ddgs.text(keyword, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": (r.get("body") or "")[:400],
                "source": "DuckDuckGo",
                "published_at": r.get("date") or datetime.now(timezone.utc).isoformat(),
            })
    return results


async def search_ddgs(keyword: str, max_results: int = 5) -> list[dict]:
    """ddgs 搜索（带缓存 + 网络检测 + 重试）"""
    if not keyword or not keyword.strip():
        return []

    keyword = keyword.strip()

    # 检查缓存（空结果不缓存，让后续请求可以重试）
    cached = _cache_get(keyword, "ddgs")
    if cached:
        return cached[:max_results]

    # 网络不可达则直接跳过
    if not await is_ddgs_available():
        return []

    # 重试 2 次，指数退避
    for attempt in range(2):
        try:
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=1) as pool:
                results = await asyncio.wait_for(
                    loop.run_in_executor(pool, _search_ddgs, keyword, min(max_results, 10)),
                    timeout=TIMEOUT,
                )
            if results:
                _cache_set(keyword, "ddgs", results)
                logger.info(f"ddgs 完成: {keyword!r} — {len(results)} 条")
                return results[:max_results]
            break  # 空结果不重试
        except asyncio.TimeoutError:
            logger.warning(f"ddgs 超时 (attempt {attempt+1}/2): {keyword!r}")
            if attempt == 0:
                await asyncio.sleep(0.5)  # 短暂退避
        except Exception as e:
            logger.error(f"ddgs 异常: {keyword!r} — {e}")
            break

    # 标记网络不可用
    _network_state["ddgs"] = (False, time.time())
    return []


# ========== AI 搜索 ==========


async def search_ai(keyword: str) -> list[dict]:
    """AI 搜索（带缓存 + 重试）"""
    import json

    import httpx

    from app.core.config import settings

    if not keyword or not keyword.strip():
        return []

    keyword = keyword.strip()

    # 检查缓存（空结果不缓存，让后续请求可以重试）
    cached = _cache_get(keyword, "ai")
    if cached:
        return cached

    base_url = settings.ai_base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_api_key}"

    prompt = (
        f'搜索关键词："{keyword}"。请以你的知识提供5条相关资讯，必须严格输出JSON数组格式：'
        f'[{{"title":"资讯标题","snippet":"50-100字内容摘要","source":"来源名称"}}]。'
        f'即使无法获取实时新闻，也请根据你的知识给出相关的资讯条目。只输出JSON数组：'
    )
    payload = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": "你是一个新闻搜索助手。即使用户搜索的关键词很具体，也请根据你的训练数据提供最相关的资讯条目。即使信息不是最新的，也请提供你知识范围内最匹配的内容。只输出JSON数组格式，不要输出其他文字。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
        "stream": False,
    }

    # 重试 2 次
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(base_url, json=payload, headers=headers)
                if resp.status_code != 200:
                    if attempt == 0 and resp.status_code >= 500:
                        await asyncio.sleep(0.8)
                        continue
                    return []
                data = resp.json()
                msg = data.get("choices", [{}])[0].get("message", {})
                content = msg.get("content") or msg.get("reasoning_content") or ""
                if not content:
                    return []

            content = content.strip()
            for pfx in ("```json", "```"):
                if content.startswith(pfx):
                    content = content[len(pfx):].strip()
                    if content.endswith("```"):
                        content = content[:-3].strip()

            s, e = content.find("["), content.rfind("]")
            items = json.loads(content[s:e+1]) if s >= 0 and e > s else []
            if not isinstance(items, list):
                items = []

            # 模型返回空数组 → 用 reasoning 生成兜底结果
            if not items:
                reasoning = (msg.get("reasoning_content") or "")[:200]
                if reasoning:
                    items = [{
                        "title": keyword,
                        "snippet": reasoning,
                        "source": "AI 知识库",
                    }]

            results = [
                {
                    "title": str(it.get("title", "")),
                    "url": str(it.get("url", "")),
                    "snippet": str(it.get("snippet", it.get("summary", ""))),
                    "source": str(it.get("source", "AI搜索")),
                    "published_at": None,
                }
                for it in items[:10] if isinstance(it, dict)
            ]
            if results:
                _cache_set(keyword, "ai", results)
            return results
        except Exception as e:
            logger.warning(f"AI 搜索异常 (attempt {attempt+1}/2): {keyword!r} — {e}")
            if attempt < 1:
                await asyncio.sleep(0.5)

    return []
