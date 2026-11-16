"""日課(routines / routine_weekdays / routine_checks)のスキーマのテスト。"""

import shutil
import sqlite3

import pytest

from pda.db.migrate import MIGRATIONS_DIR, connect, current_version, migrate

Bad = sqlite3.IntegrityError


@pytest.fixture
def db():
    conn = connect(":memory:")
    migrate(conn)
    yield conn
    conn.close()


def add_routine(db, title="英単語"):
    return db.execute("INSERT INTO routines (title) VALUES (?)", (title,)).lastrowid


def count(db, table):
    return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_日課と曜日と実行の記録を保存できる(db):
    rid = add_routine(db)
    db.execute("INSERT INTO routine_weekdays (routine_id, weekday) VALUES (?, 0), (?, 6)", (rid, rid))
    db.execute("INSERT INTO routine_checks (routine_id, day) VALUES (?, '2026-11-16')", (rid,))


@pytest.mark.parametrize("title", ["", "  "])
def test_空のタイトルの日課は保存できない(db, title):
    with pytest.raises(Bad):
        add_routine(db, title)


@pytest.mark.parametrize("weekday", [-1, 7])
def test_曜日は0から6だけ(db, weekday):
    rid = add_routine(db)
    with pytest.raises(Bad):
        db.execute("INSERT INTO routine_weekdays (routine_id, weekday) VALUES (?, ?)", (rid, weekday))


def test_同じ日課に同じ曜日は2つ付けられない(db):
    rid = add_routine(db)
    db.execute("INSERT INTO routine_weekdays (routine_id, weekday) VALUES (?, 0)", (rid,))
    with pytest.raises(Bad):
        db.execute("INSERT INTO routine_weekdays (routine_id, weekday) VALUES (?, 0)", (rid,))


@pytest.mark.parametrize("day", ["2026-11-16T09:00:00", "2026-02-30", "今日"])
def test_実行の記録の日付はYYYY_MM_DD以外を保存できない(db, day):
    rid = add_routine(db)
    with pytest.raises(Bad):
        db.execute("INSERT INTO routine_checks (routine_id, day) VALUES (?, ?)", (rid, day))


def test_同じ日課の同じ日の記録は1つだけ(db):
    rid = add_routine(db)
    db.execute("INSERT INTO routine_checks (routine_id, day) VALUES (?, '2026-11-16')", (rid,))
    with pytest.raises(Bad):
        db.execute("INSERT INTO routine_checks (routine_id, day) VALUES (?, '2026-11-16')", (rid,))


def test_存在しない日課には曜日も記録も付けられない(db):
    with pytest.raises(Bad):
        db.execute("INSERT INTO routine_weekdays (routine_id, weekday) VALUES (999, 0)")
    with pytest.raises(Bad):
        db.execute("INSERT INTO routine_checks (routine_id, day) VALUES (999, '2026-11-16')")


def test_日課を消すと曜日も実行の記録も消える(db):
    rid = add_routine(db)
    db.execute("INSERT INTO routine_weekdays (routine_id, weekday) VALUES (?, 0)", (rid,))
    db.execute("INSERT INTO routine_checks (routine_id, day) VALUES (?, '2026-11-16')", (rid,))

    db.execute("DELETE FROM routines WHERE id = ?", (rid,))

    assert (count(db, "routine_weekdays"), count(db, "routine_checks")) == (0, 0)


def test_版5のデータは版6に上げても残る(tmp_path):
    v5_dir = tmp_path / "v5"
    v5_dir.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("000[1-5]_*.sql")):
        shutil.copy(path, v5_dir)
    conn = connect(":memory:")
    migrate(conn, v5_dir)
    conn.execute("INSERT INTO tasks (title, priority, created_at) VALUES ('牛乳を買う', 'LOW', '2026-11-16T09:00:00')")

    migrate(conn)

    assert current_version(conn) >= 6
    assert conn.execute("SELECT title FROM tasks").fetchall() == [("牛乳を買う",)]
    conn.close()
