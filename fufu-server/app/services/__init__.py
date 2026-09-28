"""
fufu新闻 - 业务服务层包
===========================
封装核心业务逻辑的服务模块。

模块：
- fetcher.py   : RSS/网页抓取引擎（fetch_source 主入口）
- search.py    : 全网搜索服务（DuckDuckGo 集成）
- ai.py        : AI 大脑服务（摘要生成、标签生成、对话）
- scheduler.py : 定时任务调度（每 3 分钟全局抓取）
- opml.py      : OPML 导入导出处理
"""
