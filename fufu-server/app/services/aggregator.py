"""
fufu新闻 - 多源聚合对比服务
=============================
当用户阅读一篇文章时，自动查找来自不同订阅源但报道同一事件/话题的其他文章，
让用户获得多角度、多来源的新闻视角。

实现策略（多层匹配）：
1. 标签重叠匹配：查找标签有交集的来自其他源的文章
2. 标题关键词匹配：使用 jieba 分词 + Jaccard 相似度
3. 评分排序：标签重叠数 + 标题关键词匹配数 + 时效性加分
"""
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.source import Source

logger = logging.getLogger("fufu.aggregator")

# ===== 中文停用词表（常见无意义词，从标题关键词中过滤） =====
_STOP_WORDS: set[str] = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那",
    "些", "什么", "怎么", "如何", "还是", "可以", "这个", "那个",
    "因为", "所以", "但是", "而且", "虽然", "如果", "已经", "正在",
    "将会", "可能", "应该", "一个", "来", "对", "被", "把", "让",
    "从", "与", "及", "或", "等", "为", "其", "以", "之", "中",
    "后", "前", "内", "外", "间", "时", "但", "并", "而", "则",
    "又", "将", "能", "可", "已", "还", "做", "出", "想", "最",
    "更", "只", "再", "才", "过", "用", "年", "月", "日",
    "新", "大", "小", "多", "少", "高", "长", "真", "向",
    "各", "位", "吗", "吧", "呢", "啊", "哦", "哈", "呀", "嘛",
    "唉", "嗯", "喂", "哎", "嘿", "哟", "哇", "嘻", "哼", "啦",
    "哎哟", "哎呀", "哈哈", "呵呵", "嘿嘿", "哦哦", "呜呜",
}


def _extract_title_keywords(title: str) -> set[str]:
    """
    使用 jieba 分词从标题中提取关键词。

    处理步骤：
    1. 去除标点符号和特殊字符
    2. jieba 精确模式分词
    3. 过滤停用词、单字词、纯数字、纯英文缩写
    4. 返回关键词集合

    参数:
        title: 文章标题

    返回:
        set[str]: 关键词集合
    """
    if not title:
        return set()

    import jieba

    # 去除标点和特殊字符，保留中文、英文、数字
    clean = re.sub(r"[^一-鿿\w]", " ", title)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return set()

    # jieba 精确模式分词
    words = jieba.lcut(clean)

    keywords: set[str] = set()
    for w in words:
        w = w.strip().lower()
        # 过滤条件
        if not w:
            continue
        if len(w) < 2 and not (w.isascii() and w.isalpha()):
            continue  # 过滤单字（英文单词除外）
        if w in _STOP_WORDS:
            continue
        if w.isdigit():
            continue
        if len(w) == 1 and not (w.isascii() and w.isupper()):
            continue  # 过滤单字符（除非是英文大写缩写如 AI）
        keywords.add(w)

    return keywords


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """
    计算两个集合的 Jaccard 相似度。

    参数:
        set_a: 集合 A
        set_b: 集合 B

    返回:
        float: Jaccard 相似度值（0.0 ~ 1.0）
    """
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _recency_bonus(published_at: datetime | None) -> float:
    """
    根据发布时间计算时效性加分。

    加分规则：
    - 24 小时内：+3.0
    - 3 天内：+2.0
    - 7 天内：+1.0
    - 14 天内：+0.5
    - 更早：0

    参数:
        published_at: 文章发布时间

    返回:
        float: 时效性加分
    """
    if not published_at:
        return 0.5  # 没有时间的文章给默认小分值

    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    delta = now - published_at

    if delta < timedelta(hours=24):
        return 3.0
    if delta < timedelta(days=3):
        return 2.0
    if delta < timedelta(days=7):
        return 1.0
    if delta < timedelta(days=14):
        return 0.5
    return 0.0


