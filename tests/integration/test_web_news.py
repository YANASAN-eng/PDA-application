from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from pda.db.article_repository import ArticleRepository
from pda.db.migrate import connect
from pda.domain.article import Article, Feed
from pda.web.app import create_app

NOW = datetime(2026, 11, 16, 21, 0)
FEED = Feed(name="Zenn: quantum", url="https://zenn.dev/topics/quantum/feed")


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "pda.db"


@pytest.fixture
def client(db_path):
    return TestClient(create_app(db_path, clock=lambda: NOW))


@pytest.fixture
def articles(client, db_path):
    """画面を通さずに記事を用意する(キーワードは 0004 の初期データ: 量子・AI など)。"""
    conn = connect(db_path)
    repo = ArticleRepository(conn)
    repo.register_feeds([FEED])
    yield repo
    conn.close()


_n = 0


def add(repo, title, *, summarized_on=None, published_at=None, summary="要約です", description=""):
    """記事を保存し、summarized_on(datetime)があれば要約済みにする。"""
    global _n
    _n += 1
    a = Article(
        feed=FEED, url=f"https://zenn.dev/articles/{_n}", title=title, description=description,
        published_at=published_at, fetched_at=datetime(2026, 11, 15, 6, 0),
    )
    repo.add_new([a])
    if summarized_on:
        a.set_summary(summary, now=summarized_on)
        repo.save_summaries([a])
    return a


def appear_in_order(html: str, *texts: str) -> bool:
    positions = [html.find(t) for t in texts]
    return -1 not in positions and positions == sorted(positions)


# --- 一覧 ------------------------------------------------------------------
def test_要約した日ごとに新しい日から並び日の中は優先順位で未要約は出さない(client, articles):
    add(articles, "量子の古い話", summarized_on=datetime(2026, 11, 15, 6, 0))
    add(articles, "量子の話", summarized_on=datetime(2026, 11, 16, 6, 0), published_at=datetime(2026, 11, 16, 5, 0))
    add(articles, "量子と AI", summarized_on=datetime(2026, 11, 16, 6, 0), published_at=datetime(2026, 11, 15, 1, 0))
    add(articles, "量子の未要約の話")

    html = client.get("/news").text

    assert appear_in_order(html, "<h2>2026-11-16</h2>", "量子と AI", "量子の話", "<h2>2026-11-15</h2>", "量子の古い話")
    assert "量子の未要約の話" not in html


def test_記事は元記事へのリンクと配信元と要約と当たった分野を持つ(client, articles):
    a = add(articles, "量子と AI", summarized_on=NOW, summary="誤り訂正の新手法。")

    html = client.get("/news").text

    assert f'<a href="{a.url}" class="article-link" data-id="{a.id}" target="_blank" rel="noopener noreferrer">量子と AI</a>' in html
    assert "Zenn: quantum" in html and "誤り訂正の新手法。" in html
    assert appear_in_order(html, '<span class="badge badge-MATH_PHYSICS">物理・数学</span>', '<span class="badge badge-IT">IT</span>')


def test_記事がなければその旨を表示する(client):
    assert "まだ記事はありません" in client.get("/news").text


def test_どの画面からもニュースの画面へ行ける(client):
    assert 'href="/news"' in client.get("/tasks").text


# --- 既読 ------------------------------------------------------------------
def test_未読の記事には既読ボタンがあり既読の記事は薄く表示され未読に戻すボタンがある(client, articles):
    unread = add(articles, "量子の未読", summarized_on=NOW)
    read = add(articles, "量子の既読", summarized_on=NOW)
    articles.mark_read(read.id, now=NOW)

    html = client.get("/news").text

    assert f'action="/news/{unread.id}/read"' in html
    assert f'<li class="article read" data-id="{read.id}">' in html
    assert f'action="/news/{read.id}/unread"' in html


@pytest.mark.parametrize("page", ["1", "2"])
def test_既読にすると既読日時が入り操作したページに戻る(client, articles, page):
    for i in range(31):
        add(articles, f"量子 {i}", summarized_on=NOW)
    a = articles.list_summarized()[0]

    res = client.post(f"/news/{a.id}/read", data={"page": page}, follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == f"/news?page={page}"
    assert articles.list_summarized()[0].read_at == NOW


def test_未読に戻せる(client, articles):
    a = add(articles, "量子", summarized_on=NOW)
    articles.mark_read(a.id, now=NOW)

    res = client.post(f"/news/{a.id}/unread", data={"page": "1"}, follow_redirects=False)

    assert res.status_code == 303
    assert articles.list_summarized()[0].read_at is None


def test_戻り先のページ番号が数字でなければ1ページ目に戻る(client, articles):
    a = add(articles, "量子", summarized_on=NOW)

    res = client.post(f"/news/{a.id}/read", data={"page": "https://evil.example.com"}, follow_redirects=False)

    assert res.headers["location"] == "/news?page=1"


@pytest.mark.parametrize("op", ["read", "unread"])
def test_存在しない記事は既読にも未読にもできない(client, op):
    assert client.post(f"/news/999/{op}", data={"page": "1"}).status_code == 404


def test_元記事を開くと自動で既読にするスクリプトがある(client):
    html = client.get("/news").text

    assert "navigator.sendBeacon" in html and "article-link" in html


# --- ページ分け ----------------------------------------------------------------
def test_30件ごとにページを分ける(client, articles):
    for i in range(31):
        add(articles, f"量子の記事{i:02d}", summarized_on=NOW, published_at=datetime(2026, 11, 16, 0, i))

    first, second = client.get("/news").text, client.get("/news?page=2").text

    assert first.count('<li class="article') == 30 and second.count('<li class="article') == 1
    assert 'href="/news?page=2"' in first and 'href="/news?page=1"' in second
    assert "<h2>2026-11-16</h2>" in second  # ページが変わっても日の見出しを出す


def test_範囲外のページは見つからない(client):
    assert client.get("/news?page=2").status_code == 404
