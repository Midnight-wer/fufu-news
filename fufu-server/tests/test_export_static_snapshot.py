"""公开新闻快照导出的单元测试。"""
import json
import sqlite3
from datetime import datetime, timezone

from scripts.export_static_snapshot import build_snapshot, export_snapshot


NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
PUBLIC_FIELDS = {
    "id",
    "source_id",
    "title",
    "url",
    "content",
    "summary",
    "author",
    "published_at",
    "fetched_at",
    "image_url",
    "tags",
    "source_name",
    "source_folder",
    "view_count",
}


def create_database(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE source (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            folder TEXT NOT NULL
        );
        CREATE TABLE article (
            id INTEGER PRIMARY KEY,
            source_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            content TEXT,
            summary TEXT,
            author TEXT,
            published_at DATETIME,
            fetched_at DATETIME NOT NULL,
            image_url TEXT,
            is_read BOOLEAN NOT NULL DEFAULT 0,
            is_favorite BOOLEAN NOT NULL DEFAULT 0,
            is_later BOOLEAN NOT NULL DEFAULT 0,
            read_progress REAL NOT NULL DEFAULT 0,
            tags JSON NOT NULL DEFAULT '[]',
            deep_summary JSON
        );
        CREATE TABLE article_stats (
            id INTEGER PRIMARY KEY,
            article_id INTEGER NOT NULL,
            view_count INTEGER NOT NULL DEFAULT 0,
            comment_count INTEGER NOT NULL DEFAULT 0,
            collect_count INTEGER NOT NULL DEFAULT 0,
            hot_score REAL NOT NULL DEFAULT 0,
            calculated_at DATETIME
        );
        CREATE TABLE view_log (
            id INTEGER PRIMARY KEY,
            article_id INTEGER NOT NULL,
            ip_address TEXT NOT NULL,
            viewed_at DATETIME NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO source VALUES (1, '示例源', 'https://private.example/rss', '科技')"
    )
    conn.executemany(
        """
        INSERT INTO article (
            id, source_id, title, url, content, summary, author, published_at,
            fetched_at, image_url, is_read, is_favorite, tags
        ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
        """,
        [
            (
                1,
                "最新文章",
                "https://example.com/1",
                "<p>最新正文</p>",
                "最新摘要",
                "作者甲",
                "2026-11-16 10:00:00",
                "2026-11-16 10:05:00",
                1,
                1,
                '["AI", "科技"]',
            ),
            (
                2,
                "次新文章",
                "https://example.com/2",
                "<p>无摘要时的正文</p>",
                None,
                None,
                "2026-11-15 10:00:00",
                "2026-11-15 10:05:00",
                0,
                0,
                '["AI"]',
            ),
            (
                3,
                "热榜旧文",
                "https://example.com/3",
                "<p>旧文正文</p><script>alert(1)</script>",
                "旧文摘要",
                None,
                "2026-10-01 10:00:00",
                "2026-10-01 10:05:00",
                0,
                0,
                '[]',
            ),
        ],
    )
    conn.execute(
        "INSERT INTO article_stats VALUES (1, 3, 99, 0, 0, 88.5, '2026-11-16 11:00:00')"
    )
    conn.executemany(
        "INSERT INTO view_log (article_id, ip_address, viewed_at) VALUES (?, ?, ?)",
        [
            (3, "192.0.2.1", "2026-11-16 11:30:00"),
            (3, "192.0.2.2", "2026-11-16 11:35:00"),
            (2, "192.0.2.3", "2026-11-15 12:30:00"),
        ],
    )
    conn.commit()
    conn.close()


def test_snapshot_uses_public_fields_and_includes_hot_articles(tmp_path):
    db_path = tmp_path / "news.db"
    create_database(db_path)

    snapshot = build_snapshot(db_path, latest_limit=2, hot_limit=2, now=NOW)

    assert snapshot["version"] == 1
    assert snapshot["generated_at"] == "2026-11-16T12:00:00Z"
    assert [article["id"] for article in snapshot["articles"]] == [1, 2, 3]
    assert all(set(article) == PUBLIC_FIELDS for article in snapshot["articles"])
    serialized = json.dumps(snapshot, ensure_ascii=False)
    for private_name in (
        "is_read",
        "is_favorite",
        "is_later",
        "read_progress",
        "deep_summary",
        "ip_address",
        "private.example",
    ):
        assert private_name not in serialized
    assert snapshot["articles"][2]["view_count"] == 99
    assert snapshot["articles"][1]["summary"] == "无摘要时的正文"
    assert snapshot["hot"]["day"] == [3, 2]
    assert snapshot["hot"]["week"][0] == 3
    assert snapshot["hot"]["month"][0] == 3
    assert snapshot["hot_keywords"][:2] == ["AI", "科技"]
    assert snapshot["categories"] == [{"name": "科技", "count": 3}]


def test_empty_database_has_empty_public_collections(tmp_path):
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE source (id INTEGER PRIMARY KEY, name TEXT, url TEXT, folder TEXT);
        CREATE TABLE article (
            id INTEGER PRIMARY KEY, source_id INTEGER, title TEXT, url TEXT,
            content TEXT, summary TEXT, author TEXT, published_at DATETIME,
            fetched_at DATETIME, image_url TEXT, tags JSON
        );
        CREATE TABLE article_stats (article_id INTEGER, view_count INTEGER, hot_score REAL);
        CREATE TABLE view_log (article_id INTEGER, ip_address TEXT, viewed_at DATETIME);
        """
    )
    conn.close()

    snapshot = build_snapshot(db_path, now=NOW)

    assert snapshot["articles"] == []
    assert snapshot["categories"] == []
    assert snapshot["hot_keywords"] == []
    assert snapshot["hot"] == {"day": [], "week": [], "month": []}


def test_export_writes_utf8_json_without_private_fields(tmp_path):
    db_path = tmp_path / "news.db"
    output_path = tmp_path / "news.json"
    create_database(db_path)

    export_snapshot(db_path, output_path, latest_limit=2, hot_limit=2, now=NOW)

    raw = output_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert "最新文章" in raw
    assert data["articles"][0]["title"] == "最新文章"
    assert "is_favorite" not in raw
    assert "192.0.2.1" not in raw
