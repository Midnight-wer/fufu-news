"""
测试：文章接口
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.article import Article
from app.models.source import Source


@pytest.mark.asyncio
async def test_list_articles_empty(auth_client: AsyncClient):
    """空数据库应返回空列表"""
    resp = await auth_client.get("/api/v1/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["articles"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_articles_with_data(auth_client: AsyncClient, db_session: AsyncSession):
    """有数据时应返回文章列表"""
    src = Source(name="测试源", url="https://example.com/rss", folder="科技")
    db_session.add(src)
    await db_session.flush()

    article = Article(
        source_id=src.id, title="测试文章", url="https://example.com/1",
        summary="这是一篇测试文章", content="<p>正文内容</p>",
    )
    db_session.add(article)
    await db_session.commit()

    resp = await auth_client.get("/api/v1/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["articles"]) >= 1
    assert data["articles"][0]["title"] == "测试文章"


@pytest.mark.asyncio
async def test_get_article_by_id(auth_client: AsyncClient, db_session: AsyncSession):
    """按 ID 获取文章详情"""
    src = Source(name="测试源2", url="https://example2.com/rss", folder="游戏")
    db_session.add(src)
    await db_session.flush()

    article = Article(
        source_id=src.id, title="详情测试", url="https://example2.com/1",
        summary="详情摘要", content="<p>详情正文</p>",
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)

    resp = await auth_client.get(f"/api/v1/articles/{article.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "详情测试"


@pytest.mark.asyncio
async def test_get_article_not_found(auth_client: AsyncClient):
    """不存在的文章应返回 404"""
    resp = await auth_client.get("/api/v1/articles/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_article_status(auth_client: AsyncClient, db_session: AsyncSession):
    """更新文章已读/收藏状态"""
    src = Source(name="状态测试源", url="https://example3.com/rss", folder="动漫")
    db_session.add(src)
    await db_session.flush()

    article = Article(
        source_id=src.id, title="状态测试", url="https://example3.com/1",
        summary="测试状态更新", is_read=False, is_favorite=False,
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)

    resp = await auth_client.patch(
        f"/api/v1/articles/{article.id}",
        json={"is_read": True, "is_favorite": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_read"] is True
    assert data["is_favorite"] is True
