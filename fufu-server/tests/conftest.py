"""
fufu新闻 - 测试夹具
===================
pytest 异步测试配置，提供：
- 内存数据库（每次测试独立隔离）
- 异步 HTTP 测试客户端
- 认证 token 自动获取
"""
import pytest
import pytest_asyncio
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# 确保项目路径正确
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import Base, get_db
from app.core.config import settings
from app.main import app

# ========== 内存数据库 ==========
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


def _create_default_user(session):
    """在测试数据库中创建默认用户"""
    from app.models.user import User
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    user = User(
        username=settings.default_username,
        password_hash=pwd_context.hash(settings.default_password),
        settings={},
    )
    session.add(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """每个测试函数独立的数据库会话（含默认用户）"""
    # 创建所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        # FTS5 虚拟表（测试用：无 content_rowid 约束，避免 in-memory DB 外键问题）
        await conn.exec_driver_sql(
            "CREATE VIRTUAL TABLE IF NOT EXISTS article_fts USING fts5(title, content)"
        )

    async with TestSessionLocal() as session:
        # 创建默认用户（认证测试需要）
        _create_default_user(session)
        await session.commit()
        yield session
        await session.rollback()

    # 清理所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    """带测试数据库的 HTTP 客户端"""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def auth_client(client: AsyncClient):
    """已认证的 HTTP 客户端（自动获取 token）"""
    resp = await client.post("/api/v1/auth/token", data={
        "username": settings.default_username,
        "password": settings.default_password,
    })
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
    return client
