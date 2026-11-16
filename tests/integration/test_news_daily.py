import logging
from datetime import datetime
from pathlib import Path

import pytest

from pda.db.article_repository import ArticleRepository
from pda.db.migrate import connect, migrate
from pda.domain.article import Feed
from pda.news.daily import run_daily
from pda.news.summarizer import MockSummarizer

FIXTURES = Path(__file__).parent.parent / "fixtures"
RSS = Feed(name="Example Science", url="https://example.com/feed.xml")
ATOM = Feed(name="Example Atom", url="https://example.org/atom.xml")
BROKEN = Feed(name="Broken", url="https://broken.example.net/rss")
DOWN = Feed(name="Down", url="https://down.example.net/rss")
GROUPS = {"物理・数学": ["量子", "quantum"], "IT": ["AI"]}
DAY1 = datetime(2026, 11, 16, 6, 0)
DAY2 = datetime(2026, 11, 17, 6, 0)


class FakeFetcher:
    """URL → フィクスチャのファイル名。DOWN は接続失敗の代わりに例外を投げる。"""

    files = {RSS.url: "rss_sample.xml", ATOM.url: "atom_sample.xml", BROKEN.url: "broken.txt"}

    def fetch(self, url):
        if url not in self.files:
            raise OSError(f"接続できません: {url}")
        return (FIXTURES / self.files[url]).read_bytes()


class CountingSummarizer(MockSummarizer):
    def __init__(self):
        super().__init__(max_chars=200)
        self.calls = []

    def summarize(self, articles):
        self.calls.append([a.url for a in articles])
        return super().summarize(articles)


@pytest.fixture
def repo():
    conn = connect(":memory:")
    migrate(conn)
    yield ArticleRepository(conn)
    conn.close()


def run(repo, feeds, *, now=DAY1, limit=30, summarizer=None):
    return run_daily(
        feeds=feeds,
        fetcher=FakeFetcher(),
        repo=repo,
        summarizer=summarizer or MockSummarizer(max_chars=200),
        groups=GROUPS,
        limit=limit,
        now=now,
    )


# --- 基本の流れ --------------------------------------------------------------
def test_対象の記事だけを保存して要約する(repo):
    report = run(repo, [RSS, ATOM])

    saved = {a.url: a for a in repo.list_all()}
    assert sorted(saved) == ["https://example.com/articles/qec", "https://example.org/entries/1"]
    assert saved["https://example.com/articles/qec"].summary == "表面符号のしきい値を改善。 誤り率 < 1%"
    assert all(a.summarized_at == DAY1 for a in saved.values())
    assert (report.added, report.summarized, report.failed_feeds) == (2, 2, [])


def test_2回目の実行では同じ記事を二重に保存も要約もしない(repo):
    summarizer = CountingSummarizer()
    run(repo, [RSS], summarizer=summarizer)

    report = run(repo, [RSS], now=DAY2, summarizer=summarizer)

    assert (report.added, report.summarized, len(repo.list_all())) == (0, 0, 1)
    assert len(summarizer.calls) == 1  # 2 回目は要約器を呼ばない(本物なら費用がかかる)


# --- 失敗の扱い --------------------------------------------------------------
def test_取得や解析に失敗したフィードは記録して他のフィードは続ける(repo, caplog):
    with caplog.at_level(logging.ERROR):
        report = run(repo, [DOWN, BROKEN, RSS])

    assert report.failed_feeds == ["Down", "Broken"]
    assert [a.url for a in repo.list_all()] == ["https://example.com/articles/qec"]
    assert sum("Down" in r.getMessage() for r in caplog.records) == 1
    assert sum("Broken" in r.getMessage() for r in caplog.records) == 1


# --- 1 日の上限 -------------------------------------------------------------
def test_要約は1日の上限までで優先順位の高い記事から(repo):
    report = run(repo, [RSS, ATOM], limit=1)

    summarized = [a.url for a in repo.list_all() if a.is_summarized]
    assert summarized == ["https://example.com/articles/qec"]  # 公開日時が新しい方(どちらも 1 分野)
    assert (report.added, report.summarized) == (2, 1)


def test_同じ日に2回実行しても上限は1日の合計で数える(repo):
    run(repo, [RSS], limit=1)

    report = run(repo, [ATOM], now=DAY1.replace(hour=18), limit=1)

    assert report.summarized == 0
    assert len([a for a in repo.list_all() if a.is_summarized]) == 1


def test_上限で要約されなかった記事は翌日に要約される(repo):
    run(repo, [RSS, ATOM], limit=1)

    report = run(repo, [], now=DAY2, limit=1)

    assert report.summarized == 1
    assert all(a.is_summarized for a in repo.list_all())
