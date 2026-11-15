"""予定(AllDayEvent / TimedEvent)の保存と取り出し(SQLite)。

1 テーブル events に両方を持ち、all_day で読み分ける:
  all_day = 1 → AllDayEvent(start_at / end_at は 'YYYY-MM-DD')
  all_day = 0 → TimedEvent (start_at / end_at は 'YYYY-MM-DDTHH:MM:SS')

「その日に出る予定」の判定はドメイン(pda.domain.event.events_on)に任せ、
ここでは SQL で絞り込まない。判定ルールを 1 か所に保つため。
"""

import sqlite3

from pda.db._convert import date_from_db, date_to_db, datetime_from_db, datetime_to_db
from pda.domain.event import AllDayEvent, TimedEvent

Event = AllDayEvent | TimedEvent

# 列名はコード内の定数なので f-string で埋め込んでよい。値は必ず ? プレースホルダで渡す
_COLUMNS = "id, title, all_day, start_at, end_at, location, memo"


def _to_row(event: Event) -> tuple:
    if isinstance(event, AllDayEvent):
        all_day, convert = 1, date_to_db
    else:
        all_day, convert = 0, datetime_to_db
    return (
        event.title,
        all_day,
        convert(event.start),
        convert(event.end) if event.end is not None else None,
        event.location,
        event.memo,
    )


def _from_row(row: tuple) -> Event:
    id_, title, all_day, start_at, end_at, location, memo = row
    cls, convert = (AllDayEvent, date_from_db) if all_day else (TimedEvent, datetime_from_db)
    return cls(
        id=id_,
        title=title,
        start=convert(start_at),
        end=convert(end_at) if end_at is not None else None,
        location=location,
        memo=memo,
    )


class EventRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, event: Event) -> None:
        """保存して event.id を振る。"""
        if event.id is not None:
            raise ValueError(f"保存済みの予定です(id={event.id})")
        cur = self._conn.execute(
            "INSERT INTO events (title, all_day, start_at, end_at, location, memo) VALUES (?, ?, ?, ?, ?, ?)",
            _to_row(event),
        )
        event.id = cur.lastrowid

    def get(self, event_id: int) -> Event | None:
        row = self._conn.execute(f"SELECT {_COLUMNS} FROM events WHERE id = ?", (event_id,)).fetchone()
        return _from_row(row) if row else None

    def list_all(self) -> list[Event]:
        """開始の早い順。同じ日なら終日予定が先('YYYY-MM-DD' < 'YYYY-MM-DDT…')。同じ開始なら保存した順。"""
        rows = self._conn.execute(f"SELECT {_COLUMNS} FROM events ORDER BY start_at, id").fetchall()
        return [_from_row(r) for r in rows]

    def update(self, event: Event) -> None:
        """内容を書き換える。終日予定 ⇄ 時刻付き予定の種類の変更もできる。"""
        if event.id is None:
            raise ValueError("保存前の予定は更新できません")
        cur = self._conn.execute(
            "UPDATE events SET title = ?, all_day = ?, start_at = ?, end_at = ?, location = ?, memo = ? WHERE id = ?",
            (*_to_row(event), event.id),
        )
        if cur.rowcount == 0:
            raise LookupError(f"予定が見つかりません(id={event.id})")

    def delete(self, event_id: int) -> None:
        cur = self._conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        if cur.rowcount == 0:
            raise LookupError(f"予定が見つかりません(id={event_id})")
