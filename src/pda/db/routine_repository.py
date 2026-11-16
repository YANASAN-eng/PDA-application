"""日課の保存と取り出し(SQLite)。

1 件の日課は routines(タイトル)と routine_weekdays(曜日 1 つにつき 1 行)にまたがる。
追加・更新はその 2 つへの書き込みを 1 トランザクションで行う。
実行の記録は routine_checks(日課 × やった日)。行がなければその日は未完了。
"""

import sqlite3
from collections import defaultdict
from datetime import date

from pda.db._convert import date_to_db
from pda.db._transaction import transaction
from pda.domain.routine import Routine


class RoutineRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # --- 日課 --------------------------------------------------------------------
    def add(self, routine: Routine) -> None:
        """保存して routine.id を振る。"""
        if routine.id is not None:
            raise ValueError(f"保存済みの日課です(id={routine.id})")
        with transaction(self._conn):
            new_id = self._conn.execute("INSERT INTO routines (title) VALUES (?)", (routine.title,)).lastrowid
            self._set_weekdays(new_id, routine.weekdays)
        routine.id = new_id  # COMMIT できてから振る

    def get(self, routine_id: int) -> Routine | None:
        row = self._conn.execute("SELECT id, title FROM routines WHERE id = ?", (routine_id,)).fetchone()
        if row is None:
            return None
        weekdays = [w for (w,) in self._conn.execute(
            "SELECT weekday FROM routine_weekdays WHERE routine_id = ?", (routine_id,))]
        return Routine(id=row[0], title=row[1], weekdays=weekdays)

    def list_all(self) -> list[Routine]:
        """登録した順(id の昇順)。"""
        weekdays = self._weekdays_of()
        rows = self._conn.execute("SELECT id, title FROM routines ORDER BY id").fetchall()
        return [Routine(id=id_, title=title, weekdays=weekdays[id_]) for id_, title in rows]

    def update(self, routine: Routine) -> None:
        """タイトルと曜日を書き換える(曜日は付け直す)。"""
        if routine.id is None:
            raise ValueError("保存前の日課は更新できません")
        with transaction(self._conn):
            cur = self._conn.execute("UPDATE routines SET title = ? WHERE id = ?", (routine.title, routine.id))
            if cur.rowcount == 0:
                raise LookupError(f"日課が見つかりません(id={routine.id})")
            self._conn.execute("DELETE FROM routine_weekdays WHERE routine_id = ?", (routine.id,))
            self._set_weekdays(routine.id, routine.weekdays)

    def delete(self, routine_id: int) -> None:
        """日課を消す。曜日と実行の記録は ON DELETE CASCADE で消える。"""
        cur = self._conn.execute("DELETE FROM routines WHERE id = ?", (routine_id,))
        if cur.rowcount == 0:
            raise LookupError(f"日課が見つかりません(id={routine_id})")

    # --- 実行の記録 ----------------------------------------------------------------
    def checked_on(self, day: date) -> set[int]:
        """day にやった日課の id。"""
        rows = self._conn.execute("SELECT routine_id FROM routine_checks WHERE day = ?", (date_to_db(day),))
        return {r[0] for r in rows}

    def check(self, routine_id: int, day: date) -> None:
        """day にやったと記録する。既に記録があれば何もしない(再送信でエラーにしない)。"""
        self._require(routine_id)
        self._conn.execute(
            "INSERT INTO routine_checks (routine_id, day) VALUES (?, ?) ON CONFLICT DO NOTHING",
            (routine_id, date_to_db(day)),
        )

    def uncheck(self, routine_id: int, day: date) -> None:
        """day の記録を消す。記録がなければ何もしない。"""
        self._require(routine_id)
        self._conn.execute(
            "DELETE FROM routine_checks WHERE routine_id = ? AND day = ?", (routine_id, date_to_db(day))
        )

    # --- 内部 ----------------------------------------------------------------------
    def _set_weekdays(self, routine_id: int, weekdays) -> None:
        self._conn.executemany(
            "INSERT INTO routine_weekdays (routine_id, weekday) VALUES (?, ?)",
            [(routine_id, d) for d in sorted(weekdays)],
        )

    def _weekdays_of(self) -> dict[int, set[int]]:
        # 日課ごとに問い合わせると N+1 回になるので、まとめて 1 回で取る
        result: defaultdict[int, set[int]] = defaultdict(set)
        for routine_id, weekday in self._conn.execute("SELECT routine_id, weekday FROM routine_weekdays"):
            result[routine_id].add(weekday)
        return result

    def _require(self, routine_id: int) -> None:
        if self._conn.execute("SELECT 1 FROM routines WHERE id = ?", (routine_id,)).fetchone() is None:
            raise LookupError(f"日課が見つかりません(id={routine_id})")
