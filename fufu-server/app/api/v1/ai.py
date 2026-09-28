"""
fufu新闻 - AI 接口
=======================
提供 AI 功能相关的 REST API 端点：

- POST /ai/health            → AI 服务连接健康检查
- POST /ai/chat              → 通用 AI 对话（带 fufu 人设）
- POST /ai/chat/stream       → 流式 AI 对话（SSE 打字机效果）
- POST /ai/summarize/{id}    → 为单篇文章生成摘要
- POST /ai/tag/{id}          → 为单篇文章生成标签
- POST /ai/process/{id}      → 完整 AI 处理（摘要 + 标签）
- POST /ai/process-all       → 批量处理未处理的文章（后台任务）

fufu 人设：可爱元气的小狐狸 AI 助手，语气甜美俏皮。
"""
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.config import settings
from app.models.article import Article
from app.models.user import User
from app.api.deps import get_current_user
from app.services.ai import generate_summary, generate_tags, process_article, generate_deep_summary

# AI 模块日志记录器
logger = logging.getLogger("fufu.ai")
# 创建 AI 路由实例
router = APIRouter(tags=["AI"])


# ========== fufu 系统 Prompt（人设定义） ==========
# 注入可爱的狐狸助手人设，让 AI 回复带有甜美元气风格
FUFU_SYSTEM_PROMPT = """你是「fufu」🌸，一个住在新闻花园里的可爱 AI 助手！你的性格甜美、元气满满，像一只软乎乎的小狐狸～

🎀 说话风格：
- 语气可爱有趣，多用"呀""呢""哇""嘛""哦"等语气词
- 每句话搭配 1-3 个 emoji，但不要堆砌
- 口语化表达，像在跟好朋友聊天一样自然
- 回答短小精悍有梗，不要长篇大论，2-4句话最好
- 称呼用户为"你"，不要用"您"（太生疏啦）

🌟 风格自适应：
- 日常闲聊 → 活泼可爱，抛梗接梗，偶尔撒娇
- 聊新闻/时事 → 轻松但不失深度，像朋友分享见闻
- 技术/学习问题 → 专业准确但语气依然亲切，用简单比喻解释
- 情绪低落 → 温柔安慰，给人暖暖的鼓励 💕

💡 小技能：
- 可以推荐有趣的新闻、讲冷笑话、帮忙写文案
- 懂二次元、动漫、游戏话题
- 偶尔说一两句日语卖萌（不要太多）

记住：你就是一个可爱的朋友，不是冷冰冰的 AI 助手！让每次对话都像在樱花树下喝下午茶一样惬意～🌸"""


class AiConfig(BaseModel):
    """
    AI 配置覆盖模型——允许前端动态传入 AI 配置参数。

    所有字段均为可选，未传入的字段将使用全局 settings 中的默认值。

    字段说明：
    - ai_model: 模型名称
    - ai_base_url: AI API 请求地址
    - ai_api_key: API 密钥
    """
    ai_model: str | None = None
    ai_base_url: str | None = None
    ai_api_key: str | None = None


def _resolve(config: AiConfig) -> tuple[str, str, str]:
    """
    解析 AI 配置，返回 (base_url, model, api_key)。
    URL 不追加任何后缀（已经是完整的 API 端点地址）。

    参数:
        config: 前端传入的 AiConfig（可为空）

    返回:
        tuple[str, str, str]: (API 地址, 模型名称, API 密钥)
    """
    url = (config.ai_base_url or settings.ai_base_url).rstrip("/")
    model = config.ai_model or settings.ai_model
    key = config.ai_api_key or settings.ai_api_key
    return url, model, key


def _auth_headers(api_key: str | None) -> dict:
    """
    构建 AI API 的请求头——包含 Content-Type 和可选的 Bearer 认证。

    参数:
        api_key: API 密钥（可为 None）

    返回:
        dict: HTTP 请求头字典
    """
    h = {"Content-Type": "application/json"}
    key = api_key or settings.ai_api_key
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


