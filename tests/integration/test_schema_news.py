"""ニュース側のスキーマ(feeds / articles)の制約のテスト。"""

import shutil
import sqlite3

import pytest

from pda.db.migrate import MIGRATIONS_DIR, connect, current_version, migrate

Bad = sqlite3.IntegrityError
OK_TIME = "2026-11-16T06:00:00"


@pytest.fixture
def db():
    conn = connect(":memory:")
    migrate(conn)
    yield conn
    conn.close()


def add_feed(db, url="https://example.com/feed.xml", name="Example"):
    return db.execute("INSERT INTO feeds (name, url) VALUES (?, ?)", (name, url)).lastrowid


def add_article(db, feed_id, url="https://example.com/a", title="量子計算", published_at=None,
                fetched_at=OK_TIME, summary=None, summarized_at=None):
    db.execute(
        "INSERT INTO articles (feed_id, url, title, published_at, fetched_at, summary, summarized_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (feed_id, url, title, published_at, fetched_at, summary, summarized_at),
    )


def test_正しい記事は保存でき概要文は省略すると空文字(db):
    add_article(db, add_feed(db))

    assert db.execute("SELECT description, summary FROM articles").fetchone() == ("", None)


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://example.com/a", "", "example.com"])
def test_httpとhttps以外のURLの記事は保存できない(db, url):
    feed_id = add_feed(db)
    with pytest.raises(Bad):
        add_article(db, feed_id, url=url)


def test_大文字のHTTPSで始まるURLは保存できる(db):
    add_article(db, add_feed(db), url="HTTPS://EXAMPLE.COM/a")


def test_httpとhttps以外のURLのフィードは保存できない(db):
    with pytest.raises(Bad):
        add_feed(db, url="javascript:alert(1)")


def test_同じURLのフィードは2つ作れない(db):
    add_feed(db)
    with pytest.raises(Bad):
        add_feed(db)


def test_同じURLの記事は2つ作れない(db):
    feed_id = add_feed(db)
    add_article(db, feed_id)
    with pytest.raises(Bad):
        add_article(db, feed_id)


def test_存在しないフィードの記事は保存できない(db):
    with pytest.raises(Bad):
        add_article(db, 999)


@pytest.mark.parametrize("title", ["", "  "])
def test_空のタイトルの記事は保存できない(db, title):
    feed_id = add_feed(db)
    with pytest.raises(Bad):
        add_article(db, feed_id, title=title)


@pytest.mark.parametrize("column", ["published_at", "fetched_at"])
@pytest.mark.parametrize("value", ["2026-11-16", "2026-02-30T06:00:00", "06:00"])
def test_日時はYYYY_MM_DDTHH_MM_SS以外を保存できない(db, column, value):
    feed_id = add_feed(db)
    with pytest.raises(Bad):
        add_article(db, feed_id, **{column: value})


@pytest.mark.parametrize(
    "summary, summarized_at",
    [("要約", None), (None, OK_TIME)],
    ids=["要約文だけ", "要約日時だけ"],
)
def test_要約文と要約日時は片方だけでは保存できない(db, summary, summarized_at):
    feed_id = add_feed(db)
    with pytest.raises(Bad):
        add_article(db, feed_id, summary=summary, summarized_at=summarized_at)


def test_空文字の要約は保存できる(db):
    add_article(db, add_feed(db), summary="", summarized_at=OK_TIME)


def test_記事のあるフィードは消せない(db):
    feed_id = add_feed(db)
    add_article(db, feed_id)
    with pytest.raises(Bad):
        db.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))


def test_版2のデータは版3に上げても残る(tmp_path):
    v2_dir = tmp_path / "v2"
    v2_dir.mkdir()
    for name in ("0001_initial.sql", "0002_add_task_detail.sql"):
        shutil.copy(MIGRATIONS_DIR / name, v2_dir)
    conn = connect(":memory:")
    migrate(conn, v2_dir)
    conn.execute("INSERT INTO tasks (title, priority, created_at, detail) VALUES ('牛乳を買う', 'LOW', ?, 'シチュー用')", (OK_TIME,))

    migrate(conn)

    assert current_version(conn) >= 3
    assert conn.execute("SELECT title, detail FROM tasks").fetchall() == [("牛乳を買う", "シチュー用")]
    conn.close()
