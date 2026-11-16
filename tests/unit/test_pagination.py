import pytest

from pda.web.pagination import paginate

ITEMS = list(range(1, 8))  # 7 件


@pytest.mark.parametrize(
    "page, items, has_prev, has_next",
    [(1, [1, 2, 3], False, True), (2, [4, 5, 6], True, True), (3, [7], True, False)],
)
def test_指定したページの分だけを返し前後のページの有無が分かる(page, items, has_prev, has_next):
    p = paginate(ITEMS, page=page, per_page=3)

    assert (p.items, p.page, p.total_pages, p.has_prev, p.has_next) == (items, page, 3, has_prev, has_next)


def test_件数がページの大きさで割り切れるときに空のページを作らない():
    assert paginate(list(range(6)), page=1, per_page=3).total_pages == 2


def test_0件でも1ページ目は空のページとして返す():
    p = paginate([], page=1, per_page=3)

    assert (p.items, p.total_pages, p.has_prev, p.has_next) == ([], 1, False, False)


@pytest.mark.parametrize("page", [0, -1, 4])
def test_範囲外のページはエラー(page):
    with pytest.raises(ValueError):
        paginate(ITEMS, page=page, per_page=3)


def test_ページの大きさは1以上():
    with pytest.raises(ValueError):
        paginate(ITEMS, page=1, per_page=0)
