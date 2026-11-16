from datetime import datetime

import pytest

from pda.domain.article import Article, Feed
from pda.news.summarizer import MockSummarizer, apply_summaries

FEED = Feed(name="Example", url="https://example.com/feed.xml")
FETCHED = datetime(2026, 11, 16, 6, 0)
NOW = datetime(2026, 11, 16, 6, 5)


def article(n=1, description=""):
    return Article(feed=FEED, url=f"https://example.com/{n}", title=f"記事{n}", description=description, fetched_at=FETCHED)


# --- モック要約 --------------------------------------------------------------
def test_モック要約は概要文が上限以下ならそのまま():
    a = article(description="あいうえお")

    assert MockSummarizer(max_chars=5).summarize([a]) == {a.url: "あいうえお"}


def test_モック要約は概要文が上限を超えたら先頭を切って末尾に省略記号を付ける():
    a = article(description="あいうえおか")

    assert MockSummarizer(max_chars=5).summarize([a]) == {a.url: "あいうえお…"}


def test_モック要約は概要文が空なら空():
    a = article(description="")

    assert MockSummarizer(max_chars=5).summarize([a]) == {a.url: ""}


def test_モック要約は複数の記事をまとめて要約する():
    a, b = article(1, "あ"), article(2, "い")

    assert MockSummarizer(max_chars=5).summarize([a, b]) == {a.url: "あ", b.url: "い"}


@pytest.mark.parametrize("max_chars", [0, -1])
def test_モック要約の上限文字数は1以上(max_chars):
    with pytest.raises(ValueError):
        MockSummarizer(max_chars=max_chars)


# --- 要約の反映 ----------------------------------------------------------------
class PartialSummarizer:
    """1 件目だけ要約を返す Fake(本物の API が一部を拒否した場合の代わり)。"""

    def summarize(self, articles):
        return {articles[0].url: "要約"} if articles else {}


def test_要約を記事に反映して要約できた記事を返す():
    a = article(1, "あ")

    done = apply_summaries([a], MockSummarizer(max_chars=5), now=NOW)

    assert done == [a]
    assert (a.summary, a.summarized_at) == ("あ", NOW)


def test_要約が返らなかった記事は未要約のまま残す():
    a, b = article(1), article(2)

    done = apply_summaries([a, b], PartialSummarizer(), now=NOW)

    assert done == [a]
    assert b.is_summarized is False


def test_記事がなければ要約器を呼ばない():
    class Exploding:
        def summarize(self, articles):
            raise AssertionError("呼ばれてはいけない")

    assert apply_summaries([], Exploding(), now=NOW) == []
