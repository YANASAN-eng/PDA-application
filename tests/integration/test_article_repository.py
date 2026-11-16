import sqlite3
from datetime import date, datetime

import pytest

from pda.db.article_repository import ArticleRepository
from pda.db.migrate import connect, migrate
from pda.domain.article import Article, Feed

FEED = Feed(name="Example", url="https://example.com/feed.xml")
OTHER = Feed(name="Other", url="https://other.example.com/rss")
FETCHED = datetime(2026, 11, 16, 6, 0)
NOW = datetime(2026, 11, 16, 6, 5)


@pytest.fixture
def conn():
    c = connect(":memory:")
    migrate(c)
    yield c
    c.close()


@pytest.fixture
def repo(conn):
    r = ArticleRepository(conn)
    r.register_feeds([FEED, OTHER])
    return r


def article(n=1, feed=FEED, title=None, description="", published_at=None):
    return Article(
        feed=feed,
        url=f"https://example.com/{n}",
        title=title or f"量子の記事{n}",
        description=description,
        published_at=published_at,
        fetched_at=FETCHED,
    )


def count(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


# --- フィード --------------------------------------------------------------
def test_同じURLのフィードを登録し直すと名前が設定に合わせて変わる(repo):
    repo.register_feeds([Feed(name="Example (新しい名前)", url=FEED.url)])
    repo.add_new([article(1)])

    assert repo.list_all()[0].feed == Feed(name="Example (新しい名前)", url=FEED.url)


def test_登録していないフィードの記事は保存できない(repo):
    unknown = Feed(name="Unknown", url="https://unknown.example.com/rss")

    with pytest.raises(LookupError):
        repo.add_new([article(1, feed=unknown)])


# --- 保存と取り出し ---------------------------------------------------------
def test_保存した記事を取り出すと同じ内容でidが振られている(repo):
    a = article(1, feed=OTHER, description="概要", published_at=datetime(2026, 11, 15, 21, 0))

    added = repo.add_new([a])

    assert added == [a] and isinstance(a.id, int)
    assert repo.list_all() == [a]


def test_既にあるURLの記事は保存せず元の記事も変えない(repo):
    repo.add_new([article(1, title="量子の記事(初版)")])

    added = repo.add_new([article(1, title="量子の記事(改題)")])

    assert added == []
    assert [a.title for a in repo.list_all()] == ["量子の記事(初版)"]


def test_1回の保存の中で同じURLが重なったら最初の1件だけ保存する(repo):
    first, dup = article(1, title="一件目"), article(1, title="二件目")

    added = repo.add_new([first, dup])

    assert added == [first] and dup.id is None
    assert [a.title for a in repo.list_all()] == ["一件目"]


def test_一覧は保存した順(repo):
    a, b, c = article(3), article(1), article(2)
    repo.add_new([a, b])
    repo.add_new([c])

    assert repo.list_all() == [a, b, c]


def test_保存の途中で失敗したら1件も残らずidも振られない(repo, conn):
    conn.execute(
        "CREATE TRIGGER fail_on_bomb BEFORE INSERT ON articles WHEN NEW.title = '爆発'"
        " BEGIN SELECT RAISE(ABORT, 'テスト用の失敗'); END"
    )
    ok, bomb = article(1), article(2, title="爆発")

    with pytest.raises(sqlite3.IntegrityError):
        repo.add_new([ok, bomb])

    assert (count(conn, "articles"), ok.id) == (0, None)


def test_マイクロ秒を含む日時の記事は保存できない(repo):
    a = Article(feed=FEED, url="https://example.com/1", title="量子", fetched_at=datetime(2026, 11, 16, 6, 0, 0, 1))

    with pytest.raises(ValueError):
        repo.add_new([a])


# --- 要約 ------------------------------------------------------------------
def test_未要約の記事だけを保存した順に返す(repo):
    a, b, c = article(1), article(2), article(3)
    repo.add_new([a, b, c])
    b.set_summary("要約", now=NOW)
    repo.save_summaries([b])

    assert repo.list_unsummarized() == [a, c]


def test_要約を保存すると取り出したときに要約が付いている(repo):
    a = article(1)
    repo.add_new([a])

    a.set_summary("要約", now=NOW)
    repo.save_summaries([a])

    [loaded] = repo.list_all()
    assert (loaded.summary, loaded.summarized_at) == ("要約", NOW)


def test_保存前の記事の要約は保存できない(repo):
    a = article(1)
    a.set_summary("要約", now=NOW)

    with pytest.raises(ValueError):
        repo.save_summaries([a])


def test_要約のない記事は要約の保存に渡せない(repo):
    a = article(1)
    repo.add_new([a])

    with pytest.raises(ValueError):
        repo.save_summaries([a])


def test_ある日に要約した件数を数える(repo):
    a, b, c = article(1), article(2), article(3)
    repo.add_new([a, b, c])
    a.set_summary("要約", now=datetime(2026, 11, 15, 23, 59, 59))
    b.set_summary("要約", now=datetime(2026, 11, 16, 0, 0))
    c.set_summary("要約", now=datetime(2026, 11, 16, 23, 59, 59))
    repo.save_summaries([a, b, c])

    assert repo.count_summarized_on(date(2026, 11, 16)) == 2
    assert repo.count_summarized_on(date(2026, 11, 17)) == 0
