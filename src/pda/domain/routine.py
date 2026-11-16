"""日課(Daily)のドメインモデル(I/O なし)。

ToDo の完了は一度きりだが、日課は「どの日にやったか」を記録する(記録はリポジトリが持つ)。
日が変われば自然に未完了に戻るので、リセットの処理は持たない。
曜日は date.weekday() と同じ番号: 月=0, 火=1, …, 日=6。
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from pda.domain._validation import require_title

EVERY_DAY = frozenset(range(7))
_WEEKDAY_NAMES = "月火水木金土日"


def _normalize_weekdays(weekdays: Iterable[int]) -> frozenset[int]:
    days = frozenset(weekdays)
    if not days:
        raise ValueError("曜日を 1 つ以上選んでください")
    if not days <= EVERY_DAY:
        raise ValueError(f"曜日は 0(月)〜6(日)です: {sorted(days - EVERY_DAY)}")
    return days


@dataclass(kw_only=True)
class Routine:
    title: str
    weekdays: Iterable[int] = field(default=EVERY_DAY)  # 以後は frozenset[int]
    id: int | None = None  # 保存前は None。リポジトリが保存時に振る

    def __post_init__(self) -> None:
        require_title(self.title)
        self.weekdays = _normalize_weekdays(self.weekdays)

    def is_due_on(self, day: date) -> bool:
        return day.weekday() in self.weekdays


def routines_on(day: date, routines: Iterable[Routine]) -> list[Routine]:
    """その日の曜日の日課を、元の順序(登録した順)のまま返す。"""
    return [r for r in routines if r.is_due_on(day)]


def weekdays_label(weekdays: Iterable[int]) -> str:
    """'毎日' または '月・水・金'(月曜から順)。"""
    days = frozenset(weekdays)
    if days == EVERY_DAY:
        return "毎日"
    return "・".join(_WEEKDAY_NAMES[d] for d in sorted(days))
