from datetime import datetime
from pathlib import Path

import pytest

from pda import config
from pda.db.article_repository import ArticleRepository
from pda.db.migrate import connect
from pda.domain.article import Feed
from pda.news.summarizer import MockSummarizer
from pda.news_job import make_summarizer, run_job

FIXTURES = Path(__file__).parent.parent / "fixtures"
RSS = Feed(name="Example Science", url="https://example.com/feed.xml")
NOW = datetime(2026, 11, 16, 6, 0)


class FakeFetcher:
    def fetch(self, url):
        return (FIXTURES / "rss_sample.xml").read_bytes()


def test_DBを最新にしてから設定のキーワードで取得と要約を行う(tmp_path):
    db_path = tmp_path / "pda.db"

    report = run_job(db_path, now=NOW, feeds=[RSS], fetcher=FakeFetcher())

    conn = connect(db_path)
    try:
        urls = [a.url for a in ArticleRepository(conn).list_all() if a.is_summarized]
    finally:
        conn.close()
    assert "https://example.com/articles/qec" in urls  # 「量子」は設定のキーワードに入っている
    assert report.failed_feeds == []


def test_フィードが空なら何もせずに終わる(tmp_path):
    report = run_job(tmp_path / "pda.db", now=NOW, feeds=[], fetcher=FakeFetcher())

    assert (report.added, report.summarized, report.failed_feeds) == (0, 0, [])


def test_要約器はモックを作る():
    assert isinstance(make_summarizer("mock"), MockSummarizer)


@pytest.mark.parametrize("name", ["claude", ""])
def test_モック以外の要約器はまだ選べない(name):
    with pytest.raises(ValueError):
        make_summarizer(name)


def test_既定の設定はモック要約でフィードは空で上限は30件():
    assert (config.SUMMARIZER, config.FEEDS, config.DAILY_SUMMARY_LIMIT) == ("mock", [], 30)
