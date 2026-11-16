from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from pda.db.migrate import connect
from pda.db.routine_repository import RoutineRepository
from pda.domain.routine import Routine
from pda.web.app import create_app

NOW = datetime(2026, 11, 16, 9, 0)  # 月曜日
TODAY = NOW.date()
MON, TUE, WED, FRI, SAT = 0, 1, 2, 4, 5


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "pda.db"


@pytest.fixture
def client(db_path):
    return TestClient(create_app(db_path, clock=lambda: NOW))


@pytest.fixture
def routines(client, db_path):
    conn = connect(db_path)
    yield RoutineRepository(conn)
    conn.close()


def add(repo, title, weekdays=range(7)):
    r = Routine(title=title, weekdays=weekdays)
    repo.add(r)
    return r


def appear_in_order(html: str, *texts: str) -> bool:
    positions = [html.find(t) for t in texts]
    return -1 not in positions and positions == sorted(positions)


def section(html: str) -> str:
    """今日の画面の日課の部分。"""
    start = html.index('<section class="routines"')
    return html[start:html.index("</section>", start)]


# --- 今日の画面 ----------------------------------------------------------------
def test_今日の画面に今日の曜日の日課を登録した順に予定より上に出す(client, routines):
    add(routines, "英単語")
    add(routines, "部屋の掃除", weekdays=[SAT])
    add(routines, "筋トレ", weekdays=[MON, WED, FRI])

    html = client.get("/today").text
    part = section(html)

    assert appear_in_order(part, "英単語", "筋トレ") and "部屋の掃除" not in part
    assert html.index('<section class="routines"') < html.index("今日の予定")


def test_進み具合と終えた日課の印を出す(client, routines):
    done = add(routines, "英単語")
    add(routines, "筋トレ")
    routines.check(done.id, TODAY)

    part = section(client.get("/today").text)

    assert "1 / 2" in part
    assert f'<li class="routine done">' in part and f'action="/routines/{done.id}/uncheck"' in part


def test_チェックすると今日の記録が付き今日の画面へ戻る(client, routines):
    r = add(routines, "英単語")

    res = client.post(f"/routines/{r.id}/check", follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/today"
    assert routines.checked_on(TODAY) == {r.id}


def test_チェックを外せる(client, routines):
    r = add(routines, "英単語")
    routines.check(r.id, TODAY)

    client.post(f"/routines/{r.id}/uncheck")

    assert routines.checked_on(TODAY) == set()


def test_チェックの日付はブラウザから受け取らずサーバーの今日にする(client, routines):
    r = add(routines, "英単語")

    client.post(f"/routines/{r.id}/check", data={"day": "2020-01-01"})

    assert routines.checked_on(TODAY) == {r.id} and routines.checked_on(date(2020, 1, 1)) == set()


def test_今日の日課がなければその旨と管理画面へのリンクを出す(client):
    part = section(client.get("/today").text)

    assert "今日の日課はありません" in part and 'href="/routines"' in part


@pytest.mark.parametrize("op", ["check", "uncheck"])
def test_存在しない日課はチェックできない(client, op):
    assert client.post(f"/routines/999/{op}").status_code == 404


# --- 管理画面 ------------------------------------------------------------------
def test_管理画面は日課と曜日の表示を登録した順に並べる(client, routines):
    add(routines, "英単語")
    add(routines, "筋トレ", weekdays=[MON, WED, FRI])

    listing = client.get("/routines").text.split('<ul class="items">', 1)[1]  # 説明文の「毎日」を除く

    assert appear_in_order(listing, "英単語", "毎日", "筋トレ", "月・水・金")


def test_追加フォームは最初は全曜日にチェックが入っている(client):
    html = client.get("/routines").text
    form = html[html.index('<form method="post" action="/routines"'):]
    form = form[:form.index("</form>")]

    assert form.count('name="weekdays"') == 7 and form.count(" checked>") == 7


def test_追加すると保存されて管理画面へ戻る(client, routines):
    res = client.post("/routines", data={"title": "筋トレ", "weekdays": ["0", "2", "4"]}, follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/routines"
    [r] = routines.list_all()
    assert (r.title, r.weekdays) == ("筋トレ", {MON, WED, FRI})


@pytest.mark.parametrize(
    "data, message",
    [
        ({"title": " ", "weekdays": ["0"]}, "タイトルは空にできません"),
        ({"title": "筋トレ"}, "曜日を 1 つ以上選んでください"),
        ({"title": "筋トレ", "weekdays": ["7"]}, "曜日"),
        ({"title": "筋トレ", "weekdays": ["月"]}, "曜日"),
    ],
    ids=["空のタイトル", "曜日なし", "範囲外の曜日", "数字でない曜日"],
)
def test_不正な入力は保存せずエラーを表示する(client, routines, data, message):
    res = client.post("/routines", data=data)

    assert res.status_code == 400 and message in res.text
    assert routines.list_all() == []


def test_編集するとタイトルと曜日が変わる(client, routines):
    r = add(routines, "筋トレ", weekdays=[MON])

    res = client.post(f"/routines/{r.id}/edit", data={"title": "ジョギング", "weekdays": ["1"]}, follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/routines"
    assert routines.get(r.id) == Routine(id=r.id, title="ジョギング", weekdays=[TUE])


def test_編集ページには今の値が入っている(client, routines):
    r = add(routines, "筋トレ", weekdays=[MON, WED])

    html = client.get(f"/routines/{r.id}/edit").text

    assert f'method="post" action="/routines/{r.id}/edit"' in html and 'value="筋トレ"' in html
    assert html.count(" checked>") == 2  # スクリプトの box.checked は数えない


def test_削除すると管理画面へ戻り消えている(client, routines):
    r = add(routines, "英単語")

    res = client.post(f"/routines/{r.id}/delete", follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/routines"
    assert routines.get(r.id) is None


@pytest.mark.parametrize("method, path", [("get", "/routines/999/edit"), ("post", "/routines/999/edit"), ("post", "/routines/999/delete")])
def test_存在しない日課は編集も削除もできない(client, method, path):
    res = client.get(path) if method == "get" else client.post(path, data={"title": "x", "weekdays": ["0"]})

    assert res.status_code == 404


def test_一覧の日課は編集ポップアップ用に今の値を持ち確認付きの削除ボタンがある(client, routines):
    r = add(routines, "筋トレ", weekdays=[MON, WED])

    html = client.get("/routines").text

    assert f'<a href="/routines/{r.id}/edit" class="routine-edit" data-title="筋トレ" data-weekdays="0 2">編集</a>' in html
    assert f'action="/routines/{r.id}/delete" data-confirm="「筋トレ」を削除しますか?"' in html
    assert '<dialog id="routine-dialog"' in html


def test_管理画面では今日のタブを強調し今日の画面へ戻れる(client):
    html = client.get("/routines").text

    assert '<a href="/today" class="tab" aria-current="page">' in html
    assert 'href="/today" class="pill-link"' in html
