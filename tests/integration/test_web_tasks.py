from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from pda.db.migrate import connect
from pda.db.task_repository import TaskRepository
from pda.domain.task import Priority, Task
from pda.web.app import create_app

NOW = datetime(2026, 11, 16, 9, 0)
TODAY = NOW.date()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "pda.db"


@pytest.fixture
def client(db_path):
    return TestClient(create_app(db_path, clock=lambda: NOW))


@pytest.fixture
def tasks(client, db_path):
    """画面を通さずに DB を直接見る・準備するためのリポジトリ(create_app がスキーマを作った後に開く)。"""
    conn = connect(db_path)
    yield TaskRepository(conn)
    conn.close()


def task(title, priority=Priority.MEDIUM, due=None, done=False, created_at=datetime(2026, 11, 1, 9, 0)):
    return Task(title=title, priority=priority, due=due, done=done, created_at=created_at)


def appear_in_order(html: str, *texts: str) -> bool:
    positions = [html.find(t) for t in texts]
    return -1 not in positions and positions == sorted(positions)


# --- 一覧 ------------------------------------------------------------------
def test_トップページはToDo一覧へ移動する(client):
    res = client.get("/", follow_redirects=False)

    assert res.status_code in (302, 303, 307) and res.headers["location"] == "/tasks"


def test_一覧には未完了のタスクだけが優先度の高い順に出る(client, tasks):
    tasks.add(task("低い", Priority.LOW))
    tasks.add(task("済んだ", Priority.HIGH, done=True))
    tasks.add(task("高い", Priority.HIGH))
    tasks.add(task("中くらい", Priority.MEDIUM))

    html = client.get("/tasks").text

    assert appear_in_order(html, "高い", "中くらい", "低い")
    assert "済んだ" not in html


def test_期限を過ぎたタスクには超過の印が付き期限当日のタスクには付かない(client, tasks):
    tasks.add(task("昨日まで", due=date(2026, 11, 15)))
    tasks.add(task("今日まで", due=TODAY))

    html = client.get("/tasks").text

    assert "【超過】-昨日まで" in html
    assert "【超過】-今日まで" not in html and "今日まで" in html


# --- 追加 ------------------------------------------------------------------
def test_追加すると保存されて一覧へ戻る(client, tasks):
    res = client.post("/tasks", data={"title": "論文を読む", "priority": "HIGH", "due": "2026-11-20"}, follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/tasks"
    [saved] = tasks.list_all()
    assert (saved.title, saved.priority, saved.due, saved.done, saved.created_at) == (
        "論文を読む", Priority.HIGH, date(2026, 11, 20), False, NOW,
    )


def test_期限は空欄でもよい(client, tasks):
    client.post("/tasks", data={"title": "論文を読む", "priority": "LOW", "due": ""})

    assert tasks.list_all()[0].due is None


def test_タイトルが空なら保存せずエラーを表示し入力を残す(client, tasks):
    res = client.post("/tasks", data={"title": "  ", "priority": "LOW", "due": "2026-11-20"})

    assert res.status_code == 400
    assert "タイトルは空にできません" in res.text
    assert 'value="2026-11-20"' in res.text
    assert tasks.list_all() == []


@pytest.mark.parametrize(
    "form",
    [
        {"title": "論文を読む", "priority": "URGENT", "due": ""},
        {"title": "論文を読む", "priority": "LOW", "due": "2026-02-30"},
    ],
    ids=["存在しない優先度", "存在しない日付"],
)
def test_不正な値なら保存しない(client, tasks, form):
    res = client.post("/tasks", data=form)

    assert res.status_code == 400
    assert tasks.list_all() == []


def test_タイトルのHTMLはタグとして解釈されず文字のまま表示される(client):
    client.post("/tasks", data={"title": "<script>alert(1)</script>", "priority": "LOW", "due": ""})

    html = client.get("/tasks").text

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


# --- 完了 ------------------------------------------------------------------
def test_完了にすると一覧から消える(client, tasks):
    t = task("論文を読む")
    tasks.add(t)

    res = client.post(f"/tasks/{t.id}/done", follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/tasks"
    assert tasks.get(t.id).done is True
    assert "論文を読む" not in client.get("/tasks").text


def test_一覧の各タスクに完了ボタンがある(client, tasks):
    t = task("論文を読む")
    tasks.add(t)

    assert f'action="/tasks/{t.id}/done"' in client.get("/tasks").text


def test_存在しないタスクは完了にできない(client):
    assert client.post("/tasks/999/done").status_code == 404
