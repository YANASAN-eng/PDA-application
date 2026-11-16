from datetime import datetime

import pytest

from pda.domain.article import Article, Feed
from pda.news.filter import matched_groups, pick_for_summary, rank

FEED = Feed(name="Example", url="https://example.com/feed.xml")
FETCHED = datetime(2026, 11, 16, 6, 0)
GROUPS = {
    "物理・数学": ["量子", "quantum", "topology"],
    "IT": ["機械学習", "AI", "C++", "machine learning"],
}

_n = 0


def article(title, description="", published_at=None):
    global _n
    _n += 1
    return Article(
        feed=FEED,
        url=f"https://example.com/{_n}",
        title=title,
        description=description,
        published_at=published_at,
        fetched_at=FETCHED,
    )


def at(day, hour=0):
    return datetime(2026, 11, day, hour)


# --- 照合 ------------------------------------------------------------------
@pytest.mark.parametrize(
    "title, expected",
    [
        ("量子計算の新手法", {"物理・数学"}),  # 日本語は部分一致
        ("Quantum error correction", {"物理・数学"}),  # 英字は大文字小文字を区別しない
        ("New AI chips", {"IT"}),
        ("AI-driven search", {"IT"}),  # 記号は単語の区切り
        ("(AI) と量子", {"物理・数学", "IT"}),  # 両方
        ("How to maintain servers", set()),  # 単語の一部(maint-AI-n)には当たらない
        ("Modern C++ tips", {"IT"}),  # 記号で終わる語も照合できる
        ("Machine Learning for physics", {"IT"}),  # 空白を含む語
        ("Topological insulators", set()),  # 英字は単語単位なので topology は topological に当たらない
        ("今日の天気", set()),
    ],
)
def test_当たったキーワードのグループを返す(title, expected):
    assert matched_groups(article(title), GROUPS) == expected


def test_概要文の語でも当たる():
    assert matched_groups(article("今週の話題", description="量子コンピュータの話"), GROUPS) == {"物理・数学"}


# --- 優先順位 --------------------------------------------------------------
def test_両方の分野に当たる記事が片方だけの記事より先():
    one = article("量子の話", published_at=at(16))
    both = article("量子と機械学習", published_at=at(1))

    assert rank([one, both], GROUPS) == [both, one]


def test_当たった分野の数が同じなら公開日時の新しい順で公開日時なしは後():
    old = article("量子A", published_at=at(1))
    unknown = article("量子B", published_at=None)
    new = article("量子C", published_at=at(2))

    assert rank([old, unknown, new], GROUPS) == [new, old, unknown]


def test_分野の数も公開日時も同じなら元の順序を保つ():
    first, second = article("量子A", published_at=at(1)), article("量子B", published_at=at(1))

    assert rank([first, second], GROUPS) == [first, second]


def test_どの分野にも当たらない記事は順位付けで落とす():
    hit, miss = article("量子の話"), article("今日の天気")

    assert rank([miss, hit], GROUPS) == [hit]


# --- 要約する記事の選び方 ------------------------------------------------------
def test_要約するのは未要約の対象記事を優先順位の高い順に上限件数まで():
    both = article("量子と機械学習", published_at=at(1))
    one_new = article("量子の話", published_at=at(3))
    one_old = article("AI の話", published_at=at(2))
    done = article("量子と AI", published_at=at(4))
    done.set_summary("要約済み", now=FETCHED)
    miss = article("今日の天気", published_at=at(5))

    assert pick_for_summary([miss, one_old, done, one_new, both], GROUPS, limit=2) == [both, one_new]


def test_上限が0なら何も選ばない():
    assert pick_for_summary([article("量子の話")], GROUPS, limit=0) == []


def test_上限が負ならエラー():
    with pytest.raises(ValueError):
        pick_for_summary([article("量子の話")], GROUPS, limit=-1)
