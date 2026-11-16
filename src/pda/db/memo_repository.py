"""メモ(Memo)の保存と取り出し(SQLite)。

1 件のメモは 3 つのテーブルにまたがる:
  memos      … タイトル・本文・日時
  tags       … タグ名(名前ごとに 1 行。どのメモからも使われなくなっても消さない)
  memo_tags  … どのメモにどのタグが付いているか
"""

import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

from pda.db._convert import datetime_from_db, datetime_to_db
from pda.domain.memo import Memo


def _to_row(memo: Memo) -> tuple:
    """memos の (title, body, created_at, updated_at) の値。"""
    return (memo.title, memo.body, datetime_to_db(memo.created_at), datetime_to_db(memo.updated_at))


# 列名はコード内の定数なので f-string で埋め込んでよい。値は必ず ? プレースホルダで渡す
_COLUMNS = "id, title, body, created_at, updated_at"


def _from_row(row: tuple, tags: Iterable[str]) -> Memo:
    id_, title, body, created_at, updated_at = row
    return Memo(
        id=id_,
        title=title,
        body=body,
        tags=tags,
        created_at=datetime_from_db(created_at),
        updated_at=datetime_from_db(updated_at),
    )


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
        row = self._conn.execute(f"SELECT {_COLUMNS} FROM memos WHERE id = ?", (memo_id,)).fetchone()
        return _from_row(row, self._tags_of(memo_id)) if row else None

    def list_all(self) -> list[Memo]:
        """保存した順(id の昇順)。表示の並び順はドメインの memos_by_updated で決める。"""
        rows = self._conn.execute(f"SELECT {_COLUMNS} FROM memos ORDER BY id").fetchall()
        # メモごとに問い合わせると N+1 回になるので、結び付きは 1 回でまとめて取る
        tags: defaultdict[int, list[str]] = defaultdict(list)
        for memo_id, name in self._conn.execute(
            "SELECT mt.memo_id, t.name FROM memo_tags mt JOIN tags t ON t.id = mt.tag_id"
        ):
            tags[memo_id].append(name)
        return [_from_row(r, tags[r[0]]) for r in rows]

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

    def delete(self, memo_id: int) -> None:
        """メモを消す。memo_tags の結び付きは ON DELETE CASCADE で消え、tags は残る。"""
        cur = self._conn.execute("DELETE FROM memos WHERE id = ?", (memo_id,))
        if cur.rowcount == 0:
            raise LookupError(f"メモが見つかりません(id={memo_id})")

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

    def _link_tags(self, memo_id: int, tags: Iterable[str]) -> None:
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
