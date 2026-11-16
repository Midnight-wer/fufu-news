"""将本地 SQLite 新闻只读导出为可公开发布的静态快照。"""
import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "fufu.db"
DEFAULT_OUTPUT = PROJECT_ROOT / "fufu-web" / "public" / "data" / "news.json"
MAX_CONTENT_LENGTH = 80_000

ARTICLE_SELECT = """
    SELECT
        a.id, a.source_id, a.title, a.url, a.content, a.summary, a.author,
        a.published_at, a.fetched_at, a.image_url, a.tags,
        s.name AS source_name, s.folder AS source_folder,
        COALESCE(stats.view_count, 0) AS view_count
    FROM article a
    LEFT JOIN source s ON s.id = a.source_id
    LEFT JOIN article_stats stats ON stats.article_id = a.id
"""


class _TextExtractor(HTMLParser):
    """从 RSS HTML 中提取纯文本，并忽略脚本与样式内容。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignored_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data):
        if not self.ignored_depth:
            self.parts.append(data)


def plain_text(html):
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(str(html))
    parser.close()
    return " ".join("".join(parser.parts).split())


def iso_datetime(value):
    """将 SQLite 中按 UTC 保存的时间转换为浏览器友好的 ISO 格式。"""
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text.replace(" ", "T")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def public_article(row):
    content = row["content"] or None
    if content and len(content) > MAX_CONTENT_LENGTH:
        content = content[:MAX_CONTENT_LENGTH]
    try:
        tags = json.loads(row["tags"] or "[]")
    except (TypeError, json.JSONDecodeError):
        tags = []
    if not isinstance(tags, list):
        tags = []

    summary = plain_text(row["summary"]) or plain_text(content)[:240] or None
    return {
        "id": row["id"],
        "source_id": row["source_id"],
        "title": row["title"] or "无标题",
        "url": row["url"] or "",
        "content": content,
        "summary": summary,
        "author": row["author"],
        "published_at": iso_datetime(row["published_at"]),
        "fetched_at": iso_datetime(row["fetched_at"]),
        "image_url": row["image_url"],
        "tags": [str(tag) for tag in tags if str(tag).strip()][:12],
        "source_name": row["source_name"] or "未知来源",
        "source_folder": row["source_folder"] or "未分类",
        "view_count": int(row["view_count"] or 0),
    }


def connect_readonly(database):
    path = Path(database).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"新闻数据库不存在: {path}")
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def hot_article_ids(conn, cutoff, limit):
    """按窗口浏览量排名；无浏览数据时用热度和发布时间补足榜单。"""
    rows = conn.execute(
        """
        SELECT a.id
        FROM article a
        LEFT JOIN view_log v
            ON v.article_id = a.id AND v.viewed_at >= ?
        LEFT JOIN article_stats stats ON stats.article_id = a.id
        GROUP BY a.id
        ORDER BY
            COUNT(v.article_id) DESC,
            COALESCE(stats.hot_score, 0) DESC,
            COALESCE(a.published_at, a.fetched_at) DESC,
            a.id DESC
        LIMIT ?
        """,
        (cutoff.strftime("%Y-%m-%d %H:%M:%S"), limit),
    ).fetchall()
    return [row["id"] for row in rows]


def build_snapshot(database, latest_limit=240, hot_limit=10, now=None):
    if latest_limit < 1 or hot_limit < 1:
        raise ValueError("latest_limit 和 hot_limit 必须大于 0")
    generated_at = now or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    conn = connect_readonly(database)
    try:
        latest_rows = conn.execute(
            ARTICLE_SELECT
            + """
            ORDER BY COALESCE(a.published_at, a.fetched_at) DESC, a.id DESC
            LIMIT ?
            """,
            (latest_limit,),
        ).fetchall()
        rows_by_id = {row["id"]: row for row in latest_rows}
        hot = {
            "day": hot_article_ids(conn, generated_at - timedelta(days=1), hot_limit),
            "week": hot_article_ids(conn, generated_at - timedelta(days=7), hot_limit),
            "month": hot_article_ids(conn, generated_at - timedelta(days=30), hot_limit),
        }

        extra_ids = []
        for article_id in dict.fromkeys(
            article_id for ranking in hot.values() for article_id in ranking
        ):
            if article_id not in rows_by_id:
                extra_ids.append(article_id)
        if extra_ids:
            placeholders = ",".join("?" for _ in extra_ids)
            extra_rows = conn.execute(
                ARTICLE_SELECT + f" WHERE a.id IN ({placeholders})", extra_ids
            ).fetchall()
            rows_by_id.update({row["id"]: row for row in extra_rows})

        ordered_ids = [row["id"] for row in latest_rows] + extra_ids
        articles = [public_article(rows_by_id[article_id]) for article_id in ordered_ids]
    finally:
        conn.close()

    category_counts = Counter(article["source_folder"] for article in articles)
    categories = [
        {"name": name, "count": count}
        for name, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    tag_counts = Counter(tag for article in articles for tag in article["tags"])
    first_seen = {}
    for article in articles:
        for tag in article["tags"]:
            first_seen.setdefault(tag, len(first_seen))
    hot_keywords = [
        tag
        for tag, _ in sorted(
            tag_counts.items(), key=lambda item: (-item[1], first_seen[item[0]])
        )[:8]
    ]

    return {
        "version": 1,
        "generated_at": generated_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "articles": articles,
        "categories": categories,
        "hot": hot,
        "hot_keywords": hot_keywords,
    }


def export_snapshot(
    database, output, latest_limit=240, hot_limit=10, now=None
):
    snapshot = build_snapshot(database, latest_limit, hot_limit, now)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--latest", type=int, default=240, help="最新文章数量")
    parser.add_argument("--hot-limit", type=int, default=10, help="每个热榜的文章数量")
    args = parser.parse_args()

    snapshot = export_snapshot(
        args.database, args.output, latest_limit=args.latest, hot_limit=args.hot_limit
    )
    size_kb = args.output.stat().st_size / 1024
    print(
        f"已导出 {len(snapshot['articles'])} 篇公开文章，"
        f"{len(snapshot['categories'])} 个分类，文件 {size_kb:.1f} KB：{args.output}"
    )


if __name__ == "__main__":
    main()
