import sqlite3
from datetime import date

import pytest

from pda.db.migrate import connect, migrate
from pda.db.routine_repository import RoutineRepository
from pda.domain.routine import EVERY_DAY, Routine

MON, WED, FRI = 0, 2, 4
DAY = date(2026, 11, 16)
NEXT = date(2026, 11, 17)


@pytest.fixture
def conn():
    c = connect(":memory:")
    migrate(c)
    yield c
    c.close()


@pytest.fixture
def repo(conn):
    return RoutineRepository(conn)


def count(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


# --- 保存と取り出し ---------------------------------------------------------
def test_保存した日課を曜日ごと取り出せてidが振られる(repo):
    words, gym = Routine(title="英単語"), Routine(title="筋トレ", weekdays=[MON, WED, FRI])
    repo.add(words)
    repo.add(gym)

    assert repo.list_all() == [words, gym]
    assert repo.get(gym.id).weekdays == {MON, WED, FRI}
    assert repo.get(words.id).weekdays == EVERY_DAY


def test_存在しないidではNoneが返る(repo):
    assert repo.get(999) is None


def test_保存済みの日課を二重に保存できない(repo):
    r = Routine(title="英単語")
    repo.add(r)

    with pytest.raises(ValueError):
        repo.add(r)


def test_保存の途中で失敗したら日課も曜日も残らずidも振られない(repo, conn):
    conn.execute("CREATE TRIGGER fail BEFORE INSERT ON routine_weekdays BEGIN SELECT RAISE(ABORT, 'テスト用の失敗'); END")
    r = Routine(title="英単語")

    with pytest.raises(sqlite3.IntegrityError):
        repo.add(r)

    assert (count(conn, "routines"), r.id) == (0, None)


# --- 更新・削除 ----------------------------------------------------------------
def test_更新するとタイトルと曜日が置き換わる(repo):
    r = Routine(title="筋トレ", weekdays=[MON, WED, FRI])
    repo.add(r)

    repo.update(Routine(id=r.id, title="ジョギング", weekdays=[WED]))

    assert repo.get(r.id) == Routine(id=r.id, title="ジョギング", weekdays=[WED])


def test_更新の途中で失敗したら元のまま(repo, conn):
    r = Routine(title="筋トレ", weekdays=[MON])
    repo.add(r)
    conn.execute("CREATE TRIGGER fail BEFORE INSERT ON routine_weekdays BEGIN SELECT RAISE(ABORT, 'テスト用の失敗'); END")

    with pytest.raises(sqlite3.IntegrityError):
        repo.update(Routine(id=r.id, title="ジョギング", weekdays=[WED]))

    assert repo.get(r.id) == r


@pytest.mark.parametrize("op", ["update", "delete"])
def test_存在しない日課は更新も削除もできない(repo, op):
    with pytest.raises(LookupError):
        repo.update(Routine(id=999, title="x")) if op == "update" else repo.delete(999)


def test_保存前の日課は更新できない(repo):
    with pytest.raises(ValueError):
        repo.update(Routine(title="英単語"))


def test_削除すると曜日も実行の記録も消える(repo, conn):
    r = Routine(title="英単語")
    repo.add(r)
    repo.check(r.id, DAY)

    repo.delete(r.id)

    assert (repo.get(r.id), count(conn, "routine_weekdays"), count(conn, "routine_checks")) == (None, 0, 0)


# --- 実行の記録 ----------------------------------------------------------------
def test_チェックした日課はその日だけやった扱いになる(repo):
    a, b = Routine(title="英単語"), Routine(title="筋トレ")
    repo.add(a)
    repo.add(b)

    repo.check(a.id, DAY)

    assert (repo.checked_on(DAY), repo.checked_on(NEXT)) == ({a.id}, set())


def test_チェックを外せる(repo):
    r = Routine(title="英単語")
    repo.add(r)
    repo.check(r.id, DAY)

    repo.uncheck(r.id, DAY)

    assert repo.checked_on(DAY) == set()


def test_同じチェックや外しを2回しても結果は変わらずエラーにもならない(repo):
    r = Routine(title="英単語")
    repo.add(r)

    repo.check(r.id, DAY)
    repo.check(r.id, DAY)
    assert repo.checked_on(DAY) == {r.id}

    repo.uncheck(r.id, DAY)
    repo.uncheck(r.id, DAY)
    assert repo.checked_on(DAY) == set()


@pytest.mark.parametrize("op", ["check", "uncheck"])
def test_存在しない日課はチェックも外しもできない(repo, op):
    with pytest.raises(LookupError):
        getattr(repo, op)(999, DAY)
