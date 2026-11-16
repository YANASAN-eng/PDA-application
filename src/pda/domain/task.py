"""ToDo タスクのドメインモデル(I/O なし)。"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from pda.domain._validation import require_title

OVERDUE_PREFIX = "【超過】-"


class Priority(Enum):
    """優先度。定義順 = 高い順。"""

    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"

    @property
    def label(self) -> str:
        return self.value


@dataclass(kw_only=True)
class Task:
    title: str
    priority: Priority
    created_at: datetime
    due: date | None = None
    done: bool = False
    detail: str = ""  # 任意。目的や補足(例: 何のための買い物か)。「なし」は空文字
    id: int | None = None  # 保存前は None。リポジトリが保存時に振る

    def __post_init__(self) -> None:
        require_title(self.title)

    def is_overdue(self, today: date) -> bool:
        """超過 = 未完了のまま期限の翌日以降になっていること(期限当日は含まない)。"""
        return not self.done and self.due is not None and today > self.due

    def display_title(self, today: date) -> str:
        return f"{OVERDUE_PREFIX}{self.title}" if self.is_overdue(today) else self.title


_PRIORITY_RANK = {p: i for i, p in enumerate(Priority)}  # 高=0, 中=1, 低=2


def incomplete_by_priority(tasks: Iterable[Task]) -> list[Task]:
    """未完了のタスクだけを、優先度の高い順 → 作成日時の古い順に返す。

    優先度も作成日時も同じなら元の順序を保つ(sorted は安定ソート)。
    """
    return sorted(
        (t for t in tasks if not t.done),
        key=lambda t: (_PRIORITY_RANK[t.priority], t.created_at),
    )


def completed_by_newest(tasks: Iterable[Task]) -> list[Task]:
    """完了済みのタスクだけを、作成日時の新しい順に返す。

    作成日時が同じなら元の順序を保つ(reverse=True でも sorted は安定)。
    """
    return sorted((t for t in tasks if t.done), key=lambda t: t.created_at, reverse=True)
