from datetime import datetime

import pytest

from pda.domain.memo import Memo, memos_by_updated, parse_tag_input, search_memos, tag_counts, with_tag

T0 = datetime(2026, 11, 15, 9, 0)
T1 = datetime(2026, 11, 15, 10, 0)
T2 = datetime(2026, 11, 15, 11, 0)


def memo(title="量子計算のメモ", body="", tags=(), created_at=T0):
    return Memo(title=title, body=body, tags=tags, created_at=created_at)


# --- 作成 ------------------------------------------------------------------
@pytest.mark.parametrize("title", ["", "   "])
def test_空のタイトルではメモを作れない(title):
    with pytest.raises(ValueError):
        memo(title=title)


def test_本文は空でもよい():
    assert memo(body="").body == ""


def test_作成直後は更新日時が作成日時と同じ():
    m = memo()

    assert m.created_at == T0
    assert m.updated_at == T0


# --- タグ ------------------------------------------------------------------
def test_複数のタグを付けられる():
    assert memo(tags=["物理", "アイデア"]).tags == {"物理", "アイデア"}


def test_タグの前後の空白は取り除かれる():
    assert memo(tags=["  物理 "]).tags == {"物理"}


@pytest.mark.parametrize("tag", ["", "  "])
def test_空のタグは付けられない(tag):
    with pytest.raises(ValueError):
        memo(tags=[tag])


def test_同じタグは1つにまとまる():
    assert memo(tags=["物理", "物理", " 物理"]).tags == {"物理"}


def test_タグは英字の大文字と小文字を区別する():
    assert memo(tags=["AI", "ai"]).tags == {"AI", "ai"}


def test_指定したタグを持つメモだけを絞り込める():
    physics = memo(title="A", tags=["物理"])
    math = memo(title="B", tags=["数学"])
    both = memo(title="C", tags=["物理", "数学"])

    assert [m.title for m in with_tag([physics, math, both], "物理")] == ["A", "C"]


# --- 編集 ------------------------------------------------------------------
def test_編集すると内容と更新日時が変わり作成日時は変わらない():
    m = memo()

    m.edit(title="新しいタイトル", body="新しい本文", tags=["数学"], now=T1)

    assert (m.title, m.body, m.tags) == ("新しいタイトル", "新しい本文", {"数学"})
    assert m.updated_at == T1
    assert m.created_at == T0


def test_空のタイトルへの編集は失敗しメモは変わらない():
    m = memo(body="元の本文")

    with pytest.raises(ValueError):
        m.edit(title="", body="書き換え", tags=[], now=T1)

    assert (m.title, m.body, m.updated_at) == ("量子計算のメモ", "元の本文", T0)


def test_空のタグへの編集は失敗しメモは変わらない():
    m = memo(tags=["物理"])

    with pytest.raises(ValueError):
        m.edit(title="新しいタイトル", body="", tags=[" "], now=T1)

    assert (m.title, m.tags, m.updated_at) == ("量子計算のメモ", {"物理"}, T0)


def test_作成日時より前の時刻では編集できない():
    m = memo(created_at=T1)

    with pytest.raises(ValueError):
        m.edit(title="新しいタイトル", body="", tags=[], now=T0)


# --- 検索 ------------------------------------------------------------------
def test_キーワードがタイトルに含まれれば見つかる():
    assert memo(title="量子計算のメモ").matches("量子") is True


def test_キーワードが本文に含まれれば見つかる():
    assert memo(body="ユニタリ行列で状態が変わる").matches("ユニタリ") is True


def test_検索は英字の大文字と小文字を区別しない():
    assert memo(body="Fourier transform").matches("fourier") is True


def test_キーワードが含まれなければ見つからない():
    assert memo(title="量子計算", body="").matches("相対論") is False


def test_検索結果はキーワードを含むメモだけ():
    a = memo(title="量子もつれ")
    b = memo(title="熱力学")

    assert [m.title for m in search_memos([a, b], "量子")] == ["量子もつれ"]


@pytest.mark.parametrize("keyword", ["", "  "])
def test_空のキーワードで検索すると全件が返る(keyword):
    a, b = memo(title="A"), memo(title="B")

    assert search_memos([a, b], keyword) == [a, b]


# --- 一覧 ------------------------------------------------------------------
def test_一覧は更新日時の新しい順():
    old = memo(title="古い")
    new = memo(title="新しい")
    middle = memo(title="中間")
    new.edit(title="新しい", body="", tags=[], now=T2)
    middle.edit(title="中間", body="", tags=[], now=T1)

    assert [m.title for m in memos_by_updated([old, new, middle])] == ["新しい", "中間", "古い"]


def test_更新日時が同じメモは元の順序を保つ():
    first, second = memo(title="一番目"), memo(title="二番目")

    assert [m.title for m in memos_by_updated([first, second])] == ["一番目", "二番目"]


# --- id --------------------------------------------------------------------
def test_保存前のメモはidを持たない():
    assert memo().id is None


def test_idを指定してメモを作れる():
    assert Memo(id=7, title="量子計算のメモ", created_at=T0).id == 7


# --- タグの入力 ------------------------------------------------------------
@pytest.mark.parametrize(
    "text, tags",
    [
        ("数学 物理", ["数学", "物理"]),
        ("数学,物理", ["数学", "物理"]),
        ("数学、物理", ["数学", "物理"]),
        ("数学\u3000物理", ["数学", "物理"]),  # 全角の空白
        ("#数学 #物理", ["数学", "物理"]),  # 先頭の # は取り除く
        ("  数学 ,, 、 物理  ", ["数学", "物理"]),  # 区切りが続いても空のタグはできない
        ("C# #C#", ["C#", "C#"]),  # 途中や末尾の # は残す(重複はメモが 1 つにまとめる)
        ("", []),
        ("# ,", []),
    ],
)
def test_タグの入力は空白かカンマか読点で区切り先頭のシャープを取り除く(text, tags):
    assert parse_tag_input(text) == tags


# --- タグの絞り込みボタン ------------------------------------------------------
def test_タグと付いているメモの数を多い順に同数なら名前順に返す():
    memos = [memo(tags=["物理", "数学"]), memo(tags=["数学"]), memo(tags=["IT", "物理"]), memo(tags=["数学"])]

    assert tag_counts(memos) == [("数学", 3), ("物理", 2), ("IT", 1)]


def test_メモがなければタグもない():
    assert tag_counts([]) == []
