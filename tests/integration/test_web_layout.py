"""全画面に共通の枠組み(docs/design/ のモックアップから読み取った決まり)。"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from pda.db.migrate import connect
from pda.db.task_repository import TaskRepository
from pda.domain.task import Priority, Task
from pda.web.app import create_app

NOW = datetime(2026, 11, 16, 9, 0)


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "pda.db"
    c = TestClient(create_app(db_path, clock=lambda: NOW))
    conn = connect(db_path)
    TaskRepository(conn).add(Task(title="牛乳を買う", priority=Priority.LOW, created_at=NOW))  # id=1(編集ページ用)
    conn.close()
    return c


PAGES = {
    "/today": "今日",
    "/tasks": "ToDo", "/tasks/done": "ToDo", "/tasks/1/edit": "ToDo",
    "/events": "予定", "/events/past": "予定", "/events/new": "予定",
    "/memos": "メモ", "/memos/new": "メモ",
    "/news": "ニュース", "/keywords": "ニュース",
}
HREF = {"今日": "/today", "ToDo": "/tasks", "予定": "/events", "メモ": "/memos", "ニュース": "/news"}


@pytest.mark.parametrize("path", PAGES)
def test_どの画面にも画面下のタブバーがある(client, path):
    html = client.get(path).text

    assert '<nav class="tabbar" aria-label="メイン">' in html
    for href in ("/today", "/tasks", "/events", "/memos", "/news"):
        assert f'href="{href}"' in html


@pytest.mark.parametrize("path, current", PAGES.items())
def test_今いる画面のタブが強調される(client, path, current):
    html = client.get(path).text
    tabbar = html[html.index('<nav class="tabbar"'):]

    assert tabbar.count('aria-current="page"') == 1
    assert f'<a href="{HREF[current]}" class="tab" aria-current="page">' in tabbar


def test_準備中のタブはもうない(client):
    # 2026-11-16 に「今日」ができて、タブバーの 5 つの画面がすべて揃った
    assert 'aria-disabled="true"' not in client.get("/tasks").text


def test_デザインの色と書体を使う(client):
    html = client.get("/tasks").text

    assert "--accent: #B4501C" in html and "--bg: #FFFAEC" in html
    assert "Zen+Maru+Gothic" in html


@pytest.mark.parametrize("path, label", [("/today", "今日"), ("/tasks", "ToDo"), ("/events", "予定"), ("/memos", "メモ"), ("/news", "ニュース")])
def test_画面の見出しはタブの名前と同じ表記(client, path, label):
    # 2026-11-16: タブは「メモ」なのに見出しが「めも」で統一感がなかった(ユーザー指摘)
    assert f"<h1>{label}</h1>" in client.get(path).text
