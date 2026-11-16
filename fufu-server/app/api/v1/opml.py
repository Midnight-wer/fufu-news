"""
fufu新闻 - OPML 导入导出接口
================================
提供 OPML 格式的订阅源导入/导出 REST API：

- GET  /opml/export → 导出所有订阅源为 OPML XML 文件
- POST /opml/import → 从 OPML 文件导入订阅源

OPML（Outline Processor Markup Language）是 RSS 阅读器之间
通用的订阅源交换格式。
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.source import Source
from app.models.user import User
from app.services.opml import export_opml, import_opml

# 创建 OPML 路由实例
router = APIRouter(tags=["OPML"])


@router.get("/export")
async def export_sources(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    导出订阅源为 OPML 文件——GET /api/v1/opml/export

    将当前所有订阅源按照文件夹分组导出为 OPML 2.0 格式的 XML 文件。
    浏览器会自动触发文件下载（通过 Content-Disposition 头）。

    返回:
        PlainTextResponse: OPML XML 文件（MIME 类型 text/xml）

    异常:
        HTTPException(404): 没有任何订阅源可导出
    """
    result = await db.execute(select(Source).order_by(Source.folder, Source.name))
    sources = result.scalars().all()
    if not sources:
        raise HTTPException(status_code=404, detail="还没有订阅源可以导出呢～")

    # 生成 OPML XML 内容
    opml = export_opml(list(sources))

    # 以附件下载形式返回
    return PlainTextResponse(
        content=opml,
        media_type="text/xml",
        headers={"Content-Disposition": "attachment; filename=fufu-subscriptions.opml"},
    )


@router.post("/import")
async def import_sources(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    从 OPML 文件导入订阅源——POST /api/v1/opml/import

    解析上传的 OPML/XML 文件，将其中的 RSS 源导入到数据库。
    已存在的 URL 会自动跳过（不重复添加）。

    请求格式：multipart/form-data
    参数:
        file: 上传的 OPML 文件（.opml 或 .xml 后缀）

    返回:
        dict: {"message": "结果描述", "created": 新增数, "skipped": 跳过数}

    异常:
        HTTPException(400): 文件格式不正确 / 不是 OPML 文件 / 编码不是 UTF-8
    """
    # 验证文件扩展名
    if not file.filename or not file.filename.lower().endswith((".opml", ".xml")):
        raise HTTPException(status_code=400, detail="请上传 .opml 或 .xml 文件哦～")

    # 读取文件内容并解码为 UTF-8
    try:
        content = await file.read()
        xml_data = content.decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(status_code=400, detail="文件编码不是 UTF-8 呢，转换一下再试试～") from e

    # 解析 OPML 并导入
    try:
        result = await import_opml(xml_data, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # 构建友好的返回消息
    if result["created"] == 0 and result["skipped"] == 0:
        return {"message": "没有找到新的订阅源呢，可能都已经添加过啦～", **result}
    return {
        "message": f"✅ 新增了{result['created']}个订阅源，跳过了{result['skipped']}个已存在的～",
        **result
    }
