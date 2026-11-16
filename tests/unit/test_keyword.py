import pytest

from pda.domain.keyword import Keyword, KeywordGroup, as_groups, is_same_word


def test_グループは物理数学とITの2つ():
    assert [g.label for g in KeywordGroup] == ["物理・数学", "IT"]


def test_語の前後の空白は取り除かれる():
    assert Keyword(group=KeywordGroup.IT, word="  機械学習 ").word == "機械学習"


@pytest.mark.parametrize("word", ["", "   "])
def test_空の語は登録できない(word):
    with pytest.raises(ValueError):
        Keyword(group=KeywordGroup.IT, word=word)


@pytest.mark.parametrize(
    "a, b, same",
    [
        ("AI", "ai", True),  # 大文字小文字だけの違いは同じ語
        ("Machine Learning", "machine learning", True),
        ("量子", "量子", True),
        ("量子", "量子コンピュータ", False),
        ("LLM", "LLMs", False),
    ],
)
def test_大文字小文字だけが違う語は同じ語とみなす(a, b, same):
    assert is_same_word(a, b) is same


def test_キーワードをグループ名ごとの語の並びにまとめる():
    keywords = [
        Keyword(group=KeywordGroup.IT, word="AI"),
        Keyword(group=KeywordGroup.MATH_PHYSICS, word="量子"),
        Keyword(group=KeywordGroup.IT, word="GPU"),
    ]

    assert as_groups(keywords) == {"物理・数学": ["量子"], "IT": ["AI", "GPU"]}


def test_語のないグループも空の並びとして含める():
    assert as_groups([]) == {"物理・数学": [], "IT": []}
