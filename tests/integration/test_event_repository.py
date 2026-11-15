from datetime import date, datetime

import pytest

from pda.db.event_repository import EventRepository
from pda.db.migrate import connect, migrate
from pda.domain.event import AllDayEvent, TimedEvent, events_on

DAY = date(2026, 11, 20)
NEXT = date(2026, 11, 21)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute)


@pytest.fixture
def repo():
    conn = connect(":memory:")
    migrate(conn)
    yield EventRepository(conn)
    conn.close()


# --- 保存と取り出し(往復) ---------------------------------------------------
@pytest.mark.parametrize(
    "event",
    [
        AllDayEvent(title="誕生日", start=DAY),
        AllDayEvent(title="旅行", start=DAY, end=NEXT, location="京都", memo="切符を買う"),
        TimedEvent(title="電話", start=at(DAY, 9)),
        TimedEvent(title="会議", start=at(DAY, 10), end=at(DAY, 11), location="会議室A", memo="資料を印刷"),
        TimedEvent(title="夜勤", start=at(DAY, 23), end=at(NEXT, 1)),
    ],
    ids=["終日1日", "終日期間と場所とメモ", "時刻付き終了なし", "時刻付き全項目", "日またぎ"],
)
def test_保存した予定を取り出すと同じ種類で同じ内容(repo, event):
    repo.add(event)

    loaded = repo.get(event.id)

    assert type(loaded) is type(event)
    assert loaded == event


def test_保存するとidが振られる(repo):
    e = AllDayEvent(title="誕生日", start=DAY)

    repo.add(e)

    assert isinstance(e.id, int)


def test_保存済みの予定を二重に保存できない(repo):
    e = AllDayEvent(title="誕生日", start=DAY)
    repo.add(e)

    with pytest.raises(ValueError):
        repo.add(e)


def test_存在しないidではNoneが返る(repo):
    assert repo.get(999) is None


def test_マイクロ秒を含む日時は保存できない(repo):
    with pytest.raises(ValueError):
        repo.add(TimedEvent(title="会議", start=datetime(2026, 11, 20, 10, 0, 0, 1)))


# --- 一覧 ------------------------------------------------------------------
def test_一覧は開始の早い順で同じ日なら終日予定が先(repo):
    repo.add(TimedEvent(title="翌日の会議", start=at(NEXT, 9)))
    repo.add(TimedEvent(title="昼食", start=at(DAY, 12)))
    repo.add(AllDayEvent(title="誕生日", start=DAY))
    repo.add(TimedEvent(title="朝会", start=at(DAY, 9)))

    assert [e.title for e in repo.list_all()] == ["誕生日", "朝会", "昼食", "翌日の会議"]


def test_開始が同じ予定は保存した順(repo):
    repo.add(TimedEvent(title="先", start=at(DAY, 9)))
    repo.add(TimedEvent(title="後", start=at(DAY, 9)))

    assert [e.title for e in repo.list_all()] == ["先", "後"]


def test_取り出した一覧をドメインのその日の一覧にそのまま渡せる(repo):
    repo.add(TimedEvent(title="夜勤", start=at(DAY, 23), end=at(NEXT, 1)))
    repo.add(AllDayEvent(title="旅行", start=DAY, end=NEXT))
    repo.add(TimedEvent(title="朝会", start=at(NEXT, 9)))
    repo.add(TimedEvent(title="前日の予定", start=at(DAY, 9)))

    assert [e.title for e in events_on(NEXT, repo.list_all())] == ["旅行", "夜勤", "朝会"]


# --- 更新と削除 -------------------------------------------------------------
def test_更新すると内容が変わる(repo):
    e = TimedEvent(title="会議", start=at(DAY, 10))
    repo.add(e)

    e.title, e.end, e.location = "延長した会議", at(DAY, 12), "会議室B"
    repo.update(e)

    assert repo.get(e.id) == e


def test_終日予定を時刻付き予定に変えられる(repo):
    e = AllDayEvent(title="打ち合わせ", start=DAY)
    repo.add(e)

    changed = TimedEvent(id=e.id, title="打ち合わせ", start=at(DAY, 15), end=at(DAY, 16))
    repo.update(changed)

    loaded = repo.get(e.id)
    assert isinstance(loaded, TimedEvent)
    assert loaded == changed


def test_保存前の予定は更新できない(repo):
    with pytest.raises(ValueError):
        repo.update(AllDayEvent(title="誕生日", start=DAY))


def test_存在しない予定は更新できない(repo):
    with pytest.raises(LookupError):
        repo.update(AllDayEvent(title="誕生日", start=DAY, id=999))


def test_削除すると取り出せなくなる(repo):
    e = AllDayEvent(title="誕生日", start=DAY)
    repo.add(e)

    repo.delete(e.id)

    assert repo.get(e.id) is None
    assert repo.list_all() == []


def test_存在しない予定は削除できない(repo):
    with pytest.raises(LookupError):
        repo.delete(999)
