"""メモ(Memo)の保存と取り出し(SQLite)。

1 件のメモは 3 つのテーブルにまたがる:
  memos      … タイトル・本文・日時
  tags       … タグ名(名前ごとに 1 行。どのメモからも使われなくなっても消さない)
  memo_tags  … どのメモにどのタグが付いているか
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from pda.db._convert import datetime_from_db, datetime_to_db
from pda.domain.memo import Memo


def _to_row(memo: Memo) -> tuple:
    """memos の (title, body, created_at, updated_at) の値。"""
    return (memo.title, memo.body, datetime_to_db(memo.created_at), datetime_to_db(memo.updated_at))


class MemoRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, memo: Memo) -> None:
        """保存して memo.id を振る。"""
        if memo.id is not None:
            raise ValueError(f"保存済みのメモです(id={memo.id})")
        with self._transaction():
            cur = self._conn.execute(
                "INSERT INTO memos (title, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
                _to_row(memo),
            )
            new_id = cur.lastrowid
            self._link_tags(new_id, memo.tags)
        memo.id = new_id  # COMMIT できてから振る(失敗したら memo は変わらない)

    def get(self, memo_id: int) -> Memo | None:
        row = self._conn.execute(
            "SELECT title, body, created_at, updated_at FROM memos WHERE id = ?", (memo_id,)
        ).fetchone()
        if row is None:
            return None
        title, body, created_at, updated_at = row
        return Memo(
            id=memo_id,
            title=title,
            body=body,
            tags=self._tags_of(memo_id),
            created_at=datetime_from_db(created_at),
            updated_at=datetime_from_db(updated_at),
        )

    def update(self, memo: Memo) -> None:
        """内容とタグを書き換える。タグは結び付けを付け直す(外したタグも tags には残る)。"""
        if memo.id is None:
            raise ValueError("保存前のメモは更新できません")
        with self._transaction():
            cur = self._conn.execute(
                "UPDATE memos SET title = ?, body = ?, created_at = ?, updated_at = ? WHERE id = ?",
                (*_to_row(memo), memo.id),
            )
            if cur.rowcount == 0:
                raise LookupError(f"メモが見つかりません(id={memo.id})")
            self._conn.execute("DELETE FROM memo_tags WHERE memo_id = ?", (memo.id,))
            self._link_tags(memo.id, memo.tags)

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        """中の書き込みをすべて反映するか、1 つも反映しないか(接続は自動コミットなので明示する)。"""
        self._conn.execute("BEGIN")
        try:
            yield
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    def _link_tags(self, memo_id: int, tags) -> None:
        for name in tags:
            # 既にある名前なら何もしない(tags.name は UNIQUE)
            self._conn.execute("INSERT INTO tags (name) VALUES (?) ON CONFLICT (name) DO NOTHING", (name,))
            self._conn.execute(
                "INSERT INTO memo_tags (memo_id, tag_id) SELECT ?, id FROM tags WHERE name = ?",
                (memo_id, name),
            )

    def _tags_of(self, memo_id: int) -> list[str]:
        rows = self._conn.execute(
            "SELECT t.name FROM memo_tags mt JOIN tags t ON t.id = mt.tag_id WHERE mt.memo_id = ?",
            (memo_id,),
        ).fetchall()
        return [name for (name,) in rows]
