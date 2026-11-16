"""
fufu新闻 - 健康检查接口
===========================
提供系统健康状态检查端点：

- GET /health → 检查应用和数据库的运行状态
"""
from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import async_session

# 创建健康检查路由实例
router = APIRouter()


@router.get("")
async def health_check():
    """
    系统健康检查——GET /api/v1/health

    检查项：
    1. 数据库连接是否正常（执行 SELECT 1 测试查询）

    无需认证，公开访问。

    返回:
        dict: {
            "status": "fufu已苏醒 ✨",
            "app": "fufu新闻",
            "version": "1.0.0",
            "database": "活蹦乱跳" | "数据库睡着了zzz"
        }
    """
    db_ok = True
    try:
        # 执行最简单的数据库查询来验证连接正常
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return {
        "status": "fufu已苏醒 ✨",
        "app": "fufu新闻",
        "version": "1.0.0",
        "database": "活蹦乱跳" if db_ok else "数据库睡着了zzz",
    }
