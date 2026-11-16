from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from pda.db.event_repository import EventRepository
from pda.db.migrate import connect
from pda.domain.event import AllDayEvent, TimedEvent
from pda.web.app import create_app

NOW = datetime(2026, 11, 16, 9, 0)  # 月曜日
TODAY = NOW.date()


def at(day: int, hour: int) -> datetime:
    return datetime(2026, 11, day, hour, 0)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "pda.db"


@pytest.fixture
def client(db_path):
    return TestClient(create_app(db_path, clock=lambda: NOW))


@pytest.fixture
def events(client, db_path):
    conn = connect(db_path)
    yield EventRepository(conn)
    conn.close()


def appear_in_order(html: str, *texts: str) -> bool:
    positions = [html.find(t) for t in texts]
    return -1 not in positions and positions == sorted(positions)


def test_アプリを開くと今日の画面へ移動する(client):
    res = client.get("/", follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/today"


def test_今日の日付と今日の予定を終日から時刻順に出し他の日の予定は出さない(client, events):
    events.add(TimedEvent(title="夕食", start=at(16, 19)))
    events.add(TimedEvent(title="明日の会議", start=at(17, 10)))
    events.add(AllDayEvent(title="誕生日", start=TODAY))
    events.add(TimedEvent(title="朝会", start=at(16, 9)))

    html = client.get("/today").text

    assert appear_in_order(html, "<h1>今日</h1>", "11月16日(月)", "誕生日", "朝会", "夕食")
    assert "明日の会議" not in html


def test_日をまたいで今日に重なる予定も出る(client, events):
    events.add(AllDayEvent(title="旅行", start=date(2026, 11, 15), end=date(2026, 11, 17)))

    assert "旅行" in client.get("/today").text


def test_今日の予定がなければその旨を表示する(client):
    assert "今日の予定はありません" in client.get("/today").text


def test_予定の画面へのリンクがある(client):
    assert 'href="/events" class="pill-link"' in client.get("/today").text


def test_予定のカードは予定の画面と同じ編集ポップアップで開く(client, events):
    e = TimedEvent(title="朝会", start=at(16, 9))
    events.add(e)

    html = client.get("/today").text

    assert f'<a href="/events/{e.id}/edit" class="event-card"' in html
    assert '<dialog id="event-dialog"' in html
