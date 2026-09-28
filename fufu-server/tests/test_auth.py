"""
测试：认证接口
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """使用默认账号登录应该成功"""
    resp = await client.post("/api/v1/auth/token", data={
        "username": "fufu",
        "password": "fufu123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """错误密码应该返回 401"""
    resp = await client.post("/api/v1/auth/token", data={
        "username": "fufu",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(client: AsyncClient):
    """未认证访问受保护端点应返回 401"""
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_token(auth_client: AsyncClient):
    """携带 token 访问受保护端点应返回 200"""
    resp = await auth_client.get("/api/v1/sources")
    assert resp.status_code == 200
