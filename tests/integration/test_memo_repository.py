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
