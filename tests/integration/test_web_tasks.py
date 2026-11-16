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


def task(title, priority=Priority.MEDIUM, due=None, done=False, created_at=datetime(2026, 11, 1, 9, 0), detail=""):
    return Task(title=title, priority=priority, due=due, done=done, created_at=created_at, detail=detail)


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


# --- 完了済み ----------------------------------------------------------------
def test_完了済みページには完了したタスクだけが作成日時の新しい順に出る(client, tasks):
    tasks.add(task("古い", done=True, created_at=datetime(2026, 11, 1, 9, 0)))
    tasks.add(task("まだ", done=False))
    tasks.add(task("新しい", done=True, created_at=datetime(2026, 11, 2, 9, 0)))

    html = client.get("/tasks/done").text

    assert appear_in_order(html, "新しい", "古い")
    assert "まだ" not in html


def test_完了済みのタスクは期限を過ぎていても超過の印が付かない(client, tasks):
    tasks.add(task("済んだ", due=date(2026, 11, 1), done=True))

    assert "【超過】" not in client.get("/tasks/done").text


def test_未完了に戻すと完了済みページから消えて一覧に戻る(client, tasks):
    t = task("論文を読む", done=True)
    tasks.add(t)

    res = client.post(f"/tasks/{t.id}/undone", follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/tasks/done"
    assert tasks.get(t.id).done is False
    assert "論文を読む" in client.get("/tasks").text


def test_完了済みページの各タスクに未完了に戻すボタンがある(client, tasks):
    t = task("論文を読む", done=True)
    tasks.add(t)

    assert f'action="/tasks/{t.id}/undone"' in client.get("/tasks/done").text


def test_存在しないタスクは未完了に戻せない(client):
    assert client.post("/tasks/999/undone").status_code == 404


def test_一覧と完了済みページは互いにリンクしている(client):
    assert 'href="/tasks/done"' in client.get("/tasks").text
    assert 'href="/tasks"' in client.get("/tasks/done").text


# --- 削除(ブラウザ標準の確認ポップアップ) ----------------------------------------
@pytest.mark.parametrize("done, page", [(False, "/tasks"), (True, "/tasks/done")], ids=["未完了の一覧", "完了済みページ"])
def test_一覧の削除ボタンは確認の文言付きで削除を送る(client, tasks, done, page):
    t = task("牛乳を買う", done=done)
    tasks.add(t)

    html = client.get(page).text

    assert f'method="post" action="/tasks/{t.id}/delete" data-confirm="「牛乳を買う」を削除しますか?"' in html


def test_確認の文言に入るタイトルは属性の中でエスケープされる(client, tasks):
    tasks.add(task('a"b<c>'))

    assert 'data-confirm="「a&#34;b&lt;c&gt;」を削除しますか?"' in client.get("/tasks").text


@pytest.mark.parametrize("page", ["/tasks", "/tasks/done"])
def test_各ページに確認ポップアップの共通スクリプトがある(client, page):
    assert "dataset.confirm" in client.get(page).text


@pytest.mark.parametrize("done, back", [(False, "/tasks"), (True, "/tasks/done")], ids=["未完了", "完了済み"])
def test_削除すると消えて元のページへ戻る(client, tasks, done, back):
    t = task("論文を読む", done=done)
    tasks.add(t)

    res = client.post(f"/tasks/{t.id}/delete", follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == back
    assert tasks.get(t.id) is None


def test_存在しないタスクは削除できない(client):
    assert client.post("/tasks/999/delete").status_code == 404


def test_削除の確認ページはもうない(client, tasks):
    t = task("論文を読む")
    tasks.add(t)

    assert client.get(f"/tasks/{t.id}/delete").status_code in (404, 405)
    assert tasks.get(t.id) is not None


# --- 詳細 ------------------------------------------------------------------
def test_詳細を付けて追加できる(client, tasks):
    client.post("/tasks", data={"title": "牛乳を買う", "priority": "LOW", "due": "", "detail": "シチュー用"})

    assert tasks.list_all()[0].detail == "シチュー用"


def test_詳細の欄を送らなくても追加できる(client, tasks):
    client.post("/tasks", data={"title": "牛乳を買う", "priority": "LOW", "due": ""})

    assert tasks.list_all()[0].detail == ""


def test_追加フォームに詳細の入力欄がある(client):
    assert '<textarea name="detail"' in client.get("/tasks").text


def test_エラーのときも入力した詳細は残る(client):
    res = client.post("/tasks", data={"title": " ", "priority": "LOW", "due": "", "detail": "シチュー用"})

    assert "シチュー用" in res.text


@pytest.mark.parametrize("done, page", [(False, "/tasks"), (True, "/tasks/done")], ids=["未完了の一覧", "完了済みページ"])
def test_一覧に詳細が表示される(client, tasks, done, page):
    tasks.add(task("牛乳を買う", done=done, detail="シチュー用"))

    assert "シチュー用" in client.get(page).text


# --- 編集 ------------------------------------------------------------------
def test_編集ページには今の値が入ったフォームがある(client, tasks):
    t = task("牛乳を買う", priority=Priority.LOW, due=date(2026, 11, 20), detail="シチュー用")
    tasks.add(t)

    html = client.get(f"/tasks/{t.id}/edit").text

    assert f'method="post" action="/tasks/{t.id}/edit"' in html
    assert 'value="牛乳を買う"' in html and 'value="2026-11-20"' in html and "シチュー用</textarea>" in html
    assert '<option value="LOW" selected>' in html


@pytest.mark.parametrize("done, back", [(False, "/tasks"), (True, "/tasks/done")], ids=["未完了", "完了済み"])
def test_編集を保存すると元の一覧へ戻り作成日時と完了は変わらない(client, tasks, done, back):
    t = task("牛乳を買う", done=done)
    tasks.add(t)

    res = client.post(
        f"/tasks/{t.id}/edit",
        data={"title": "牛乳を 2 本買う", "priority": "HIGH", "due": "2026-11-20", "detail": "シチュー用"},
        follow_redirects=False,
    )

    assert res.status_code == 303 and res.headers["location"] == back
    saved = tasks.get(t.id)
    assert (saved.title, saved.priority, saved.due, saved.detail) == ("牛乳を 2 本買う", Priority.HIGH, date(2026, 11, 20), "シチュー用")
    assert (saved.created_at, saved.done) == (t.created_at, done)


@pytest.mark.parametrize(
    "form, message",
    [
        ({"title": " ", "priority": "LOW", "due": "", "detail": "メモ"}, "タイトルは空にできません"),
        ({"title": "牛乳", "priority": "URGENT", "due": "", "detail": ""}, "優先度が正しくありません"),
        ({"title": "牛乳", "priority": "LOW", "due": "2026-02-30", "detail": ""}, "日付が正しくありません"),
    ],
    ids=["空のタイトル", "存在しない優先度", "存在しない日付"],
)
def test_不正な編集は保存せずエラーを表示し入力を残す(client, tasks, form, message):
    t = task("牛乳を買う")
    tasks.add(t)

    res = client.post(f"/tasks/{t.id}/edit", data=form)

    assert res.status_code == 400 and message in res.text
    assert f'value="{form["title"]}"' in res.text
    assert tasks.get(t.id).title == "牛乳を買う"


@pytest.mark.parametrize("method", ["get", "post"])
def test_存在しないタスクは編集できない(client, method):
    data = {"title": "x", "priority": "LOW", "due": "", "detail": ""} if method == "post" else None
    res = client.get("/tasks/999/edit") if method == "get" else client.post("/tasks/999/edit", data=data)

    assert res.status_code == 404


def test_一覧の編集リンクは今の値をポップアップ用に持つ(client, tasks):
    t = task("牛乳を買う", priority=Priority.LOW, due=date(2026, 11, 20), detail='シチュー用"です"')
    tasks.add(t)

    html = client.get("/tasks").text

    assert (
        f'<a href="/tasks/{t.id}/edit" class="task-edit" data-title="牛乳を買う" data-priority="LOW"'
        f' data-due="2026-11-20" data-detail="シチュー用&#34;です&#34;">編集</a>'
    ) in html
    assert '<dialog id="task-edit-dialog"' in html and 'getElementById("task-edit-dialog")' in html
