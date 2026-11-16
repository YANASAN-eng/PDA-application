"""ニュースの絞り込みキーワードの保存と取り出し(SQLite)。

ドメインの値 ↔ DB の値:
  group  KeywordGroup.IT  ↔ 'IT'(Enum の名前)
"""

import sqlite3

from pda.db._transaction import transaction
from pda.domain.keyword import Keyword, KeywordGroup, is_same_word


class DuplicateKeywordError(ValueError):
    """同じグループに同じ語(大文字小文字だけの違いを含む)が登録済み。"""


class KeywordRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_all(self) -> list[Keyword]:
        """登録した順(id の昇順)。グループごとの分け方はドメイン(as_groups)に任せる。"""
        rows = self._conn.execute("SELECT id, grp, word FROM keywords ORDER BY id")
        return [Keyword(id=id_, group=KeywordGroup[grp], word=word) for id_, grp, word in rows]

    def add(self, keyword: Keyword) -> None:
        """保存して keyword.id を振る。同じグループに同じ語があれば DuplicateKeywordError。"""
        if keyword.id is not None:
            raise ValueError(f"保存済みのキーワードです(id={keyword.id})")
        with transaction(self._conn):
            # 「同じ語」の判定はドメインの規則で行う(DB の NOCASE は ASCII の英字しか同一視しないため)
            for (existing,) in self._conn.execute(
                "SELECT word FROM keywords WHERE grp = ?", (keyword.group.name,)
            ).fetchall():
                if is_same_word(existing, keyword.word):
                    raise DuplicateKeywordError(
                        f"「{keyword.word}」は {keyword.group.label} に登録済みです(「{existing}」)"
                    )
            cur = self._conn.execute(
                "INSERT INTO keywords (grp, word) VALUES (?, ?)", (keyword.group.name, keyword.word)
            )
        keyword.id = cur.lastrowid  # COMMIT できてから振る

    def delete(self, keyword_id: int) -> None:
        cur = self._conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
        if cur.rowcount == 0:
            raise LookupError(f"キーワードが見つかりません(id={keyword_id})")
