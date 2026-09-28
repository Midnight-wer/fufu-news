"""
fufu新闻 - 全网搜索功能测试脚本
=====================================
测试各项搜索功能的可用性，无需启动完整的 Web 服务器。

运行方式：在 fufu-server 目录下执行
    python test_search.py

测试项目：
1. fallback 本地数据集搜索（engine_fallback）
2. 本地文章 FTS5 全文搜索（engine_local）
3. 完整搜索流程（ddgs + fallback 兜底）
"""
import asyncio
import sys
# 将当前目录加入模块搜索路径，确保能从命令行直接运行
sys.path.insert(0, ".")

async def main():
    """
    主测试函数——依次测试各项搜索功能。

    对每个测试关键词：
    1. 输出 fallback 数据集搜索结果（前 3 条）
    2. 输出本地文章搜索匹配条数
    3. 执行完整搜索并输出最终结果（前 3 条）

    注意：engine_fallback 和 engine_local 可能在某些版本中已被移除，
    如果导入失败，脚本会抛出 ImportError，这是正常的。
    """
    from app.services.search import search_web, engine_fallback, engine_local

    # 测试关键词列表：覆盖中英文、不同领域
    queries = ["英语", "原神", "AI", "科技", "动漫"]

    for q in queries:
        print(f"\n{'='*60}")
        print(f"测试关键词: {q!r}")
        print(f"{'='*60}")

        # 1. 测试 fallback 本地数据集搜索
        fb = engine_fallback(q)
        print(f"  [fallback] → {len(fb)} 条")
        for r in fb[:3]:  # 只显示前 3 条
            print(f"    - {r['title'][:60]}")

        # 2. 测试本地文章 FTS5 搜索
        local = await engine_local(q)
        print(f"  [本地] → {len(local)} 条")

        # 3. 完整搜索流程（8 秒超时，ddgs + fallback 兜底）
        results = await search_web(q)
        print(f"  [最终] → {len(results)} 条")
        for r in results[:3]:  # 只显示前 3 条
            print(f"    - {r.get('title', '')[:80]}")

        # 如果所有搜索都没有结果，输出警告
        if not results:
            print(f"  ⚠️ 无结果！需要修复！")

if __name__ == "__main__":
    # 使用 asyncio.run() 运行异步主函数
    asyncio.run(main())
