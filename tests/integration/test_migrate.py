"""マイグレーションの仕組みのテスト(テスト用の小さな SQL を使う)。"""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from pda.db.migrate import checksum, connect, current_version, migrate, migrate_file

NOW = datetime(2026, 11, 15, 9, 0, 0)


def write(directory: Path, name: str, sql: str) -> None:
    (directory / name).write_text(sql, encoding="utf-8")


def tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {r[0] for r in rows}


@pytest.fixture
def mig_dir(tmp_path: Path) -> Path:
    d = tmp_path / "migrations"
    d.mkdir()
    write(d, "0001_create_a.sql", "CREATE TABLE a (x INTEGER);")
    write(d, "0002_create_b.sql", "CREATE TABLE b (y INTEGER);")
    return d


@pytest.fixture
def conn():
    c = connect(":memory:")
    yield c
    c.close()


# --- 接続 ------------------------------------------------------------------
def test_接続すると外部キー制約が有効になっている(conn):
    # SQLite は既定で外部キー制約を検査しない。接続ごとに有効にする必要がある
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# --- 適用 ------------------------------------------------------------------
def test_空のDBの版は0(conn):
    assert current_version(conn) == 0


def test_空のDBに適用すると全マイグレーションが番号順に適用される(conn, mig_dir):
    applied = migrate(conn, mig_dir)

    assert applied == [1, 2]
    assert current_version(conn) == 2
    assert {"a", "b"} <= tables(conn)


def test_最新の版のDBに再度適用しても何もしない(conn, mig_dir):
    migrate(conn, mig_dir)

    assert migrate(conn, mig_dir) == []
    assert current_version(conn) == 2


def test_途中の版からは未適用の分だけ適用されデータは残る(conn, tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    write(d, "0001_create_a.sql", "CREATE TABLE a (x INTEGER);")
    migrate(conn, d)
    conn.execute("INSERT INTO a (x) VALUES (42)")

    write(d, "0002_add_column.sql", "ALTER TABLE a ADD COLUMN z TEXT;")
    applied = migrate(conn, d)

    assert applied == [2]
    assert conn.execute("SELECT x, z FROM a").fetchall() == [(42, None)]


# --- 失敗・異常 -------------------------------------------------------------
def test_失敗したマイグレーションは丸ごと取り消され版も変わらない(conn, mig_dir):
    write(mig_dir, "0003_broken.sql", "CREATE TABLE c (z INTEGER);\nINSERT INTO no_such_table VALUES (1);")

    with pytest.raises(sqlite3.Error):
        migrate(conn, mig_dir)

    assert current_version(conn) == 2  # 0001, 0002 は成功済み
    assert "c" not in tables(conn)  # 0003 の途中まで実行された分も残らない


def test_番号が飛んでいたら何も適用しない(conn, tmp_path):
    d = tmp_path / "gap"
    d.mkdir()
    write(d, "0001_create_a.sql", "CREATE TABLE a (x INTEGER);")
    write(d, "0003_create_c.sql", "CREATE TABLE c (z INTEGER);")

    with pytest.raises(ValueError):
        migrate(conn, d)

    assert current_version(conn) == 0


def test_アプリが知っているより新しい版のDBには触らない(conn, mig_dir):
    conn.execute("PRAGMA user_version = 5")

    with pytest.raises(RuntimeError):
        migrate(conn, mig_dir)

    assert current_version(conn) == 5


# --- バックアップ -----------------------------------------------------------
def test_既存のDBに未適用分があるときは適用前にバックアップを取る(tmp_path, mig_dir):
    db = tmp_path / "pda.db"
    first_only = tmp_path / "first"
    first_only.mkdir()
    write(first_only, "0001_create_a.sql", "CREATE TABLE a (x INTEGER);")
    c = connect(db)
    migrate(c, first_only)
    c.execute("INSERT INTO a (x) VALUES (7)")
    c.close()

    migrate_file(db, now=NOW, migrations_dir=mig_dir)

    backup = tmp_path / "pda.20261115T090000.bak"
    assert backup.exists()
    b = connect(backup)
    assert current_version(b) == 1  # 適用前の状態
    assert b.execute("SELECT x FROM a").fetchall() == [(7,)]
    b.close()
    c = connect(db)
    assert current_version(c) == 2
    c.close()


def test_未適用分がなければバックアップを取らない(tmp_path, mig_dir):
    db = tmp_path / "pda.db"
    migrate_file(db, now=NOW, migrations_dir=mig_dir)

    migrate_file(db, now=datetime(2026, 11, 16), migrations_dir=mig_dir)

    assert list(tmp_path.glob("*.bak")) == []


def test_新しく作るDBはバックアップを取らない(tmp_path, mig_dir):
    migrate_file(tmp_path / "pda.db", now=NOW, migrations_dir=mig_dir)

    assert list(tmp_path.glob("*.bak")) == []


# --- チェックサム -----------------------------------------------------------


def test_同じ内容のファイルは同じチェックサムになる(tmp_path):
    a, b = tmp_path / "a.sql", tmp_path / "b.sql"
    a.write_bytes(b"CREATE TABLE t (x INTEGER);\n")
    b.write_bytes(b"CREATE TABLE t (x INTEGER);\n")

    assert checksum(a) == checksum(b)


def test_1文字でも違えばチェックサムが変わる(tmp_path):
    a, b = tmp_path / "a.sql", tmp_path / "b.sql"
    a.write_bytes(b"CREATE TABLE t (x INTEGER);\n")
    b.write_bytes(b"CREATE TABLE t (x INTEGER) ;\n")

    assert checksum(a) != checksum(b)


def test_改行コードの違いではチェックサムは変わらない(tmp_path):
    lf, crlf = tmp_path / "lf.sql", tmp_path / "crlf.sql"
    lf.write_bytes(b"-- c\nCREATE TABLE t (x INTEGER);\n")
    crlf.write_bytes(b"-- c\r\nCREATE TABLE t (x INTEGER);\r\n")

    assert checksum(lf) == checksum(crlf)


def test_チェックサムはSHA256の16進64文字(tmp_path):
    f = tmp_path / "a.sql"
    f.write_bytes(b"")

    assert checksum(f) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
