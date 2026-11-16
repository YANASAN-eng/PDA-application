from datetime import date, datetime

import pytest

from pda.db.migrate import connect, migrate
from pda.db.task_repository import TaskRepository
from pda.domain.task import Priority, Task, incomplete_by_priority

T0 = datetime(2026, 11, 15, 9, 0, 0)
T1 = datetime(2026, 11, 15, 10, 0, 0)
T2 = datetime(2026, 11, 15, 11, 0, 0)


@pytest.fixture
def repo():
    conn = connect(":memory:")
    migrate(conn)
    yield TaskRepository(conn)
    conn.close()


def task(title="レポートを書く", priority=Priority.HIGH, due=None, done=False, created_at=T0):
    return Task(title=title, priority=priority, due=due, done=done, created_at=created_at)


# --- 保存と取り出し ---------------------------------------------------------
def test_保存するとidが振られる(repo):
    t = task()

    repo.add(t)

    assert isinstance(t.id, int)


def test_保存したタスクを取り出すと同じ内容(repo):
    t = task(due=date(2026, 11, 20), priority=Priority.LOW)
    repo.add(t)

    assert repo.get(t.id) == t


def test_期限なしで完了済みのタスクも同じ内容で取り出せる(repo):
    t = task(due=None, done=True)
    repo.add(t)

    assert repo.get(t.id) == t


def test_存在しないidではNoneが返る(repo):
    assert repo.get(999) is None


def test_保存済みのタスクを二重に保存できない(repo):
    t = task()
    repo.add(t)

    with pytest.raises(ValueError):
        repo.add(t)


def test_マイクロ秒を含む作成日時は保存できない(repo):
    # DB は秒単位。黙って切り捨てると、保存したものと取り出したものが一致しなくなる
    with pytest.raises(ValueError):
        repo.add(task(created_at=datetime(2026, 11, 15, 9, 0, 0, 123456)))


# --- 一覧 ------------------------------------------------------------------
def test_一覧は作成日時の古い順(repo):
    for title, at in [("2番目", T1), ("3番目", T2), ("1番目", T0)]:
        repo.add(task(title=title, created_at=at))

    assert [t.title for t in repo.list_all()] == ["1番目", "2番目", "3番目"]


def test_作成日時が同じタスクは保存した順(repo):
    repo.add(task(title="先", created_at=T0))
    repo.add(task(title="後", created_at=T0))

    assert [t.title for t in repo.list_all()] == ["先", "後"]


def test_取り出した一覧をドメインの並び替えにそのまま渡せる(repo):
    repo.add(task(title="低", priority=Priority.LOW, created_at=T0))
    repo.add(task(title="高・後", priority=Priority.HIGH, created_at=T2))
    repo.add(task(title="完了", priority=Priority.HIGH, done=True, created_at=T0))
    repo.add(task(title="高・先", priority=Priority.HIGH, created_at=T1))

    assert [t.title for t in incomplete_by_priority(repo.list_all())] == ["高・先", "高・後", "低"]


# --- 更新と削除 -------------------------------------------------------------
def test_更新すると内容が変わる(repo):
    t = task()
    repo.add(t)

    t.title, t.priority, t.due, t.done = "書き直した", Priority.MEDIUM, date(2026, 12, 1), True
    repo.update(t)

    assert repo.get(t.id) == t


def test_保存前のタスクは更新できない(repo):
    with pytest.raises(ValueError):
        repo.update(task())


def test_存在しないタスクは更新できない(repo):
    t = task()
    t.id = 999

    with pytest.raises(LookupError):
        repo.update(t)


def test_削除すると取り出せなくなる(repo):
    t = task()
    repo.add(t)

    repo.delete(t.id)

    assert repo.get(t.id) is None
    assert repo.list_all() == []


def test_存在しないタスクは削除できない(repo):
    with pytest.raises(LookupError):
        repo.delete(999)


# --- 詳細 ------------------------------------------------------------------
def test_詳細も保存して取り出せる(repo):
    t = Task(title="牛乳を買う", priority=Priority.LOW, created_at=T0, detail="シチュー用。\n1L を 2 本")
    repo.add(t)

    assert repo.get(t.id).detail == "シチュー用。\n1L を 2 本"


def test_詳細を更新できる(repo):
    t = Task(title="牛乳を買う", priority=Priority.LOW, created_at=T0)
    repo.add(t)

    t.detail = "飲む用"
    repo.update(t)

    assert repo.get(t.id).detail == "飲む用"
