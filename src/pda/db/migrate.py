"""DB スキーマのマイグレーション。

- マイグレーションは `migrations/NNNN_説明.sql`。番号は 1 から隙間なく連続させる
- 適用済みの版は `PRAGMA user_version` に記録する
- 1 つのマイグレーションは 1 トランザクションで実行し、失敗したら丸ごと取り消す
  (そのため SQL ファイルの中に BEGIN / COMMIT を書かない)
"""

import re
import sqlite3
from datetime import datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_NAME = re.compile(r"^(\d{4})_[^.]+\.sql$")


def connect(path: str | Path) -> sqlite3.Connection:
    """外部キー制約を有効にした接続を返す。トランザクションは明示的に管理する。"""
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite の既定は OFF。接続ごとに必要
    return conn


def current_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _load(migrations_dir: Path) -> list[tuple[int, Path]]:
    """マイグレーションを番号順に返す。番号が 1 から連続していなければ ValueError。"""
    found = []
    for path in migrations_dir.iterdir():
        m = _NAME.match(path.name)
        if m:
            found.append((int(m.group(1)), path))
    found.sort()
    numbers = [n for n, _ in found]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(f"マイグレーション番号が 1 から連続していません: {numbers}")
    return found


def _pending(conn: sqlite3.Connection, migrations: list[tuple[int, Path]]) -> list[tuple[int, Path]]:
    version = current_version(conn)
    latest = len(migrations)
    if version > latest:
        raise RuntimeError(f"DB の版 {version} はこのアプリが知る最新版 {latest} より新しいので触りません")
    return migrations[version:]


def migrate(conn: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[int]:
    """未適用のマイグレーションを番号順に適用し、適用した番号を返す。"""
    applied = []
    for number, path in _pending(conn, _load(migrations_dir)):
        sql = path.read_text(encoding="utf-8")
        try:
            # executescript は実行前に COMMIT するので、BEGIN〜COMMIT をスクリプト側に含める
            conn.executescript(f"BEGIN;\n{sql}\n;PRAGMA user_version = {number};\nCOMMIT;")
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        applied.append(number)
    return applied


def migrate_file(db_path: Path, *, now: datetime, migrations_dir: Path = MIGRATIONS_DIR) -> list[int]:
    """DB ファイルにマイグレーションを適用する。既存の DB に未適用分があれば先にバックアップを取る。"""
    existed = db_path.exists()
    conn = connect(db_path)
    try:
        if existed and _pending(conn, _load(migrations_dir)):
            backup_path = db_path.with_name(f"{db_path.stem}.{now:%Y%m%dT%H%M%S}.bak")
            dest = sqlite3.connect(backup_path)
            try:
                conn.backup(dest)  # SQLite のバックアップ API(書き込み中でも一貫したコピー)
            finally:
                dest.close()
        return migrate(conn, migrations_dir)
    finally:
        conn.close()
