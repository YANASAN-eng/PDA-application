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
    "/tasks": "ToDo", "/tasks/done": "ToDo", "/tasks/1/edit": "ToDo",
    "/memos": "メモ", "/memos/new": "メモ",
    "/news": "ニュース", "/keywords": "ニュース",
}
HREF = {"ToDo": "/tasks", "メモ": "/memos", "ニュース": "/news"}


@pytest.mark.parametrize("path", PAGES)
def test_どの画面にも画面下のタブバーがある(client, path):
    html = client.get(path).text

    assert '<nav class="tabbar" aria-label="メイン">' in html
    assert 'href="/tasks"' in html and 'href="/memos"' in html and 'href="/news"' in html


@pytest.mark.parametrize("path, current", PAGES.items())
def test_今いる画面のタブが強調される(client, path, current):
    html = client.get(path).text
    tabbar = html[html.index('<nav class="tabbar"'):]

    assert tabbar.count('aria-current="page"') == 1
    assert f'<a href="{HREF[current]}" class="tab" aria-current="page">' in tabbar


@pytest.mark.parametrize("label", ["今日", "予定"])
def test_まだない画面のタブは押せない表示(client, label):
    html = client.get("/tasks").text

    assert f'<span class="tab" aria-disabled="true" title="準備中">' in html
    tabbar = html[html.index('<nav class="tabbar"'):]
    assert label in tabbar


def test_デザインの色と書体を使う(client):
    html = client.get("/tasks").text

    assert "--accent: #B4501C" in html and "--bg: #FFFAEC" in html
    assert "Zen+Maru+Gothic" in html


@pytest.mark.parametrize("path, label", [("/tasks", "ToDo"), ("/memos", "メモ"), ("/news", "ニュース")])
def test_画面の見出しはタブの名前と同じ表記(client, path, label):
    # 2026-11-16: タブは「メモ」なのに見出しが「めも」で統一感がなかった(ユーザー指摘)
    assert f"<h1>{label}</h1>" in client.get(path).text
