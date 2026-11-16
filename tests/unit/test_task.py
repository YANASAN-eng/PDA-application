from datetime import date, datetime

import pytest

from pda.domain.task import OVERDUE_PREFIX, Priority, Task, completed_by_newest, incomplete_by_priority

T0 = datetime(2026, 11, 15, 9, 0)
T1 = datetime(2026, 11, 15, 10, 0)
T2 = datetime(2026, 11, 15, 11, 0)
DUE = date(2026, 11, 15)


def _task(title="レポートを書く", priority=Priority.MEDIUM, due=DUE, done=False, created_at=T0):
    return Task(title=title, priority=priority, due=due, done=done, created_at=created_at)


# --- 作成 ------------------------------------------------------------------
def test_優先度は高中低の3段階():
    assert [p.label for p in Priority] == ["高", "中", "低"]


def test_タスクはタイトルと優先度と作成日時を指定して作る():
    task = Task(title="レポートを書く", priority=Priority.HIGH, created_at=T0)

    assert task.title == "レポートを書く"
    assert task.priority is Priority.HIGH
    assert task.created_at == T0


def test_作成日時は省略できない():
    with pytest.raises(TypeError):
        Task(title="レポートを書く", priority=Priority.HIGH)


def test_作ったばかりのタスクは未完了():
    assert Task(title="レポートを書く", priority=Priority.MEDIUM, created_at=T0).done is False


def test_期限は指定しなくてもよい():
    assert Task(title="本を読む", priority=Priority.LOW, created_at=T0).due is None


def test_保存前のタスクはidを持たない():
    assert Task(title="本を読む", priority=Priority.LOW, created_at=T0).id is None


@pytest.mark.parametrize("title", ["", "   "])
def test_空のタイトルではタスクを作れない(title):
    with pytest.raises(ValueError):
        Task(title=title, priority=Priority.MEDIUM, created_at=T0)


# --- 期限超過 -------------------------------------------------------------
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


def test_接頭辞は隅付き括弧とハイフンの形():
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


def test_同じ優先度のタスクは作成日時の古い順():
    newer = _task("後に作った", Priority.HIGH, created_at=T2)
    older = _task("先に作った", Priority.HIGH, created_at=T1)

    result = incomplete_by_priority([newer, older])

    assert [t.title for t in result] == ["先に作った", "後に作った"]


def test_優先度と作成日時が同じタスクは元の順序を保つ():
    first = _task("一番目", Priority.HIGH, created_at=T0)
    second = _task("二番目", Priority.HIGH, created_at=T0)

    result = incomplete_by_priority([first, second])

    assert [t.title for t in result] == ["一番目", "二番目"]


# --- 完了済みの一覧 ----------------------------------------------------------
def test_完了済みの一覧は完了したタスクだけを作成日時の新しい順に返す():
    old = Task(title="古い", priority=Priority.HIGH, created_at=T0, done=True)
    open_ = Task(title="未完了", priority=Priority.HIGH, created_at=T1)
    new = Task(title="新しい", priority=Priority.LOW, created_at=T2, done=True)

    assert [t.title for t in completed_by_newest([old, open_, new])] == ["新しい", "古い"]


def test_完了済みで作成日時が同じタスクは元の順序を保つ():
    first = Task(title="一番目", priority=Priority.LOW, created_at=T0, done=True)
    second = Task(title="二番目", priority=Priority.HIGH, created_at=T0, done=True)

    assert [t.title for t in completed_by_newest([first, second])] == ["一番目", "二番目"]


# --- 詳細 ------------------------------------------------------------------
def test_詳細は省略すると空():
    assert Task(title="牛乳を買う", priority=Priority.LOW, created_at=T0).detail == ""


def test_詳細を付けて作れる():
    t = Task(title="牛乳を買う", priority=Priority.LOW, created_at=T0, detail="シチュー用。\n1L を 2 本")

    assert t.detail == "シチュー用。\n1L を 2 本"