def _classify_perspective(
    tag_overlap: int,
    keyword_overlap: int,
) -> str:
    """
    根据标签和关键词重叠程度分类视角类型。

    分类规则：
    - 标签重叠 >= 3：同一事件（高度相关，可能报道同一件事）
    - 标签重叠 >= 1：相关报道（共享一些主题标签）
    - 仅有标题关键词匹配：补充视角（关联较弱，但主题相近）

    参数:
        tag_overlap: 重叠标签数量
        keyword_overlap: 重叠标题关键词数量

    返回:
        str: 视角类型标签
    """
    if tag_overlap >= 3:
        return "同一事件"
    if tag_overlap >= 1:
        return "相关报道"
    if keyword_overlap >= 2:
        return "补充视角"
    return "补充视角"


def _generate_common_points(
    main_keywords: set[str],
    related_articles: list[dict],
) -> list[str]:
    """
    生成共同关注点列表——在多篇相关文章中都有出现的关键词。

    参数:
        main_keywords: 主文章的关键词集合
        related_articles: 相关文章列表（需包含 overlap_keywords 字段）

    返回:
        list[str]: 共同关注点句子
    """
    if len(related_articles) < 2:
        # 只有一篇相关文章时，列出共享的关键词
        if related_articles and related_articles[0].get("overlap_keywords"):
            kw = related_articles[0]["overlap_keywords"][:4]
            return [f"共同关注：{'、'.join(kw)}"]
        return []

    # 统计每个关键词在多少篇相关文章中出现
    kw_count: dict[str, int] = {}
    for art in related_articles:
        seen: set[str] = set()
        for kw in art.get("overlap_keywords", []):
            if kw in main_keywords and kw not in seen:
                kw_count[kw] = kw_count.get(kw, 0) + 1
                seen.add(kw)

    # 取出现次数 >= 2 的关键词
    common_kw = sorted(
        [(kw, cnt) for kw, cnt in kw_count.items() if cnt >= 2],
        key=lambda x: -x[1],
    )[:5]

    points: list[str] = []
    if common_kw:
        kw_str = "、".join(k[0] for k in common_kw)
        points.append(f"多篇报道共同关注：{kw_str}")

    return points


def _generate_different_points(
    main_article_tags: list[str],
    related_articles: list[dict],
) -> list[str]:
    """
    生成不同视角点——不同来源侧重的方面。

    基于各来源的标签差异，简要说明各自侧重的角度。

    参数:
        main_article_tags: 主文章的标签列表
        related_articles: 相关文章列表

    返回:
        list[str]: 不同视角说明
    """
    points: list[str] = []

    for art in related_articles[:3]:
        art_tags: list[str] = art.get("article", {}).get("tags", []) or []
        # 找出该文章有而主文章没有的标签（独特视角）
        unique_tags = [t for t in art_tags if t and t not in main_article_tags]
        if unique_tags:
            source_name = art.get("article", {}).get("source_name", "其他来源")
            unique_str = "、".join(unique_tags[:3])
            points.append(f"{source_name}侧重：{unique_str}")
        else:
            source_name = art.get("article", {}).get("source_name", "其他来源")
            perspective = art.get("perspective", "相关报道")
            points.append(f"{source_name}：从{perspective}角度报道")

    return points