@router.post("/health")
async def ai_health(config: AiConfig = AiConfig()):
    """
    AI 服务健康检查——POST /api/v1/ai/health

    向配置的 AI API 发送一个最小请求（"hi"），
    检测连接是否正常、模型是否可用。

    参数:
        config: 可选，覆盖默认 AI 配置

    返回:
        dict: {"status": "ok"/"error", "model": ..., "base_url": ..., "detail": ...}
    """
    base_url, model, key = _resolve(config)
    headers = _auth_headers(key)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5,
    }

    logger.info(f"健康检查 -> URL: {base_url}, Model: {model}")
    logger.debug(f"健康检查 请求头: {headers}")
    logger.debug(f"健康检查 请求体: {payload}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(base_url, json=payload, headers=headers)
            logger.info(f"健康检查 响应码: {resp.status_code}")
            if resp.status_code >= 400:
                logger.error(f"健康检查 错误响应: {resp.text[:500]}")
            resp.raise_for_status()
            return {"status": "ok", "model": model, "base_url": base_url}
    except httpx.ConnectError:
        return {"status": "error", "detail": f"无法连接到 {base_url}，请确认地址正确～"}
    except httpx.TimeoutException:
        return {"status": "error", "detail": f"连接 {base_url} 超时，请检查网络～"}
    except httpx.HTTPStatusError as e:
        detail = f"HTTP {e.response.status_code}"
        try:
            body = e.response.json()
            if "error" in body:
                detail += f": {body['error']}"
        except Exception:
            detail += f": {e.response.text[:200]}"
        return {"status": "error", "detail": detail}
    except Exception as e:
        return {"status": "error", "detail": f"AI 服务异常: {str(e)[:200]}"}


class ChatRequest(BaseModel):
    """
    AI 对话请求体模型。

    字段说明：
    - messages: 对话历史消息列表 [{"role": "user/assistant", "content": "..."}]
    - model: 可选，覆盖默认模型
    - base_url: 可选，覆盖默认 API 地址
    - api_key: 可选，覆盖默认 API 密钥
    """
    messages: list[dict]
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None


@router.post("/chat")
async def ai_chat(req: ChatRequest):
    """
    通用 AI 对话接口——POST /api/v1/ai/chat

    将用户的对话消息（附带 fufu 系统人设）发送给 AI API，
    返回 AI 的文本回复。

    fufu 人设会自动注入为 system 角色的第一条消息。

    参数:
        req: ChatRequest（对话消息 + 可选 AI 配置覆盖）

    返回:
        dict: {"content": "AI 回复文本"}

    异常:
        HTTPException(502): 连接失败
        HTTPException(504): 超时
    """
    base_url = (req.base_url or settings.ai_base_url).rstrip("/")
    model = req.model or settings.ai_model
    key = req.api_key or settings.ai_api_key

    headers = _auth_headers(key)

    # 构建消息列表：system prompt + 最近 20 条历史消息
    msgs = [{"role": "system", "content": FUFU_SYSTEM_PROMPT}]
    for m in req.messages[-20:]:  # 只保留最近 20 条，避免超出上下文窗口
        msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})

    payload = {
        "model": model,
        "messages": msgs,
        "temperature": 0.8,  # 较高温度让回复更活泼多样
        "max_tokens": 4096,
    }

    logger.info(f"Chat -> URL: {base_url}, Model: {model}")
    logger.debug(f"Chat 请求头: {headers}")
    logger.debug(f"Chat 消息数: {len(msgs)}")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(base_url, json=payload, headers=headers)
            logger.info(f"Chat 响应码: {resp.status_code}")
            if resp.status_code >= 400:
                logger.error(f"Chat 错误响应: {resp.text[:500]}")
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content") or msg.get("reasoning_content") or ""
            return {"content": content}
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"无法连接到 {base_url}，请确认地址正确～")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI 服务响应超时，请稍后重试～")
    except httpx.HTTPStatusError as e:
        detail = f"HTTP {e.response.status_code}"
        try:
            body = e.response.json()
            if "error" in body:
                detail += f": {body['error']}"
        except Exception:
            detail += f": {e.response.text[:200]}"
        raise HTTPException(status_code=502, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 调用失败: {str(e)[:200]}")


@router.post("/summarize/{article_id}")
async def summarize_article(
    article_id: int,
    config: AiConfig = AiConfig(),
    mode: str = "basic",
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    为单篇文章生成 AI 摘要——POST /api/v1/ai/summarize/{article_id}

    支持两种模式（通过 ?mode= 查询参数指定）：
    - basic（默认）：生成 2-3 句简洁可爱的中文摘要，存入 article.summary
    - deep：生成结构化深度摘要（一句话总结/关键数据/核心观点/背景/各方反应），存入 article.deep_summary

    参数:
        article_id: 文章 ID
        config: 可选 AI 配置覆盖
        mode: 摘要模式——"basic" 或 "deep"

    返回:
        basic 模式: {"article_id": ..., "summary": "摘要内容"}
        deep 模式:  {"article_id": ..., "deep_summary": {...}}

    异常:
        HTTPException(404): 文章不存在
        HTTPException(502): AI 服务调用失败
    """
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="找不到这篇文章呢～")

    base_url, model, key = _resolve(config)

    # ===== 深度摘要模式 =====
    if mode == "deep":
        deep = None
        error_msg = None
        try:
            deep = await generate_deep_summary(
                article.content, article.title,
                model=model, base_url=base_url, api_key=key,
            )
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"深度摘要生成失败 article={article_id}: {e}")

        if deep and deep.get("one_liner"):
            article.deep_summary = deep
            await db.flush()
            return {"code": 200, "data": {"article_id": article_id, "deep_summary": deep}, "message": "ok"}
        if error_msg:
            raise HTTPException(status_code=502, detail=error_msg)
        return {"code": 200, "data": {"article_id": article_id, "deep_summary": None}, "message": "内容太短，没法生成深度摘要呢～"}

    # ===== 基础摘要模式 =====
    summary = None
    error_msg = None
    try:
        summary = await generate_summary(
            article.content, article.title,
            model=model, base_url=base_url, api_key=key,
        )
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"摘要生成失败 article={article_id}: {e}")

    if summary:
        article.summary = summary
        await db.flush()
        return {"article_id": article_id, "summary": summary}
    if error_msg:
        raise HTTPException(status_code=502, detail=error_msg)
    return {"article_id": article_id, "summary": None, "message": "内容太短，没法生成摘要呢～"}


@router.post("/tag/{article_id}")
async def tag_article(
    article_id: int,
    config: AiConfig = AiConfig(),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    为单篇文章生成 AI 标签——POST /api/v1/ai/tag/{article_id}

    读取文章正文，调用 AI 服务提取 3-5 个中文关键词标签。
    标签会保存到数据库的 article.tags 字段（JSON 数组）。

    参数:
        article_id: 文章 ID
        config: 可选 AI 配置覆盖

    返回:
        dict: {"article_id": ..., "tags": ["标签1", "标签2", ...]}

    异常:
        HTTPException(404): 文章不存在
        HTTPException(502): AI 服务调用失败
    """
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="找不到这篇文章呢～")

    base_url, model, key = _resolve(config)

    # 调用 AI 生成标签
    tags = None
    error_msg = None
    try:
        tags = await generate_tags(
            article.content, article.title,
            model=model, base_url=base_url, api_key=key,
        )
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"标签生成失败 article={article_id}: {e}")

    if tags:
        article.tags = tags
        await db.flush()
        return {"article_id": article_id, "tags": tags}
    if error_msg:
        raise HTTPException(status_code=502, detail=error_msg)
    return {"article_id": article_id, "tags": None, "message": "内容太短，没法生成标签呢～"}


