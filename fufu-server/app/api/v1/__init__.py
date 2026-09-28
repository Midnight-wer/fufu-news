"""
fufu新闻 - v1 API 子包
==========================
第一版 API 端点模块集合。

包含的路由模块：
- health.py       : 健康检查接口
- auth.py         : 认证接口（登录/令牌）
- sources.py      : 订阅源 CRUD 接口
- articles.py     : 文章列表/查询/更新接口
- ai.py           : AI 对话/摘要/标签接口
- opml.py         : OPML 导入导出接口
- achievements.py : 成就系统接口
- search.py       : 全网搜索接口
- router.py       : 路由聚合器（将以上所有路由合并注册）
"""
