from datetime import date

import pytest

from pda.domain.task import OVERDUE_PREFIX, Priority, Task, incomplete_by_priority


def test_優先度は高中低の3段階():
    assert [p.label for p in Priority] == ["高", "中", "低"]


def test_タスクはタイトルと優先度を指定して作る():
    task = Task(title="レポートを書く", priority=Priority.HIGH)

    assert task.title == "レポートを書く"
    assert task.priority is Priority.HIGH


def test_作ったばかりのタスクは未完了():
    task = Task(title="レポートを書く", priority=Priority.MEDIUM)

    assert task.done is False


def test_期限は指定しなくてもよい():
    task = Task(title="本を読む", priority=Priority.LOW)

    assert task.due is None


@pytest.mark.parametrize("title", ["", "   "])
def test_空のタイトルではタスクを作れない(title):
    with pytest.raises(ValueError):
        Task(title=title, priority=Priority.MEDIUM)


# --- 期限超過 -------------------------------------------------------------

DUE = date(2026, 11, 15)


def _task(title="レポートを書く", priority=Priority.MEDIUM, due=DUE, done=False):
    return Task(title=title, priority=priority, due=due, done=done)


def test_期限の翌日から超過になる():
    assert _task().is_overdue(today=date(2026, 11, 16)) is True


def test_期限当日は超過ではない():
    assert _task().is_overdue(today=DUE) is False


def test_期限前は超過ではない():
    assert _task().is_overdue(today=date(2026, 11, 14)) is False


def test_期限なしのタスクは超過しない():
    assert _task(due=None).is_overdue(today=date(2100, 1, 1)) is False


def test_完了済みのタスクは期限を過ぎても超過しない():
    assert _task(done=True).is_overdue(today=date(2026, 11, 16)) is False


def test_接頭辞は角括弧とハイフンの形():
    assert OVERDUE_PREFIX == "【超過】-"


def test_超過したタスクは表示タイトルに接頭辞が付く():
    assert _task().display_title(today=date(2026, 11, 16)) == "【超過】-レポートを書く"


def test_超過していないタスクは表示タイトルがそのまま():
    assert _task().display_title(today=DUE) == "レポートを書く"


# --- 一覧の並び ------------------------------------------------------------
def test_一覧には未完了のタスクだけが優先度の高い順に並ぶ():
    low = _task("低い", Priority.LOW)
    high = _task("高い", Priority.HIGH)
    finished = _task("完了済み", Priority.HIGH, done=True)
    medium = _task("中くらい", Priority.MEDIUM)

    result = incomplete_by_priority([low, high, finished, medium])

    assert [t.title for t in result] == ["高い", "中くらい", "低い"]


def test_同じ優先度のタスクは元の順序を保つ():
    first = _task("一番目", Priority.HIGH)
    second = _task("二番目", Priority.HIGH)

    result = incomplete_by_priority([first, second])

    assert [t.title for t in result] == ["一番目", "二番目"]
