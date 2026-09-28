"""
fufu新闻 - OPML 处理服务
=============================
OPML（Outline Processor Markup Language）导入/导出服务。

OPML 是 RSS 阅读器之间通用的订阅源交换格式（XML）。
本模块实现了 OPML 2.0 标准的生成和解析功能。

- export_opml(): 将订阅源列表导出为 OPML XML 字符串
- import_opml(): 从 OPML XML 字符串解析并导入订阅源
"""
from lxml import etree
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.source import Source


def export_opml(sources: list[Source]) -> str:
    """
    将订阅源列表导出为 OPML 2.0 格式的 XML 字符串。

    按文件夹分组组织订阅源，结构如下：
    <opml version="2.0">
      <head><title>fufu新闻 订阅列表</title></head>
      <body>
        <outline text="文件夹名" title="文件夹名">
          <outline type="rss" text="源名称" title="源名称" xmlUrl="源URL"/>
        </outline>
      </body>
    </opml>

    参数:
        sources: 要导出的 Subscription ORM 对象列表

    返回:
        str: OPML XML 字符串（UTF-8 编码，带 XML 声明）
    """
    # 创建根元素
    opml = etree.Element("opml", version="2.0")
    head = etree.SubElement(opml, "head")
    title = etree.SubElement(head, "title")
    title.text = "fufu新闻 订阅列表"
    body = etree.SubElement(opml, "body")

    # 按文件夹分组
    folders: dict[str, list[Source]] = {}
    for s in sources:
        f = s.folder or "默认分组"
        folders.setdefault(f, []).append(s)

    # 生成 XML 结构
    for folder_name, items in folders.items():
        outline = etree.SubElement(body, "outline", text=folder_name, title=folder_name)
        for s in items:
            etree.SubElement(
                outline,
                "outline",
                type="rss",
                text=s.name,
                title=s.name,
                xmlUrl=s.url,
            )

    # 序列化为字符串（带 XML 声明和美化缩进）
    return etree.tostring(opml, encoding="unicode", pretty_print=True, xml_declaration=True)


async def import_opml(xml_data: str, db: AsyncSession) -> dict:
    """
    从 OPML XML 字符串解析并导入订阅源到数据库。

    遍历所有 <outline> 元素，提取含有 xmlUrl 属性的 RSS 源，
    跳过已存在的 URL（不重复添加）。
    文件夹信息从父级 <outline> 的 text 属性继承。

    参数:
        xml_data: OPML XML 字符串（UTF-8 编码）
        db: 数据库会话

    返回:
        dict: {"created": 新增数量, "skipped": 跳过数量}

    异常:
        ValueError: OPML 格式不正确（XML 解析失败）
    """
    try:
        root = etree.fromstring(xml_data.encode("utf-8"))
    except Exception:
        raise ValueError("OPML 文件格式不正确呢～")

    created = 0
    skipped = 0

    # 遍历所有 outline 元素
    for outline in root.iter("outline"):
        # 获取 RSS 源 URL（xmlUrl 属性是 OPML 标准中表示 Feed URL 的属性）
        xml_url = outline.get("xmlUrl") or outline.get("xmlurl") or outline.get("url")
        if not xml_url:
            continue  # 不是 Feed 项，跳过

        # 获取源名称
        text = outline.get("text") or outline.get("title") or xml_url

        # 从父元素获取文件夹名
        folder = "默认分组"
        parent = outline.getparent()
        if parent is not None and parent.get("text"):
            folder = parent.get("text")

        # 检查是否已存在相同 URL 的源
        result = await db.execute(select(Source).where(Source.url == xml_url))
        if result.scalar_one_or_none():
            skipped += 1
            continue

        # 创建新源
        source = Source(
            name=text[:200],  # 截断过长的名称
            url=xml_url,
            source_type="rss",  # OPML 导入的默认为 RSS 类型
            folder=folder,
        )
        db.add(source)
        created += 1

    # 提交到数据库
    await db.flush()
    return {"created": created, "skipped": skipped}
