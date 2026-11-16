import sqlite3
from datetime import datetime

import pytest

from pda.db.memo_repository import MemoRepository
from pda.db.migrate import connect, migrate
from pda.domain.memo import Memo

T0 = datetime(2026, 11, 16, 9, 0)
T1 = datetime(2026, 11, 16, 10, 0)


@pytest.fixture
def conn():
    c = connect(":memory:")
    migrate(c)
    yield c
    c.close()


@pytest.fixture
def repo(conn):
    return MemoRepository(conn)


def memo(title="量子計算のメモ", body="", tags=(), created_at=T0):
    return Memo(title=title, body=body, tags=tags, created_at=created_at)


# --- 保存と取り出し(往復) ---------------------------------------------------
@pytest.mark.parametrize(
    "m",
    [
        memo(),
        memo(body="重ね合わせと干渉", tags=["物理", "IT"]),
        Memo(title="編集済み", body="本文", tags=["数学"], created_at=T0, updated_at=T1),
    ],
    ids=["タグなし", "本文と複数タグ", "更新日時が作成日時と違う"],
)
def test_保存したメモを取り出すと同じ内容(repo, m):
    repo.add(m)

    assert repo.get(m.id) == m


def test_保存するとidが振られる(repo):
    m = memo()

    repo.add(m)

    assert isinstance(m.id, int)


def test_保存済みのメモを二重に保存できない(repo):
    m = memo()
    repo.add(m)

    with pytest.raises(ValueError):
        repo.add(m)


def test_存在しないidではNoneが返る(repo):
    assert repo.get(999) is None


def test_マイクロ秒を含む日時は保存できない(repo):
    with pytest.raises(ValueError):
        repo.add(memo(created_at=datetime(2026, 11, 16, 9, 0, 0, 1)))


def test_同じ名前のタグは複数のメモで1行を共有する(repo, conn):
    repo.add(memo(title="A", tags=["物理"]))
    repo.add(memo(title="B", tags=["物理"]))

    assert conn.execute("SELECT count(*) FROM tags WHERE name = '物理'").fetchone()[0] == 1


# --- 失敗したら何も残らない(1 トランザクション) ---------------------------
def break_memo_tags(conn):
    """memo_tags への挿入を必ず失敗させる(途中で失敗する状況を作るため。テスト用 DB にだけ作る)。"""
    conn.execute(
        "CREATE TRIGGER fail_link BEFORE INSERT ON memo_tags BEGIN SELECT RAISE(ABORT, 'テスト用の失敗'); END"
    )


def count(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_保存の途中で失敗したらメモもタグも残らずidも振られない(repo, conn):
    break_memo_tags(conn)
    m = memo(tags=["物理"])

    with pytest.raises(sqlite3.IntegrityError):
        repo.add(m)

    assert (count(conn, "memos"), count(conn, "tags"), m.id) == (0, 0, None)
