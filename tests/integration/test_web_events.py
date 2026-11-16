from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from pda.db.event_repository import EventRepository
from pda.db.migrate import connect
from pda.domain.event import AllDayEvent, TimedEvent
from pda.web.app import create_app

NOW = datetime(2026, 11, 16, 9, 0)  # 月曜日
TODAY = NOW.date()


def d(day: int) -> date:
    return date(2026, 11, day)


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute)


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


def form(**overrides):
    base = {
        "title": "会議", "all_day": "", "start_date": "2026-11-20", "start_time": "10:00",
        "end_date": "", "end_time": "", "location": "", "memo": "",
    }
    return {**base, **overrides}


# --- 一覧 ------------------------------------------------------------------
def test_今日から先の予定を日ごとに並べ今日には今日と付き過去は出ない(client, events):
    events.add(TimedEvent(title="来週の会議", start=at(20, 10)))
    events.add(AllDayEvent(title="誕生日", start=TODAY))
    events.add(TimedEvent(title="昨日の会議", start=at(15, 10)))

    html = client.get("/events").text

    assert appear_in_order(html, "今日 11月16日(月)", "誕生日", "11月20日(金)", "来週の会議")
    assert "昨日の会議" not in html


@pytest.mark.parametrize(
    "event, label",
    [
        (AllDayEvent(title="誕生日", start=d(20)), "終日"),
        (TimedEvent(title="電話", start=at(20, 9)), "09:00"),
        (TimedEvent(title="会議", start=at(20, 10), end=at(20, 11, 30)), "10:00–11:30"),
        (TimedEvent(title="夜勤", start=at(20, 23), end=at(21, 1)), "11/20 23:00 → 11/21 01:00"),
    ],
    ids=["終日", "終了なし", "同じ日", "日をまたぐ"],
)
def test_時刻の表示(client, events, event, label):
    events.add(event)

    assert f'<span class="event-time">{label}</span>' in client.get("/events").text


def test_場所とメモを表示する(client, events):
    events.add(TimedEvent(title="会議", start=at(20, 10), location="会議室A", memo="資料を印刷"))

    html = client.get("/events").text

    assert "会議室A" in html and "資料を印刷" in html


def test_予定がなければその旨を表示する(client):
    assert "これからの予定はありません" in client.get("/events").text


def test_過去の予定は新しい日から並ぶ(client, events):
    events.add(TimedEvent(title="先週の会議", start=at(9, 10)))
    events.add(TimedEvent(title="昨日の会議", start=at(15, 10)))
    events.add(TimedEvent(title="明日の会議", start=at(17, 10)))

    html = client.get("/events/past").text

    assert appear_in_order(html, "11月15日(日)", "昨日の会議", "11月9日(月)", "先週の会議")
    assert "明日の会議" not in html


def test_過去の予定は30件ごとにページを分ける(client, events):
    for day in range(1, 16):  # 11/1〜11/15 に 2 件ずつ = 30 件
        events.add(TimedEvent(title=f"朝{day}", start=at(day, 9)))
        events.add(TimedEvent(title=f"夜{day}", start=at(day, 20)))
    events.add(TimedEvent(title="もっと前", start=datetime(2026, 10, 31, 9, 0)))

    first, second = client.get("/events/past").text, client.get("/events/past?page=2").text

    assert first.count('class="event-card"') == 30 and "もっと前" in second
    assert client.get("/events/past?page=3").status_code == 404


def test_予定の一覧と過去の予定は互いにリンクしている(client):
    assert 'href="/events/past"' in client.get("/events").text
    assert 'href="/events"' in client.get("/events/past").text


