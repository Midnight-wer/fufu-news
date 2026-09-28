"""
fufu新闻 - AI 大脑（服务层）
================================
AI 服务核心模块——封装 AI API 调用的底层逻辑。

提供的功能：
- generate_summary(): 调用 AI 生成文章摘要
- generate_tags(): 调用 AI 生成文章标签
- process_article(): 对单篇文章执行完整 AI 处理（摘要 + 标签）

底层使用 _chat() 函数与 AI API 通信（OpenAI 兼容接口）。
"""
import json
import re
import logging
import httpx
from app.core.config import settings

# AI 服务日志记录器
logger = logging.getLogger("fufu.ai")

# ========== Prompt 模板 ==========

# 摘要生成的 Prompt
SUMMARY_PROMPT = """你是一个叫"fufu"的可爱新闻助手，性格温柔治愈。请用简洁可爱的中文总结以下新闻内容。

要求：
- 保持轻松愉快的语气，像在跟好朋友分享
- 2-3句话，不超过150字
- 突出最有趣或最重要的信息
- 使用适当的emoji点缀

新闻内容："""

# 标签生成的 Prompt
TAG_PROMPT = """你是一个叫"fufu"的可爱新闻助手。请从以下新闻内容中提取3-5个关键词标签。

要求：
- 标签使用中文
- 每个标签2-4个字
- 标签要能概括文章主题
- 以JSON数组格式返回，不要包含其他内容
- 示例：["科技", "人工智能", "环保"]

新闻内容："""


def _build_messages(prompt: str, content: str) -> list[dict]:
    """
    构建 AI 对话的消息列表。

    参数:
        prompt: 任务指令（摘要/标签的 Prompt）
        content: 要处理的文章内容（最多 4000 字符）

    返回:
        list[dict]: 符合 OpenAI 格式的消息列表
    """
    return [
        {"role": "system", "content": "你叫fufu，是一个可爱的新闻助手。回复简洁、温暖、带点俏皮。"},
        {"role": "user", "content": prompt + "\n\n" + content[:4000]},
    ]


def _clean_content(content: str | None) -> str:
    """
    清理文章内容——去除 HTML 标签并规范化空白字符。

    参数:
        content: 原始文章 HTML 内容（可为 None）

    返回:
        str: 清理后的纯文本
    """
    if not content:
        return ""
    # 去除 HTML 标签
    clean = re.sub(r"<[^>]+>", "", content)
    # 规范化空白字符（多个空格/换行合并为一个空格）
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


