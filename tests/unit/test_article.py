from datetime import datetime

import pytest

from pda.domain.article import Article, Feed

FEED = Feed(name="Example", url="https://example.com/feed.xml")
FETCHED = datetime(2026, 11, 16, 6, 0)


def article(url="https://example.com/a", title="量子計算の新手法", description="", published_at=None):
    return Article(feed=FEED, url=url, title=title, description=description, published_at=published_at, fetched_at=FETCHED)


# --- 作成 ------------------------------------------------------------------
def test_概要文は省略すると空():
    a = Article(feed=FEED, url="https://example.com/a", title="量子計算", fetched_at=FETCHED)

    assert a.description == ""


@pytest.mark.parametrize("title", ["", "   "])
def test_空のタイトルでは記事を作れない(title):
    with pytest.raises(ValueError):
        article(title=title)


@pytest.mark.parametrize("url", ["https://example.com/a", "http://example.com/a", "HTTPS://EXAMPLE.COM/a"])
def test_httpとhttpsのURLは受け付ける(url):
    assert article(url=url).url == url


@pytest.mark.parametrize(
    "url",
    ["javascript:alert(1)", "ftp://example.com/a", "", "/relative/path", "example.com/a", "https://"],
    ids=["javascript", "ftp", "空", "相対パス", "スキームなし", "ホストなし"],
)
def test_httpとhttps以外のURLの記事は作れない(url):
    with pytest.raises(ValueError):
        article(url=url)


def test_httpとhttps以外のURLのフィードは作れない():
    with pytest.raises(ValueError):
        Feed(name="Bad", url="javascript:alert(1)")


@pytest.mark.parametrize("name", ["", "  "])
def test_名前が空のフィードは作れない(name):
    with pytest.raises(ValueError):
        Feed(name=name, url="https://example.com/feed.xml")


# --- 要約 ------------------------------------------------------------------
def test_作った時点では未要約():
    a = article()

    assert (a.summary, a.summarized_at, a.is_summarized) == (None, None, False)


def test_要約を付けると要約文と要約日時が入る():
    a = article()
    now = datetime(2026, 11, 16, 6, 5)

    a.set_summary("新しい誤り訂正の手法。", now=now)

    assert (a.summary, a.summarized_at, a.is_summarized) == ("新しい誤り訂正の手法。", now, True)


def test_要約文と要約日時は片方だけでは持てない():
    with pytest.raises(ValueError):
        Article(feed=FEED, url="https://example.com/a", title="量子計算", fetched_at=FETCHED, summary="要約")


# --- 既読 ------------------------------------------------------------------
def test_作った時点では未読():
    a = article()

    assert (a.read_at, a.is_read) == (None, False)


def test_既読にすると既読日時が入り未読に戻すと消える():
    a = article()
    now = datetime(2026, 11, 16, 21, 0)

    a.mark_read(now=now)
    assert (a.read_at, a.is_read) == (now, True)

    a.mark_unread()
    assert (a.read_at, a.is_read) == (None, False)