async def find_related_from_other_sources(
    article_id: int,
    db: AsyncSession,
    limit: int = 4,
) -> dict:
    """
    从其他订阅源查找报道同一话题的相关文章。

    多层匹配策略：
    1. 获取主文章的关键词和标签
    2. 从数据库查询其他源最近的文章（30 天窗口，最多 200 条候选）
    3. 对每篇候选文章计算：标签重叠 + 标题关键词匹配 + 时效性加分
    4. 按总分排序，返回 top N

    参数:
        article_id: 主文章 ID
        db: 异步数据库会话
        limit: 返回的相关文章数量上限

    返回:
        dict: {
            "main_article": {...},
            "related_sources": [...],
            "common_points": [...],
            "different_points": [...]
        }
    """
    # ---- 第 1 步：获取主文章 ----
    result = await db.execute(
        select(Article).where(Article.id == article_id)
    )
    main_article = result.scalar_one_or_none()
    if not main_article:
        logger.warning(f"聚合对比：找不到文章 id={article_id}")
        return {
            "main_article": None,
            "related_sources": [],
            "common_points": [],
            "different_points": [],
        }

    # 获取主文章的源信息
    src_result = await db.execute(
        select(Source.name, Source.folder).where(Source.id == main_article.source_id)
    )
    src_row = src_result.one_or_none()

    main_article.source_name = src_row[0] if src_row else None
    main_article.source_folder = src_row[1] if src_row else None

    # 提取主文章的关键词和标签
    main_tags: list[str] = main_article.tags or []
    main_keywords: set[str] = _extract_title_keywords(main_article.title or "")

    logger.info(
        f"聚合对比: 文章 #{article_id} 关键词={main_keywords}, 标签={main_tags}"
    )

    if not main_keywords and not main_tags:
        return {
            "main_article": main_article,
            "related_sources": [],
            "common_points": [],
            "different_points": [],
        }

    # ---- 第 2 步：查询候选文章（其他源，30 天内） ----
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    candidate_query = (
        select(Article)
        .where(
            Article.source_id != main_article.source_id,
            Article.published_at >= cutoff,
        )
        .order_by(Article.published_at.desc().nullslast())
        .limit(200)
    )

    candidate_result = await db.execute(candidate_query)
    candidates = candidate_result.scalars().all()

    if not candidates:
        logger.info(f"聚合对比: 文章 #{article_id} 无候选文章")
        return {
            "main_article": main_article,
            "related_sources": [],
            "common_points": [],
            "different_points": [],
        }

    # 批量获取候选文章的源信息
    candidate_source_ids = {c.source_id for c in candidates}
    src_query = await db.execute(
        select(Source.id, Source.name).where(Source.id.in_(candidate_source_ids))
    )
    source_map: dict[int, str] = {s[0]: s[1] for s in src_query.all()}

    # ---- 第 3 步：评分排序 ----
    scored: list[dict] = []

    for candidate in candidates:
        candidate_tags: list[str] = candidate.tags or []
        candidate_title: str = candidate.title or ""
        candidate_keywords: set[str] = _extract_title_keywords(candidate_title)

        # 标签重叠计数
        tag_overlap = len(set(main_tags) & set(candidate_tags))
        # 标题关键词重叠计数
        keyword_overlap = len(main_keywords & candidate_keywords)

        # 完全没有重叠的跳过
        if tag_overlap == 0 and keyword_overlap == 0:
            continue

        # 计算总分
        score = (
            tag_overlap * 2.0
            + keyword_overlap * 1.0
            + _recency_bonus(candidate.published_at)
        )

        # 归一化相似度分数（0-1 范围）
        similarity_score = round(min(score / 10.0, 1.0), 2)

        # 视角分类
        perspective = _classify_perspective(tag_overlap, keyword_overlap)

        # 重叠关键词列表（用于前端展示）
        overlap_kw = list(main_keywords & candidate_keywords)

        scored.append({
            "article": candidate,
            "source_name": source_map.get(candidate.source_id, "未知来源"),
            "perspective": perspective,
            "overlap_keywords": overlap_kw[:8],  # 最多 8 个
            "similarity_score": similarity_score,
            "tag_overlap": tag_overlap,
            "keyword_overlap": keyword_overlap,
            "raw_score": score,
        })

    # 按分数降序排列
    scored.sort(key=lambda x: (-x["raw_score"], -(x["tag_overlap"])))

    # 取 top N
    top_results = scored[:limit]

    # ---- 第 4 步：构建响应 ----
    related_sources = []
    for item in top_results:
        art = item["article"]
        related_sources.append({
            "article": {
                "id": art.id,
                "title": art.title,
                "source_id": art.source_id,
                "source_name": item["source_name"],
                "summary": art.summary,
                "published_at": art.published_at.isoformat() if art.published_at else None,
                "image_url": art.image_url,
                "url": art.url,
                "tags": art.tags,
            },
            "perspective": item["perspective"],
            "overlap_keywords": item["overlap_keywords"],
            "similarity_score": item["similarity_score"],
        })

    # 生成共同点和不同点
    common_points = _generate_common_points(main_keywords, related_sources)
    different_points = _generate_different_points(main_tags, related_sources)

    logger.info(
        f"聚合对比完成: 文章 #{article_id} 找到 {len(related_sources)} 篇相关文章"
    )

    return {
        "main_article": main_article,
        "related_sources": related_sources,
        "common_points": common_points,
        "different_points": different_points,
    }