async def _chat(
    messages: list[dict],
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str | None:
    """
    调用 AI 聊天接口——底层 AI API 通信函数（带重试）。

    参数:
        messages: 对话消息列表
        model: 模型名称（可选）
        base_url: API 地址（可选）
        api_key: API 密钥（可选）

    返回:
        str | None: AI 的文本回复，失败返回 None
    """
    import asyncio, random
    url = (base_url or settings.ai_base_url).rstrip("/")
    key = api_key or settings.ai_api_key
    m = model or settings.ai_model

    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    payload = {
        "model": m,
        "messages": messages,
        "temperature": settings.ai_temperature,
        "max_tokens": 4096,
    }

    logger.info(f"AI 请求 -> URL: {url}, Model: {m}, 有APIKey: {bool(key)}")

    last_error = None
    for attempt in range(3):  # 最多重试 2 次（共 3 次尝试）
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                logger.info(f"AI 响应 -> 状态码: {resp.status_code}")
                if resp.status_code >= 500:
                    # 服务端错误可重试
                    if attempt < 2:
                        wait = (attempt + 1) * 2 + random.uniform(0, 1)
                        logger.warning(f"AI {resp.status_code} 错误，{wait:.1f}s后重试 ({attempt+1}/3)")
                        await asyncio.sleep(wait)
                        continue
                if resp.status_code >= 400:
                    logger.error(f"AI 错误响应体: {resp.text[:500]}")
                resp.raise_for_status()
                data = resp.json()
                msg = data["choices"][0]["message"]
                return (msg.get("content") or msg.get("reasoning_content") or "").strip()
        except httpx.ConnectError as e:
            last_error = e
            if attempt < 2:
                wait = (attempt + 1) * 3
                logger.warning(f"AI 连接失败，{wait:.1f}s后重试 ({attempt+1}/3)")
                await asyncio.sleep(wait)
        except httpx.TimeoutException as e:
            last_error = e
            if attempt < 2:
                logger.warning(f"AI 超时，重试 ({attempt+1}/3)")
                await asyncio.sleep(1)
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500 and attempt < 2:
                wait = (attempt + 1) * 3
                logger.warning(f"AI HTTP {e.response.status_code}，{wait:.1f}s后重试 ({attempt+1}/3)")
                await asyncio.sleep(wait)
                continue
            detail = f"状态码 {e.response.status_code}"
            try:
                body = e.response.json()
                if "error" in body:
                    detail += f": {body['error']}"
            except Exception:
                detail += f": {e.response.text[:300]}"
            raise RuntimeError(f"AI 服务返回错误 — {detail}")
        except Exception as e:
            last_error = e
            if attempt < 2:
                await asyncio.sleep(1)

    if last_error:
        raise RuntimeError(f"AI 调用失败（已重试）: {str(last_error)[:200]}")
    return None


async def generate_summary(
    content: str | None,
    title: str = "",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str:
    """
    为文章生成 AI 摘要。

    对文章内容进行清理后，调用 AI 生成 2-3 句可爱的中文摘要。
    内容太短（少于 100 字符）则跳过。

    参数:
        content: 文章正文（HTML 格式）
        title: 文章标题（可选，会包含在 prompt 中提供上下文）
        model: 模型名称覆盖
        base_url: API 地址覆盖
        api_key: API 密钥覆盖

    返回:
        str: AI 生成的摘要文本（失败或内容太短时返回空字符串）
    """
    text = _clean_content(content)
    if not text or len(text) < 100:
        return ""  # 内容太短，不生成摘要

    # 拼接标题和正文
    full = f"标题：{title}\n\n正文：{text}" if title else text
    try:
        result = await _chat(
            _build_messages(SUMMARY_PROMPT, full),
            model=model, base_url=base_url, api_key=api_key,
        )
        return result.strip() if result else ""
    except Exception as e:
        logger.warning(f"摘要生成失败: {e}")
        return ""


async def generate_tags(
    content: str | None,
    title: str = "",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> list[str]:
    """
    为文章生成 AI 标签。

    对文章内容进行清理后，调用 AI 提取 3-5 个中文关键词标签。
    AI 返回的 JSON 数组会被解析提取。

    参数:
        content: 文章正文（HTML 格式）
        title: 文章标题（可选）
        model: 模型名称覆盖
        base_url: API 地址覆盖
        api_key: API 密钥覆盖

    返回:
        list[str]: 标签字符串列表（失败或内容太短时返回空列表）
    """
    text = _clean_content(content)
    if not text or len(text) < 100:
        return []  # 内容太短，不生成标签

    # 拼接标题和正文
    full = f"标题：{title}\n\n正文：{text}" if title else text
    try:
        result = await _chat(
            _build_messages(TAG_PROMPT, full),
            model=model, base_url=base_url, api_key=api_key,
        )
        if not result:
            return []

        # 从 AI 回复中提取 JSON 数组
        match = re.search(r"\[.*?\]", result, re.DOTALL)
        if match:
            tags = json.loads(match.group())
            # 过滤非字符串元素，最多返回 5 个
            return [t for t in tags if isinstance(t, str)][:5]
        return []
    except Exception as e:
        logger.warning(f"标签生成失败: {e}")
        return []


# ========== 深度摘要 Prompt ==========

# 深度摘要生成 Prompt——产出结构化 JSON
DEEP_SUMMARY_PROMPT = """你是一个叫"fufu"的可爱新闻助手，同时也是一名专业的新闻分析师。请仔细阅读以下新闻内容，生成一份结构化的深度摘要。

要求以严格的 JSON 格式返回，结构如下：
```json
{
  "one_liner": "用一句话概括这篇新闻的核心信息（30字以内）",
  "key_data": [
    {"label": "数据名称", "value": "具体数值或描述"}
  ],
  "core_points": [
    "核心观点1：简要说明",
    "核心观点2：简要说明",
    "核心观点3：简要说明"
  ],
  "background": "提供相关的行业背景、历史脉络或关联事件（100-200字）",
  "reactions": {
    "support": "支持方的观点和理由（如无则填'暂无明确支持方观点'）",
    "oppose": "反对方的观点和理由（如无则填'暂无明确反对方观点'）",
    "neutral": "中立方的观点和分析（如无则填'暂无明确中立方观点'）"
  }
}
```

具体要求：
- one_liner: 精准简洁，直击新闻核心
- key_data: 提取文中2-4个关键数据点，label用中文，value准确引用原文数据
- core_points: 提炼2-5个核心观点，每个观点10-25字
- background: 补充相关背景知识，帮助读者理解新闻语境
- reactions: 识别文中涉及的不同立场/利益相关方的反应
- 如果某部分确实没有对应内容，请填写合理的替代说明
- 只返回 JSON，不要在 JSON 外加任何解释文字

新闻内容："""


async def generate_deep_summary(
    content: str | None,
    title: str = "",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict:
    """
    为文章生成结构化深度摘要。

    对文章内容进行清理后，调用 AI 生成包含以下段落的深度摘要：
    - 一句话总结（one_liner）
    - 关键数据（key_data）
    - 核心观点（core_points）
    - 背景补充（background）
    - 各方反应（reactions）

    返回的 dict 可直接存入 article.deep_summary（JSON 字段）。

    参数:
        content: 文章正文（HTML 格式）
        title: 文章标题（可选，会包含在 prompt 中提供上下文）
        model: 模型名称覆盖
        base_url: API 地址覆盖
        api_key: API 密钥覆盖

    返回:
        dict: 结构化深度摘要，包含 one_liner / key_data / core_points /
              background / reactions / generated_at 字段。
              失败或内容太短时返回空字典。
    """
    text = _clean_content(content)
    if not text or len(text) < 100:
        logger.info(f"深度摘要跳过：内容太短 ({len(text)} 字符)")
        return {}

    full = f"标题：{title}\n\n正文：{text}" if title else text

    try:
        result = await _chat(
            _build_messages(DEEP_SUMMARY_PROMPT, full),
            model=model, base_url=base_url, api_key=api_key,
        )
        if not result:
            logger.warning("深度摘要生成失败：AI 返回空内容")
            return {}

        # 尝试解析 AI 返回的 JSON
        parsed = _parse_deep_summary_json(result)
        if parsed:
            logger.info(f"深度摘要生成成功：one_liner={parsed.get('one_liner', '')[:30]}")
            return parsed

        logger.warning("深度摘要 JSON 解析失败，返回原始文本")
        return {
            "one_liner": result[:100] if result else "",
            "key_data": [],
            "core_points": [],
            "background": "",
            "reactions": {"support": "", "oppose": "", "neutral": ""},
            "generated_at": "",
            "_parse_error": True,
        }

    except Exception as e:
        logger.warning(f"深度摘要生成异常: {e}")
        return {}


def _parse_deep_summary_json(raw: str) -> dict | None:
    """
    从 AI 原始回复中提取并解析深度摘要 JSON。

    处理策略：
    1. 尝试直接解析整个字符串为 JSON
    2. 尝试提取 ```json ... ``` 代码块
    3. 尝试用正则提取最外层 { ... } JSON 对象
    4. 验证并补全必要字段

    参数:
        raw: AI 返回的原始文本

    返回:
        dict | None: 解析成功返回结构化摘要，失败返回 None
    """
    from datetime import datetime, timezone
    import re as _re

    candidates = []

    # 策略1：直接解析
    candidates.append(raw.strip())

    # 策略2：提取 ```json ... ``` 代码块
    code_match = _re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if code_match:
        candidates.append(code_match.group(1).strip())

    # 策略3：正则提取最外层 JSON 对象
    brace_match = _re.search(r"\{[\s\S]*\}", raw)
    if brace_match:
        candidates.append(brace_match.group(0).strip())

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if not isinstance(data, dict):
                continue
            # 验证至少包含 one_liner
            if "one_liner" not in data and "core_points" not in data:
                continue

            # 补全缺失字段的默认值
            result = {
                "one_liner": str(data.get("one_liner", "")),
                "key_data": _normalize_key_data(data.get("key_data", [])),
                "core_points": _normalize_string_list(data.get("core_points", [])),
                "background": str(data.get("background", "")),
                "reactions": _normalize_reactions(data.get("reactions", {})),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            return result

        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    return None


def _normalize_key_data(raw: list | None) -> list[dict]:
    """规范化 key_data 列表，确保每个元素是 {label, value} 格式。"""
    if not raw or not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if isinstance(item, dict):
            result.append({
                "label": str(item.get("label", "")),
                "value": str(item.get("value", "")),
            })
    return result[:4]  # 最多保留 4 条


def _normalize_string_list(raw: list | None) -> list[str]:
    """规范化字符串列表，确保每个元素是字符串。"""
    if not raw or not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item][:5]  # 最多保留 5 条


def _normalize_reactions(raw: dict | None) -> dict:
    """规范化 reactions 字段，补全 support/oppose/neutral 三个键。"""
    if not raw or not isinstance(raw, dict):
        return {"support": "", "oppose": "", "neutral": ""}
    return {
        "support": str(raw.get("support", "")),
        "oppose": str(raw.get("oppose", "")),
        "neutral": str(raw.get("neutral", "")),
    }


async def process_article(
    article,
    db,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict:
    """
    对单篇文章执行完整 AI 处理——生成摘要和标签。

    根据 settings 中的 ai_auto_summary 和 ai_auto_tag 开关决定生成哪些内容。
    生成的结果会写回传入的 article 对象并刷入数据库。

    参数:
        article: Article ORM 实例（通过 SQLAlchemy session 加载）
        db: 数据库会话（用于 flush 更新）
        model: 模型名称覆盖
        base_url: API 地址覆盖
        api_key: API 密钥覆盖

    返回:
        dict: {"summary": "摘要内容" or None, "tags": [...] or None}
    """
    result = {"summary": None, "tags": None}

    # 如果启用了自动摘要
    if settings.ai_auto_summary:
        summary = await generate_summary(
            article.content, article.title,
            model=model, base_url=base_url, api_key=api_key,
        )
        if summary:
            article.summary = summary
            result["summary"] = summary

    # 如果启用了自动标签
    if settings.ai_auto_tag:
        tags = await generate_tags(
            article.content, article.title,
            model=model, base_url=base_url, api_key=api_key,
        )
        if tags:
            article.tags = tags
            result["tags"] = tags

    # 有任意内容被更新时，刷新到数据库
    if result["summary"] or result["tags"]:
        db.add(article)
        await db.flush()

    return result
