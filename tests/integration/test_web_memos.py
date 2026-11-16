from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from pda.db.memo_repository import MemoRepository
from pda.db.migrate import connect
from pda.domain.memo import Memo
from pda.web.app import create_app

NOW = datetime(2026, 11, 16, 21, 0)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "pda.db"


@pytest.fixture
def client(db_path):
    return TestClient(create_app(db_path, clock=lambda: NOW))


@pytest.fixture
def memos(client, db_path):
    conn = connect(db_path)
    yield MemoRepository(conn)
    conn.close()


def add(repo, title, body="", tags=(), at=datetime(2026, 11, 15, 9, 0)):
    m = Memo(title=title, body=body, tags=tags, created_at=at)
    repo.add(m)
    return m


def appear_in_order(html: str, *texts: str) -> bool:
    positions = [html.find(t) for t in texts]
    return -1 not in positions and positions == sorted(positions)


def cards(html: str) -> str:
    """一覧のカードの部分だけ(検索欄やタグのボタンを除く)。"""
    return html[html.index('<div class="memo-grid">'):]


# --- 一覧 ------------------------------------------------------------------
def test_一覧は更新日時の新しい順のカードでタイトル本文タグ更新日時を持つ(client, memos):
    add(memos, "古いメモ", at=datetime(2026, 11, 14, 8, 0))
    add(memos, "フーリエ変換", body="畳み込み定理", tags=["数学"], at=datetime(2026, 11, 16, 8, 12))

    html = cards(client.get("/memos").text)

    assert appear_in_order(html, "フーリエ変換", "畳み込み定理", "#数学", "11/16 08:12", "古いメモ")


def test_表示しているメモの枚数を出す(client, memos):
    add(memos, "A")
    add(memos, "B")

    assert '<span id="memo-count">2</span> まい' in client.get("/memos").text  # 数字は絞り込みで書き換えるので span で囲む


def test_メモがなければその旨を表示する(client):
    assert "まだメモはありません" in client.get("/memos").text


def test_検索はタイトルか本文に含むメモだけで大文字小文字を区別しない(client, memos):
    add(memos, "SQLite の CHECK")
    add(memos, "固有値", body="線形写像で向きが変わらない sqlite とは無関係")
    add(memos, "読みたい本")

    html = cards(client.get("/memos", params={"q": "sqlite"}).text)

    assert "SQLite の CHECK" in html and "固有値" in html and "読みたい本" not in html


def test_タグで絞り込める(client, memos):
    add(memos, "エントロピー", tags=["物理", "数学"])
    add(memos, "SQLite", tags=["IT"])

    html = cards(client.get("/memos", params={"tag": "物理"}).text)

    assert "エントロピー" in html and "SQLite" not in html


def test_タグのボタンはすべてと付いているタグを多い順に出し選んだものを押下状態にする(client, memos):
    add(memos, "A", tags=["物理", "数学"])
    add(memos, "B", tags=["数学"])

    html = client.get("/memos", params={"tag": "物理"}).text
    chips = html[html.index('<div class="tag-filter">'):html.index('<div class="memo-grid">')]

    assert appear_in_order(chips, "すべて", "#数学", "#物理")
    assert 'href="/memos?tag=%E7%89%A9%E7%90%86" class="tag-chip" aria-pressed="true"' in chips
    assert 'href="/memos" class="tag-chip" aria-pressed="false"' in chips


# --- 作成 ------------------------------------------------------------------
def test_作成すると保存されて一覧へ戻る(client, memos):
    res = client.post("/memos", data={"title": "勉強会", "body": "閾値定理", "tags": "物理、#量子"}, follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/memos"
    [m] = memos.list_all()
    assert (m.title, m.body, m.tags, m.created_at, m.updated_at) == ("勉強会", "閾値定理", {"物理", "量子"}, NOW, NOW)


def test_タイトルが空なら保存せずエラーを表示し入力を残す(client, memos):
    res = client.post("/memos", data={"title": " ", "body": "閾値定理", "tags": "物理"})

    assert res.status_code == 400 and "タイトルは空にできません" in res.text
    assert "閾値定理</textarea>" in res.text and 'value="物理"' in res.text
    assert memos.list_all() == []


def test_新規作成のページがある(client):
    assert 'method="post" action="/memos"' in client.get("/memos/new").text


# --- 編集・削除 ----------------------------------------------------------------
def test_編集すると内容と更新日時が変わり作成日時は変わらない(client, memos):
    m = add(memos, "勉強会", tags=["物理"])

    res = client.post(f"/memos/{m.id}/edit", data={"title": "勉強会で聞くこと", "body": "前提条件", "tags": "量子"}, follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/memos"
    saved = memos.get(m.id)
    assert (saved.title, saved.body, saved.tags, saved.updated_at, saved.created_at) == (
        "勉強会で聞くこと", "前提条件", {"量子"}, NOW, m.created_at,
    )


def test_編集ページには今の値が入っている(client, memos):
    m = add(memos, "勉強会", body="閾値定理", tags=["物理", "量子"])

    html = client.get(f"/memos/{m.id}/edit").text

    assert f'method="post" action="/memos/{m.id}/edit"' in html
    assert 'value="勉強会"' in html and "閾値定理</textarea>" in html and 'value="物理 量子"' in html


def test_削除すると一覧へ戻り消えている(client, memos):
    m = add(memos, "勉強会")

    res = client.post(f"/memos/{m.id}/delete", follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/memos"
    assert memos.get(m.id) is None


@pytest.mark.parametrize("method, path", [("get", "/memos/999/edit"), ("post", "/memos/999/edit"), ("post", "/memos/999/delete")])
def test_存在しないメモは編集も削除もできない(client, method, path):
    res = client.get(path) if method == "get" else client.post(path, data={"title": "x", "body": "", "tags": ""})

    assert res.status_code == 404


# --- ポップアップと絞り込み(JavaScript)のための構造 ------------------------------------
def test_カードは編集ポップアップ用に今の値と検索用の文字列を持つ(client, memos):
    m = add(memos, "SQLite の CHECK", body='IS を "使う"', tags=["IT"])

    html = client.get("/memos").text

    assert (
        f'<a href="/memos/{m.id}/edit" class="memo-card" data-title="SQLite の CHECK"'
        f' data-body="IS を &#34;使う&#34;" data-tags="IT" data-delete="/memos/{m.id}/delete"'
    ) in html


def test_新規作成のボタンとポップアップと絞り込みのスクリプトがある(client):
    html = client.get("/memos").text

    assert '<a href="/memos/new" class="memo-new"' in html
    assert '<dialog id="memo-dialog"' in html and 'getElementById("memo-dialog")' in html
    assert 'getElementById("memo-search")' in html
