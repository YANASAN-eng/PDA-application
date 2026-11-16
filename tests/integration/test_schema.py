"""本物のスキーマ(migrations/)の制約のテスト。"""

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


def add_task(db, title="レポート", priority="HIGH", due=None, done=0, created_at="2026-11-15T09:00:00"):
    db.execute(
        "INSERT INTO tasks (title, priority, due, done, created_at) VALUES (?, ?, ?, ?, ?)",
        (title, priority, due, done, created_at),
    )


def add_event(db, all_day, start_at, end_at=None, title="予定"):
    db.execute(
        "INSERT INTO events (title, all_day, start_at, end_at) VALUES (?, ?, ?, ?)",
        (title, all_day, start_at, end_at),
    )


def add_memo(db, title="メモ", body="", created_at="2026-11-15T09:00:00", updated_at="2026-11-15T09:00:00"):
    cur = db.execute(
        "INSERT INTO memos (title, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (title, body, created_at, updated_at),
    )
    return cur.lastrowid


def add_tag(db, name):
    return db.execute("INSERT INTO tags (name) VALUES (?)", (name,)).lastrowid


def test_PDAのテーブルがすべて作られる(db):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    assert {"tasks", "events", "memos", "tags", "memo_tags"} <= names


# --- tasks -----------------------------------------------------------------
def test_タスクの詳細は省略すると空文字になる(db):
    add_task(db)

    assert db.execute("SELECT detail FROM tasks").fetchone() == ("",)


def test_タスクの詳細にNULLは保存できない(db):
    with pytest.raises(Bad):
        db.execute(
            "INSERT INTO tasks (title, priority, created_at, detail) VALUES ('レポート', 'HIGH', '2026-11-15T09:00:00', NULL)"
        )


def test_版1のタスクは版2に上げても残り詳細は空文字になる(tmp_path):
    v1_dir = tmp_path / "v1"
    v1_dir.mkdir()
    shutil.copy(MIGRATIONS_DIR / "0001_initial.sql", v1_dir)
    conn = connect(":memory:")
    migrate(conn, v1_dir)
    add_task(conn, title="牛乳を買う")

    migrate(conn)

    assert current_version(conn) >= 2
    assert conn.execute("SELECT title, detail FROM tasks").fetchall() == [("牛乳を買う", "")]
    conn.close()

def test_正しいタスクは保存できる(db):
    add_task(db, due="2026-11-20")

    assert db.execute("SELECT count(*) FROM tasks").fetchone()[0] == 1


@pytest.mark.parametrize("priority", ["高", "high", "URGENT", ""])
def test_タスクの優先度はHIGH_MEDIUM_LOW以外を保存できない(db, priority):
    with pytest.raises(Bad):
        add_task(db, priority=priority)


@pytest.mark.parametrize("title", ["", "   "])
def test_空のタイトルのタスクは保存できない(db, title):
    with pytest.raises(Bad):
        add_task(db, title=title)


@pytest.mark.parametrize("due", ["2026/11/20", "2026-11-20T09:00:00", "2026-13-01", "明日"])
def test_タスクの期限はYYYY_MM_DD以外を保存できない(db, due):
    with pytest.raises(Bad):
        add_task(db, due=due)


def test_タスクの完了フラグは0か1だけ(db):
    with pytest.raises(Bad):
        add_task(db, done=2)


@pytest.mark.parametrize(
    "created_at",
    ["2026-11-15", "2026-11-15 09:00:00", "2026-11-15T09:00", "2026-13-01T09:00:00", "2026-11-15T25:00:00", "今朝"],
)
def test_日時はYYYY_MM_DDTHH_MM_SS以外を保存できない(db, created_at):
    with pytest.raises(Bad):
        add_task(db, created_at=created_at)


# --- events ----------------------------------------------------------------
def test_終日予定は日付で保存できる(db):
    add_event(db, all_day=1, start_at="2026-11-20", end_at="2026-11-22")


def test_時刻付き予定は日時で保存できる(db):
    add_event(db, all_day=0, start_at="2026-11-20T09:00:00", end_at="2026-11-20T10:00:00")


def test_終日予定に日時は保存できない(db):
    with pytest.raises(Bad):
        add_event(db, all_day=1, start_at="2026-11-20T09:00:00")


def test_時刻付き予定に日付だけは保存できない(db):
    with pytest.raises(Bad):
        add_event(db, all_day=0, start_at="2026-11-20")


@pytest.mark.parametrize(
    ("all_day", "start_at", "end_at"),
    [
        (1, "2026-13-01", None),
        (1, "2026-11-20", "来週"),
        (0, "2026-11-20T25:00:00", None),
        (0, "2026-11-20T09:00:00", "あとで"),
    ],
)
def test_不正な日付や日時の予定は保存できない(db, all_day, start_at, end_at):
    # date() / strftime() は不正な値に NULL を返す。CHECK は NULL を「違反なし」とみなすので要注意
    with pytest.raises(Bad):
        add_event(db, all_day=all_day, start_at=start_at, end_at=end_at)


def test_更新日時が不正なメモは保存できない(db):
    with pytest.raises(Bad):
        add_memo(db, updated_at="2026-11-15T99:00:00")


def test_終了が開始より前の予定は保存できない(db):
    with pytest.raises(Bad):
        add_event(db, all_day=0, start_at="2026-11-20T10:00:00", end_at="2026-11-20T09:00:00")


# --- memos -----------------------------------------------------------------
def test_更新日時が作成日時より前のメモは保存できない(db):
    with pytest.raises(Bad):
        add_memo(db, created_at="2026-11-15T09:00:00", updated_at="2026-11-15T08:00:00")


def test_メモの本文は空文字で保存できる(db):
    add_memo(db, body="")


# --- tags / memo_tags ------------------------------------------------------
def test_同じ名前のタグは2つ作れない(db):
    add_tag(db, "物理")

    with pytest.raises(Bad):
        add_tag(db, "物理")


def test_タグ名は英字の大文字と小文字を区別する(db):
    add_tag(db, "AI")
    add_tag(db, "ai")


@pytest.mark.parametrize("name", ["", "  ", " 物理", "物理 "])
def test_空のタグや前後に空白のあるタグは保存できない(db, name):
    with pytest.raises(Bad):
        add_tag(db, name)


def test_存在しないメモにタグを付けられない(db):
    tag = add_tag(db, "物理")

    with pytest.raises(Bad):
        db.execute("INSERT INTO memo_tags (memo_id, tag_id) VALUES (999, ?)", (tag,))


def test_同じメモに同じタグを二重に付けられない(db):
    memo, tag = add_memo(db), add_tag(db, "物理")
    db.execute("INSERT INTO memo_tags (memo_id, tag_id) VALUES (?, ?)", (memo, tag))

    with pytest.raises(Bad):
        db.execute("INSERT INTO memo_tags (memo_id, tag_id) VALUES (?, ?)", (memo, tag))


def test_メモを消すとそのメモのタグ付けも消えタグ自体は残る(db):
    memo, tag = add_memo(db), add_tag(db, "物理")
    db.execute("INSERT INTO memo_tags (memo_id, tag_id) VALUES (?, ?)", (memo, tag))

    db.execute("DELETE FROM memos WHERE id = ?", (memo,))

    assert db.execute("SELECT count(*) FROM memo_tags").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM tags").fetchone()[0] == 1