@router.post("/process/{article_id}")
async def process_article_endpoint(
    article_id: int,
    config: AiConfig = AiConfig(),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    对单篇文章执行完整 AI 处理——POST /api/v1/ai/process/{article_id}

    同时生成摘要和标签，一步完成。

    参数:
        article_id: 文章 ID
        config: 可选 AI 配置覆盖

    返回:
        dict: {"article_id": ..., "summary": ..., "tags": [...]}
    """
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="找不到这篇文章呢～")

    base_url, model, key = _resolve(config)
    r = await process_article(article, db, model=model, base_url=base_url, api_key=key)
    return {"article_id": article_id, **r}


class DeepSummarizeBatchRequest(BaseModel):
    """
    深度摘要批量生成请求体。

    字段说明：
    - article_ids: 指定要处理的文章 ID 列表（可选，为空则自动查找）
    - max_count: 如果未指定 article_ids，最多处理多少篇（默认 10，上限 50）
    """
    article_ids: list[int] | None = None
    max_count: int = 10


@router.post("/deep-summarize/{article_id}")
async def deep_summarize_article(
    article_id: int,
    config: AiConfig = AiConfig(),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    为单篇文章生成结构化深度摘要——POST /api/v1/ai/deep-summarize/{article_id}

    生成包含以下段落的深度摘要并存入 article.deep_summary：
    - 一句话总结（one_liner）
    - 关键数据（key_data）
    - 核心观点（core_points）
    - 背景补充（background）
    - 各方反应（reactions）

    参数:
        article_id: 文章 ID
        config: 可选 AI 配置覆盖

    返回:
        dict: {"code": 200, "data": {"article_id": ..., "deep_summary": {...}}, "message": "ok"}

    异常:
        HTTPException(404): 文章不存在
        HTTPException(502): AI 服务调用失败
    """
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="找不到这篇文章呢～")

    base_url, model, key = _resolve(config)

    deep = None
    error_msg = None
    try:
        deep = await generate_deep_summary(
            article.content, article.title,
            model=model, base_url=base_url, api_key=key,
        )
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"深度摘要生成失败 article={article_id}: {e}")

    if deep and deep.get("one_liner"):
        article.deep_summary = deep
        await db.flush()
        return {"code": 200, "data": {"article_id": article_id, "deep_summary": deep}, "message": "ok"}
    if error_msg:
        raise HTTPException(status_code=502, detail=error_msg)
    return {"code": 200, "data": {"article_id": article_id, "deep_summary": None}, "message": "内容太短，没法生成深度摘要呢～"}


