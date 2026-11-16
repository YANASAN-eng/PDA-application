"""Task の保存と取り出し(SQLite)。

ドメインの値 ↔ DB の値 の対応:
  priority   Priority.HIGH      ↔ 'HIGH'(Enum の名前)
  due        date | None        ↔ 'YYYY-MM-DD' | NULL
  done       bool               ↔ 0 / 1
  created_at datetime(秒単位)  ↔ 'YYYY-MM-DDTHH:MM:SS'
  detail     str                ↔ TEXT(「なし」は ''。0002 で追加)
"""

import sqlite3

from pda.db._convert import date_from_db, date_to_db, datetime_from_db, datetime_to_db
from pda.domain.task import Priority, Task

# 列名はコード内の定数なので f-string で埋め込んでよい。値は必ず ? プレースホルダで渡す
_COLUMNS = "id, title, priority, due, done, created_at, detail"


def _to_row(task: Task) -> tuple:
    return (
        task.title,
        task.priority.name,
        date_to_db(task.due) if task.due else None,
        int(task.done),
        datetime_to_db(task.created_at),
        task.detail,
    )


def _from_row(row: tuple) -> Task:
    id_, title, priority, due, done, created_at, detail = row
    return Task(
        id=id_,
        title=title,
        priority=Priority[priority],
        due=date_from_db(due) if due else None,
        done=bool(done),
        created_at=datetime_from_db(created_at),
        detail=detail,
    )


class TaskRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, task: Task) -> None:
        """保存して task.id を振る。"""
        if task.id is not None:
            raise ValueError(f"保存済みのタスクです(id={task.id})")
        cur = self._conn.execute(
            "INSERT INTO tasks (title, priority, due, done, created_at, detail) VALUES (?, ?, ?, ?, ?, ?)",
            _to_row(task),
        )
        task.id = cur.lastrowid

    def get(self, task_id: int) -> Task | None:
        row = self._conn.execute(f"SELECT {_COLUMNS} FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _from_row(row) if row else None

    def list_all(self) -> list[Task]:
        """作成日時の古い順。同じ日時なら保存した順(id 順)。"""
        rows = self._conn.execute(f"SELECT {_COLUMNS} FROM tasks ORDER BY created_at, id").fetchall()
        return [_from_row(r) for r in rows]

    def update(self, task: Task) -> None:
        if task.id is None:
            raise ValueError("保存前のタスクは更新できません")
        cur = self._conn.execute(
            "UPDATE tasks SET title = ?, priority = ?, due = ?, done = ?, created_at = ?, detail = ? WHERE id = ?",
            (*_to_row(task), task.id),
        )
        if cur.rowcount == 0:
            raise LookupError(f"タスクが見つかりません(id={task.id})")

    def delete(self, task_id: int) -> None:
        cur = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cur.rowcount == 0:
            raise LookupError(f"タスクが見つかりません(id={task_id})")
