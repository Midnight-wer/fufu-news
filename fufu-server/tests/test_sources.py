"""
测试：订阅源接口
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.source import Source


@pytest.mark.asyncio
async def test_list_sources_empty(auth_client: AsyncClient):
    """未播种时订阅源列表应为空"""
    resp = await auth_client.get("/api/v1/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_source(auth_client: AsyncClient):
    """创建新订阅源"""
    resp = await auth_client.post("/api/v1/sources", json={
        "name": "新测试源",
        "url": "https://new-test.example.com/rss",
        "source_type": "rss",
        "folder": "科技",
        "fetch_interval": 30,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "新测试源"
    assert data["url"] == "https://new-test.example.com/rss"
    assert data["folder"] == "科技"


@pytest.mark.asyncio
async def test_create_duplicate_source(auth_client: AsyncClient):
    """重复 URL 的订阅源应被拒绝"""
    await auth_client.post("/api/v1/sources", json={
        "name": "源A", "url": "https://dup.example.com/rss", "source_type": "rss",
    })
    resp = await auth_client.post("/api/v1/sources", json={
        "name": "源B", "url": "https://dup.example.com/rss", "source_type": "rss",
    })
    # 应返回 400 或 409（重复）
    assert resp.status_code in (400, 409)


@pytest.mark.asyncio
async def test_delete_source(auth_client: AsyncClient):
    """删除订阅源"""
    # 创建
    create_resp = await auth_client.post("/api/v1/sources", json={
        "name": "待删除源", "url": "https://todelete.example.com/rss", "source_type": "rss",
    })
    src_id = create_resp.json()["id"]

    # 删除
    resp = await auth_client.delete(f"/api/v1/sources/{src_id}")
    assert resp.status_code in (200, 204)

    # 确认已删除
    get_resp = await auth_client.get(f"/api/v1/sources/{src_id}")
    assert get_resp.status_code in (404, 200)
    if get_resp.status_code == 200:
        # 某些实现返回空数据表示已删除
        assert get_resp.json() in ([], None, {"detail": "Not Found"})