# --- 追加 ------------------------------------------------------------------
def test_時刻付きの予定を追加すると保存され一覧へ戻る(client, events):
    res = client.post("/events", data=form(end_time="11:30", location="会議室A", memo="資料"), follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/events"
    [e] = events.list_all()
    assert e == TimedEvent(id=e.id, title="会議", start=at(20, 10), end=at(20, 11, 30), location="会議室A", memo="資料")


def test_終日の予定を追加でき時刻の欄は無視する(client, events):
    client.post("/events", data=form(title="旅行", all_day="1", start_time="10:00", end_date="2026-11-22"))

    [e] = events.list_all()
    assert e == AllDayEvent(id=e.id, title="旅行", start=d(20), end=d(22))


def test_終了の時刻だけ入れたら開始と同じ日とみなす(client, events):
    client.post("/events", data=form(end_time="11:00"))

    assert events.list_all()[0].end == at(20, 11)


def test_場所とメモが空欄ならなし(client, events):
    client.post("/events", data=form(location="  ", memo=""))

    e = events.list_all()[0]
    assert (e.location, e.memo) == (None, None)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"title": " "}, "タイトルは空にできません"),
        ({"start_date": ""}, "開始日を入れてください"),
        ({"start_time": ""}, "開始の時刻を入れてください"),
        ({"end_date": "2026-11-21"}, "終了の時刻を入れてください"),
        ({"end_time": "09:00"}, "終了は開始以降にしてください"),
        ({"start_date": "2026-02-30"}, "日付が正しくありません"),
        ({"start_time": "25:00"}, "時刻が正しくありません"),
        ({"all_day": "1", "end_date": "2026-11-19"}, "終了日は開始日以降にしてください"),
    ],
    ids=["空のタイトル", "開始日なし", "開始時刻なし", "終了日だけ", "終了が開始より前", "存在しない日付", "存在しない時刻", "終日で終了日が前"],
)
def test_不正な入力は保存せずエラーを表示し入力を残す(client, events, overrides, message):
    data = form(**overrides)

    res = client.post("/events", data=data)

    assert res.status_code == 400 and message in res.text
    assert f'value="{data["title"]}"' in res.text
    assert events.list_all() == []


def test_追加のページがある(client):
    assert 'method="post" action="/events"' in client.get("/events/new").text


# --- 編集・削除 ----------------------------------------------------------------
def test_編集すると内容が変わり終日から時刻付きへの変更もできる(client, events):
    e = AllDayEvent(title="誕生日", start=d(20))
    events.add(e)

    res = client.post(f"/events/{e.id}/edit", data=form(title="誕生会", start_time="18:00", end_time="20:00"), follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/events"
    assert events.get(e.id) == TimedEvent(id=e.id, title="誕生会", start=at(20, 18), end=at(20, 20))


def test_編集ページには今の値が入っている(client, events):
    e = TimedEvent(title="会議", start=at(20, 10), end=at(20, 11), location="会議室A")
    events.add(e)

    html = client.get(f"/events/{e.id}/edit").text

    assert f'method="post" action="/events/{e.id}/edit"' in html
    for value in ('value="会議"', 'value="2026-11-20"', 'value="10:00"', 'value="11:00"', 'value="会議室A"'):
        assert value in html


def test_削除すると一覧へ戻り消えている(client, events):
    e = TimedEvent(title="会議", start=at(20, 10))
    events.add(e)

    res = client.post(f"/events/{e.id}/delete", follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/events"
    assert events.get(e.id) is None


@pytest.mark.parametrize("method, path", [("get", "/events/999/edit"), ("post", "/events/999/edit"), ("post", "/events/999/delete")])
def test_存在しない予定は編集も削除もできない(client, method, path):
    res = client.get(path) if method == "get" else client.post(path, data=form())

    assert res.status_code == 404


# --- ポップアップ(JavaScript)のための構造 ---------------------------------------------
def test_カードは編集ポップアップ用に今の値を持つ(client, events):
    e = TimedEvent(title="会議", start=at(20, 10), end=at(20, 11), location="会議室A", memo='"資料"')
    events.add(e)

    html = client.get("/events").text

    assert (
        f'<a href="/events/{e.id}/edit" class="event-card" data-title="会議" data-all-day=""'
        ' data-start-date="2026-11-20" data-start-time="10:00" data-end-date="2026-11-20" data-end-time="11:00"'
        f' data-location="会議室A" data-memo="&#34;資料&#34;" data-delete="/events/{e.id}/delete">'
    ) in html


def test_追加のボタンとポップアップがある(client):
    html = client.get("/events").text

    assert '<a href="/events/new" class="event-new"' in html
    assert '<dialog id="event-dialog"' in html and 'getElementById("event-dialog")' in html
