"""
测试：健康检查接口
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """健康检查应该返回 200 和正确状态"""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "app" in data
    assert data["app"] == "fufu新闻"


@pytest.mark.asyncio
async def test_health_check_database_ok(client: AsyncClient):
    """健康检查应确认数据库正常"""
    resp = await client.get("/api/v1/health")
    data = resp.json()
    assert data["database"] == "活蹦乱跳"
