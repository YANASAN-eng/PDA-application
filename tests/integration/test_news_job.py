from datetime import datetime
from pathlib import Path

import pytest

from pda import config
from pda.db.article_repository import ArticleRepository
from pda.db.keyword_repository import KeywordRepository
from pda.db.migrate import connect, migrate_file
from pda.domain.article import Feed
from pda.domain.keyword import Keyword, KeywordGroup
from pda.news.summarizer import MockSummarizer
from pda.news_job import make_summarizer, run_job

FIXTURES = Path(__file__).parent.parent / "fixtures"
RSS = Feed(name="Example Science", url="https://example.com/feed.xml")
NOW = datetime(2026, 11, 16, 6, 0)


class FakeFetcher:
    def fetch(self, url):
        return (FIXTURES / "rss_sample.xml").read_bytes()


def test_DBを最新にしてから取得と要約を行う(tmp_path):
    db_path = tmp_path / "pda.db"

    report = run_job(db_path, now=NOW, feeds=[RSS], fetcher=FakeFetcher())

    conn = connect(db_path)
    try:
        urls = [a.url for a in ArticleRepository(conn).list_all() if a.is_summarized]
    finally:
        conn.close()
    assert "https://example.com/articles/qec" in urls  # 「量子」は初期データのキーワードに入っている
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


def test_既定の設定はモック要約で上限は30件():
    assert (config.SUMMARIZER, config.DAILY_SUMMARY_LIMIT) == ("mock", 30)


def test_設定のフィードはURLも名前も重複しない():
    urls = [f.url for f in config.FEEDS]
    names = [f.name for f in config.FEEDS]

    assert len(urls) == len(set(urls)) and len(names) == len(set(names))


def test_絞り込みには設定ではなくDBのキーワードを使う(tmp_path):
    db_path = tmp_path / "pda.db"
    migrate_file(db_path, now=NOW)
    conn = connect(db_path)
    conn.execute("DELETE FROM keywords")
    KeywordRepository(conn).add(Keyword(group=KeywordGroup.MATH_PHYSICS, word="日本時間"))
    conn.close()

    run_job(db_path, now=NOW, feeds=[RSS], fetcher=FakeFetcher())

    conn = connect(db_path)
    try:
        urls = [a.url for a in ArticleRepository(conn).list_all()]
    finally:
        conn.close()
    # 設定にあった「量子」なら量子誤り訂正の記事が残る。DB の「日本時間」なら次の記事だけが残る
    assert urls == ["https://example.com/articles/jst"]


def test_キーワードは設定ファイルには置かない():
    assert not hasattr(config, "KEYWORD_GROUPS")
