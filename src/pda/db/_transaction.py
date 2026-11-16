"""複数の書き込みを 1 トランザクションにまとめる(リポジトリ共通)。"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """中の書き込みをすべて反映するか、1 つも反映しないか。

    connect() の接続は自動コミット(isolation_level=None)なので、BEGIN / COMMIT / ROLLBACK を明示する。
    """
    conn.execute("BEGIN")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
