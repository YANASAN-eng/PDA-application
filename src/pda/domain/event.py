"""予定のドメインモデル(I/O なし)。

時刻はタイムゾーンを持たない日本時間(naive datetime)として扱う。
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from pda.domain._validation import require_title


@dataclass
class AllDayEvent:
    """終日予定。期間は開始日から終了日まで(終了日を含む)。"""

    title: str
    start: date
    end: date | None = None
    location: str | None = None
    memo: str | None = None
    id: int | None = None  # 保存前は None。リポジトリが保存時に振る

    def __post_init__(self) -> None:
        require_title(self.title)
        # datetime は date のサブクラスなので isinstance(date) では区別できない
        for value in (self.start, self.end):
            if isinstance(value, datetime):
                raise TypeError("終日予定には日付(date)を渡してください")
        if self.end is not None and self.end < self.start:
            raise ValueError("終了日は開始日以降にしてください")

    def occurs_on(self, day: date) -> bool:
        last = self.end if self.end is not None else self.start
        return self.start <= day <= last


@dataclass
class TimedEvent:
    """時刻付き予定。期間は [開始, 終了)。終了なし or 終了=開始 は瞬間の予定。"""

    title: str
    start: datetime
    end: datetime | None = None
    location: str | None = None
    memo: str | None = None
    id: int | None = None  # 保存前は None。リポジトリが保存時に振る

    def __post_init__(self) -> None:
        require_title(self.title)
        if self.end is not None and self.end < self.start:
            raise ValueError("終了は開始以降にしてください")

    def occurs_on(self, day: date) -> bool:
        day_start = datetime.combine(day, time.min)
        day_end = day_start + timedelta(days=1)
        if self.end is None or self.end == self.start:
            return day_start <= self.start < day_end
        # 半開区間 [start, end) と [day_start, day_end) が重なる条件
        return self.start < day_end and self.end > day_start


def events_on(day: date, events: Iterable[AllDayEvent | TimedEvent]) -> list[AllDayEvent | TimedEvent]:
    """その日に出る予定を、終日予定 → 時刻付き予定(開始順)の順で返す。"""
    todays = [e for e in events if e.occurs_on(day)]
    all_day = [e for e in todays if isinstance(e, AllDayEvent)]
    timed = sorted((e for e in todays if isinstance(e, TimedEvent)), key=lambda e: e.start)
    return all_day + timed


Event = AllDayEvent | TimedEvent


def _candidate_days(event: Event) -> Iterable[date]:
    """予定が出るかもしれない日(開始日〜終了日)。実際に出るかは occurs_on で決める。"""
    if isinstance(event, AllDayEvent):
        first, last = event.start, event.end or event.start
    else:
        first, last = event.start.date(), (event.end or event.start).date()
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


def _by_day(events: Iterable[Event], days: Iterable[date]) -> list[tuple[date, list[Event]]]:
    events = list(events)
    result = [(day, events_on(day, events)) for day in days]
    return [(day, items) for day, items in result if items]


def upcoming_by_day(events: Iterable[Event], today: date) -> list[tuple[date, list[Event]]]:
    """今日以降で予定のある日を、今日から順に。日の中は events_on の順(終日 → 開始時刻順)。"""
    events = list(events)
    days = {day for e in events for day in _candidate_days(e) if day >= today}
    return _by_day(events, sorted(days))


def past_by_day(events: Iterable[Event], today: date) -> list[tuple[date, list[Event]]]:
    """今日より前で予定のあった日を、新しい日から順に。"""
    events = list(events)
    days = {day for e in events for day in _candidate_days(e) if day < today}
    return _by_day(events, sorted(days, reverse=True))
