"""キーワード(keywords)のスキーマのテスト。"""

import shutil
import sqlite3

import pytest

from pda.db.migrate import MIGRATIONS_DIR, connect, current_version, migrate

Bad = sqlite3.IntegrityError


@pytest.fixture
def db():
    conn = connect(":memory:")
    migrate(conn)
    conn.execute("DELETE FROM keywords")  # 初期データを除いた空の状態で制約を試す
    yield conn
    conn.close()


def add(db, grp, word):
    db.execute("INSERT INTO keywords (grp, word) VALUES (?, ?)", (grp, word))


def test_正しいキーワードは保存できる(db):
    add(db, "IT", "AI")
    add(db, "MATH_PHYSICS", "量子")


def test_グループはMATH_PHYSICSとIT以外を保存できない(db):
    with pytest.raises(Bad):
        add(db, "BIOLOGY", "細胞")


@pytest.mark.parametrize("word", ["", " ", " AI", "AI "])
def test_空の語や前後に空白のある語は保存できない(db, word):
    with pytest.raises(Bad):
        add(db, "IT", word)


def test_同じグループに大文字小文字だけが違う語は保存できない(db):
    add(db, "IT", "AI")
    with pytest.raises(Bad):
        add(db, "IT", "ai")


def test_別のグループなら同じ語を保存できる(db):
    add(db, "IT", "量子コンピュータ")
    add(db, "MATH_PHYSICS", "量子コンピュータ")


def test_初期データとして今までのキーワードが入っている():
    conn = connect(":memory:")
    migrate(conn)
    rows = set(conn.execute("SELECT grp, word FROM keywords"))
    conn.close()

    assert {("MATH_PHYSICS", "量子"), ("MATH_PHYSICS", "quantum"), ("IT", "AI"), ("IT", "機械学習")} <= rows


def test_版3のデータは版4に上げても残る(tmp_path):
    v3_dir = tmp_path / "v3"
    v3_dir.mkdir()
    for name in ("0001_initial.sql", "0002_add_task_detail.sql", "0003_add_news.sql"):
        shutil.copy(MIGRATIONS_DIR / name, v3_dir)
    conn = connect(":memory:")
    migrate(conn, v3_dir)
    conn.execute("INSERT INTO feeds (name, url) VALUES ('Example', 'https://example.com/feed.xml')")

    migrate(conn)

    assert current_version(conn) >= 4
    assert conn.execute("SELECT name FROM feeds").fetchall() == [("Example",)]
    conn.close()
