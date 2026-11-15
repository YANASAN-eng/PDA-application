from datetime import date, datetime

import pytest

from pda.domain.event import AllDayEvent, TimedEvent, events_on

DAY = date(2026, 11, 15)
NEXT = date(2026, 11, 16)
PREV = date(2026, 11, 14)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute)


# --- 作成時の検証 ------------------------------------------------------------
@pytest.mark.parametrize("title", ["", "   "])
def test_空のタイトルでは予定を作れない(title):
    with pytest.raises(ValueError):
        TimedEvent(title=title, start=at(DAY, 10))
    with pytest.raises(ValueError):
        AllDayEvent(title=title, start=DAY)


def test_時刻付き予定は終了が開始より前だと作れない():
    with pytest.raises(ValueError):
        TimedEvent(title="会議", start=at(DAY, 10), end=at(DAY, 9))


def test_終日予定は終了日が開始日より前だと作れない():
    with pytest.raises(ValueError):
        AllDayEvent(title="旅行", start=DAY, end=PREV)


def test_終日予定に時刻付きの値は渡せない():
    # datetime は date のサブクラスなので、明示的に弾く必要がある
    with pytest.raises(TypeError):
        AllDayEvent(title="旅行", start=at(DAY, 10))


def test_場所とメモは指定しなくてもよい():
    event = TimedEvent(title="会議", start=at(DAY, 10))

    assert event.location is None
    assert event.memo is None


# --- 終日予定がその日に出るか --------------------------------------------------
def test_1日だけの終日予定はその日にだけ出る():
    event = AllDayEvent(title="誕生日", start=DAY)

    assert event.occurs_on(DAY) is True
    assert event.occurs_on(PREV) is False
    assert event.occurs_on(NEXT) is False


def test_複数日の終日予定は終了日を含む全日に出る():
    event = AllDayEvent(title="旅行", start=PREV, end=NEXT)

    assert [event.occurs_on(d) for d in (PREV, DAY, NEXT)] == [True, True, True]
    assert event.occurs_on(date(2026, 11, 17)) is False


# --- 時刻付き予定がその日に出るか ----------------------------------------------
def test_その日の中に収まる予定はその日にだけ出る():
    event = TimedEvent(title="会議", start=at(DAY, 10), end=at(DAY, 11))

    assert event.occurs_on(DAY) is True
    assert event.occurs_on(NEXT) is False


def test_日をまたぐ予定は重なる両方の日に出る():
    event = TimedEvent(title="夜勤", start=at(DAY, 23), end=at(NEXT, 1))

    assert event.occurs_on(DAY) is True
    assert event.occurs_on(NEXT) is True


def test_翌日0時ちょうどに終わる予定は翌日には出ない():
    event = TimedEvent(title="飲み会", start=at(DAY, 22), end=at(NEXT, 0))

    assert event.occurs_on(DAY) is True
    assert event.occurs_on(NEXT) is False


def test_終了のない予定は開始日にだけ出る():
    event = TimedEvent(title="電話", start=at(DAY, 0))

    assert event.occurs_on(DAY) is True
    assert event.occurs_on(PREV) is False


def test_終了と開始が同じ予定は開始日にだけ出る():
    event = TimedEvent(title="締切", start=at(DAY, 0), end=at(DAY, 0))

    assert event.occurs_on(DAY) is True
    assert event.occurs_on(PREV) is False


# --- その日の一覧 ------------------------------------------------------------
def test_その日の一覧は終日予定が先で時刻付きは開始順():
    lunch = TimedEvent(title="昼食", start=at(DAY, 12))
    birthday = AllDayEvent(title="誕生日", start=DAY)
    meeting = TimedEvent(title="会議", start=at(DAY, 9))
    tomorrow = TimedEvent(title="明日の予定", start=at(NEXT, 9))
    trip = AllDayEvent(title="旅行", start=PREV, end=NEXT)

    result = events_on(DAY, [lunch, birthday, meeting, tomorrow, trip])

    assert [e.title for e in result] == ["誕生日", "旅行", "会議", "昼食"]


def test_前日から続く予定はその日の最初の時刻付き予定になる():
    night = TimedEvent(title="夜勤", start=at(PREV, 23), end=at(DAY, 1))
    meeting = TimedEvent(title="会議", start=at(DAY, 9))

    result = events_on(DAY, [meeting, night])

    assert [e.title for e in result] == ["夜勤", "会議"]


# --- id --------------------------------------------------------------------
def test_保存前の予定はidを持たない():
    assert AllDayEvent(title="誕生日", start=DAY).id is None
    assert TimedEvent(title="会議", start=at(DAY, 10)).id is None
