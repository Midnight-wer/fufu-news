"""
fufu新闻 - v1 路由聚合器
==========================
将所有 v1 版本的 API 子路由汇总注册到同一个 APIRouter 上。

路由结构：
- /health      → 健康检查
- /auth        → 用户认证（登录/令牌）
- /sources     → 订阅源 CRUD + 抓取
- /articles    → 文章列表/详情/更新/搜索
- /ai          → AI 对话/摘要/标签
- /opml        → OPML 导入/导出
- /achievements → 成就系统
- /history         → 阅读历史
- /search          → 全网搜索
- /recommendations → 个性化推荐

所有路由挂载在 /api/v1 前缀下（由 main.py 中的 app.include_router 设置）。
"""
from fastapi import APIRouter

from app.api.v1 import (
    achievements,
    ai,
    articles,
    auth,
    comments,
    folders,
    health,
    history,
    honeypot,
    opml,
    profile,
    ranking,
    recommendations,
    rss_proxy,
    search,
    sources,
)

# 创建 v1 路由聚合器实例
router = APIRouter()

# 注册各模块的子路由
router.include_router(health.router, prefix="/health", tags=["健康检查"])
router.include_router(auth.router, prefix="/auth", tags=["认证"])
router.include_router(sources.router, prefix="/sources", tags=["订阅源"])
router.include_router(rss_proxy.router, prefix="/sources", tags=["RSS代理"])
router.include_router(articles.router, prefix="/articles", tags=["文章"])
router.include_router(ai.router, prefix="/ai", tags=["AI"])
router.include_router(opml.router, prefix="/opml", tags=["OPML"])
router.include_router(achievements.router, prefix="/achievements", tags=["成就"])
router.include_router(search.router, prefix="/search", tags=["全网搜索"])
router.include_router(ranking.router, prefix="/ranking", tags=["排行榜"])
router.include_router(history.router, prefix="/history", tags=["阅读历史"])
router.include_router(honeypot.router, tags=["蜜罐"])  # 蜜罐端点（诱捕爬虫）
router.include_router(folders.router, tags=["收藏夹文件夹"])
router.include_router(recommendations.router, prefix="/recommendations", tags=["个性化推荐"])
router.include_router(comments.router, tags=["评论"])
router.include_router(profile.router, prefix="/profile", tags=["画像"])
