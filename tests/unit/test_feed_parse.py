import logging
from datetime import datetime
from pathlib import Path

import pytest

from pda.domain.article import Feed
from pda.news.fetcher import FeedError, parse_feed

FIXTURES = Path(__file__).parent.parent / "fixtures"
FEED = Feed(name="Example Science", url="https://example.com/feed.xml")
FETCHED = datetime(2026, 11, 16, 6, 0)


def parse(name):
    return parse_feed(FEED, (FIXTURES / name).read_bytes(), fetched_at=FETCHED)


def by_url(articles):
    return {a.url: a for a in articles}


# --- RSS 2.0 ---------------------------------------------------------------
def test_RSSの項目から記事を作る():
    a = by_url(parse("rss_sample.xml"))["https://example.com/articles/qec"]

    assert (a.feed, a.title, a.fetched_at, a.summary) == (FEED, "量子誤り訂正の新手法", FETCHED, None)


def test_概要文はHTMLタグを除き文字参照を戻し空白をまとめる():
    a = by_url(parse("rss_sample.xml"))["https://example.com/articles/qec"]

    assert a.description == "表面符号のしきい値を改善。 誤り率 < 1%"


def test_公開日時はUTCから日本時間に直す():
    a = by_url(parse("rss_sample.xml"))["https://example.com/articles/qec"]

    assert a.published_at == datetime(2026, 11, 16, 6, 30)  # 21:30 GMT + 9 時間


def test_日本時間で書かれた公開日時もそのままの時刻になる():
    a = by_url(parse("rss_sample.xml"))["https://example.com/articles/jst"]

    assert a.published_at == datetime(2026, 11, 16, 8, 0)


def test_公開日時と概要文がない項目は公開日時なしで概要文は空():
    a = by_url(parse("rss_sample.xml"))["https://example.com/articles/no-date"]

    assert (a.published_at, a.description) == (None, "")


def test_危ないリンクや空のタイトルの項目はその項目だけ飛ばして警告を残す(caplog):
    with caplog.at_level(logging.WARNING):
        articles = parse("rss_sample.xml")

    assert sorted(by_url(articles)) == [
        "https://example.com/articles/jst",
        "https://example.com/articles/no-date",
        "https://example.com/articles/qec",
    ]
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 2


# --- Atom ------------------------------------------------------------------
def test_Atomの項目から記事を作り更新日時を公開日時とみなす():
    [a] = parse("atom_sample.xml")

    assert (a.url, a.title, a.description, a.published_at) == (
        "https://example.org/entries/1",
        "Topological quantum computing",
        "Majorana modes",
        datetime(2026, 11, 15, 21, 0),
    )


# --- 空・壊れたフィード -------------------------------------------------------
def test_記事のない正常なフィードは空():
    assert parse("empty_feed.xml") == []


def test_フィードとして読めない内容はエラー():
    with pytest.raises(FeedError):
        parse("broken.txt")