@router.post("/deep-summarize-batch")
async def deep_summarize_batch(
    body: DeepSummarizeBatchRequest,
    background_tasks: BackgroundTasks,
    config: AiConfig = AiConfig(),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    批量生成深度结构化摘要——POST /api/v1/ai/deep-summarize-batch

    两种使用方式：
    1. 指定 article_ids：对所给 ID 中尚无 deep_summary 的文章生成深度摘要
    2. 不指定 article_ids：自动查找尚无 deep_summary 的文章（最多 max_count 篇）

    处理在后台任务中异步执行，接口立即返回排队数量。

    参数:
        body: DeepSummarizeBatchRequest（article_ids + max_count）
        config: 可选 AI 配置覆盖

    返回:
        dict: {"code": 200, "data": {"queued": N}, "message": "..."}
    """
    base_url, model, key = _resolve(config)

    # 确定要处理的文章列表
    if body.article_ids:
        # 指定了文章 ID——只处理其中尚无 deep_summary 的
        max_count = min(body.max_count or len(body.article_ids), 50)
        result = await db.execute(
            select(Article)
            .where(
                Article.id.in_(body.article_ids),
                Article.deep_summary == None,  # noqa: E711
            )
            .limit(max_count)
        )
    else:
        # 未指定 ID——查找所有尚无 deep_summary 的文章
        max_count = min(body.max_count, 50)
        result = await db.execute(
            select(Article)
            .where(Article.deep_summary == None)  # noqa: E711
            .limit(max_count)
        )

    articles = result.scalars().all()

    async def _process_batch():
        """后台批量深度摘要生成——独立会话逐篇处理。"""
        from app.core.database import async_session
        async with async_session() as bdb:
            for a in articles:
                try:
                    art = (await bdb.execute(
                        select(Article).where(Article.id == a.id)
                    )).scalar_one_or_none()
                    if not art:
                        continue
                    deep = await generate_deep_summary(
                        art.content, art.title,
                        model=model, base_url=base_url, api_key=key,
                    )
                    if deep and deep.get("one_liner"):
                        art.deep_summary = deep
                        await bdb.commit()
                        logger.info(f"深度摘要已保存 article={art.id}")
                    else:
                        logger.info(f"深度摘要跳过 article={art.id}（内容太短或生成失败）")
                except Exception as e:
                    logger.warning(f"批量深度摘要失败 article={a.id}: {e}")
                    await bdb.rollback()
                    continue

    background_tasks.add_task(_process_batch)
    return {
        "code": 200,
        "data": {"queued": len(articles)},
        "message": f"已安排为{len(articles)}篇文章生成深度摘要，请稍候～",
    }


@router.post("/process-all")
async def process_all_articles(
    background_tasks: BackgroundTasks,
    config: AiConfig = AiConfig(),
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    批量 AI 处理文章——POST /api/v1/ai/process-all

    查询所有缺少摘要或标签的文章（最多 limit 篇），
    在后台任务中逐个调用 AI 生成摘要和标签。
    使用 BackgroundTasks 异步执行，不阻塞接口响应。

    参数:
        config: 可选 AI 配置覆盖
        limit: 最多处理多少篇文章（默认 50）

    返回:
        dict: {"queued": 排队处理数量, "message": "..."}
    """
    # 查询缺少摘要或标签的文章
    result = await db.execute(
        select(Article)
        .where(
            (Article.summary == None) | (Article.summary == "") |
            (Article.tags == None) | (Article.tags == "[]")
        )
        .limit(limit)
    )
    articles = result.scalars().all()
    base_url, model, key = _resolve(config)

    async def _process_batch():
        """
        后台批量处理函数——在独立数据库会话中逐篇处理文章。
        每篇文章使用独立的 try-except，单篇失败不影响后续处理。
        """
        from app.core.database import async_session
        async with async_session() as bdb:
            for a in articles:
                try:
                    # 重新从数据库加载文章（避免跨会话问题）
                    art = (await bdb.execute(
                        select(Article).where(Article.id == a.id)
                    )).scalar_one_or_none()
                    if art:
                        await process_article(
                            art, bdb, model=model, base_url=base_url, api_key=key,
                        )
                    await bdb.commit()
                except Exception as e:
                    logger.warning(f"批量处理失败 article={a.id}: {e}")
                    await bdb.rollback()
                    continue

    # 将批量处理任务加入 FastAPI 的后台任务队列
    background_tasks.add_task(_process_batch)
    return {"queued": len(articles), "message": f"已安排为{len(articles)}篇文章生成AI摘要和标签，请稍候～"}


# ========== 流式对话 ==========
import json as _json
from fastapi.responses import StreamingResponse


@router.post("/chat/stream")
async def ai_chat_stream(req: ChatRequest):
    """
    流式 AI 对话——POST /api/v1/ai/chat/stream

    使用 SSE（Server-Sent Events）协议实时流式输出 AI 回复，
    前端可据此实现打字机效果。

    实现细节：
    - 请求 AI API 时设置 stream=True
    - 逐行读取 SSE 数据（data: {...} 格式）
    - 提取 delta.content 内容并转发给前端
    - 遇到 [DONE] 标记时结束流

    参数:
        req: ChatRequest（对话消息 + 可选配置）

    返回:
        StreamingResponse: SSE 流（text/event-stream MIME 类型）
    """
    base_url = (req.base_url or settings.ai_base_url).rstrip("/")
    model = req.model or settings.ai_model
    key = req.api_key or settings.ai_api_key

    headers = _auth_headers(key)

    # 构建消息列表，注入 fufu 人设
    msgs = [{"role": "system", "content": FUFU_SYSTEM_PROMPT}]
    for m in req.messages[-20:]:  # 只保留最近 20 条历史
        msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})

    payload = {
        "model": model,
        "messages": msgs,
        "temperature": 0.8,
        "max_tokens": 4096,
        "stream": True,  # 启用流式输出
    }

    logger.info(f"Stream Chat -> URL: {base_url}, Model: {model}, 消息数: {len(msgs)}")

    async def event_stream():
        """
        SSE 事件生成器——异步迭代 AI API 的流式响应。

        对于每个收到的 chunk：
        - 提取 delta.content
        - 以 SSE data 格式 yield 给前端
        - 遇到 [DONE] 或错误时终止
        """
        import asyncio
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", base_url, json=payload, headers=headers) as resp:
                    # HTTP 错误处理
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        err_detail = f"HTTP {resp.status_code}"
                        try:
                            err_json = _json.loads(body)
                            if "error" in err_json:
                                err_detail += f": {err_json['error']}"
                        except Exception:
                            err_detail += f": {body.decode()[:200]}"
                        yield f"data: {_json.dumps({'error': err_detail})}\n\n"
                        return

                    # 逐行读取 SSE 流
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]  # 去掉 "data: " 前缀
                        if data_str.strip() == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break
                        try:
                            chunk = _json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield f"data: {_json.dumps({'content': content})}\n\n"
                                await asyncio.sleep(0)  # 让出事件循环控制权
                        except (_json.JSONDecodeError, KeyError, IndexError):
                            continue  # 跳过解析失败的行
        except httpx.ConnectError:
            yield f"data: {_json.dumps({'error': '无法连接到 AI 服务，请确认地址正确～'})}\n\n"
        except httpx.TimeoutException:
            yield f"data: {_json.dumps({'error': 'AI 服务响应超时，请稍后重试～'})}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'error': f'AI 调用失败: {str(e)[:200]}'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",  # SSE 协议 MIME 类型
        headers={
            "Cache-Control": "no-cache",  # 禁止缓存
            "Connection": "keep-alive",  # 保持长连接
            "X-Accel-Buffering": "no",  # 禁用 Nginx 代理缓冲
        },
    )
