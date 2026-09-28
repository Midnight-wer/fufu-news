"""
测试：搜索接口
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_missing_query(auth_client: AsyncClient):
    """缺少 q 参数时，搜索端点可能返回默认结果或 422"""
    resp = await auth_client.get("/api/v1/search/web")
    # 两种行为均可接受：422（参数校验）或 200（默认空搜索）
    assert resp.status_code in (200, 422)


@pytest.mark.asyncio
async def test_search_with_query(auth_client: AsyncClient):
    """正常搜索请求"""
    resp = await auth_client.get("/api/v1/search/web", params={"q": "人工智能"})
    # 可能返回 200（搜索成功）或 503（ddgs 不可达），两种都合理
    assert resp.status_code in (200, 503)


@pytest.mark.asyncio
async def test_search_empty_query(auth_client: AsyncClient):
    """空查询应返回 422"""
    resp = await auth_client.get("/api/v1/search/web", params={"q": ""})
    assert resp.status_code == 422
