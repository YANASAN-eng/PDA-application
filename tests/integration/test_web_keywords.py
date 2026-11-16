from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from pda.db.keyword_repository import KeywordRepository
from pda.db.migrate import connect
from pda.domain.keyword import Keyword, KeywordGroup
from pda.web.app import create_app

NOW = datetime(2026, 11, 16, 9, 0)
IT, MP = KeywordGroup.IT, KeywordGroup.MATH_PHYSICS


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "pda.db"


@pytest.fixture
def client(db_path):
    return TestClient(create_app(db_path, clock=lambda: NOW))


@pytest.fixture
def keywords(client, db_path):
    """画面を通さずに DB を直接見る・準備する(初期データは消して空から始める)。"""
    conn = connect(db_path)
    conn.execute("DELETE FROM keywords")
    yield KeywordRepository(conn)
    conn.close()


def appear_in_order(html: str, *texts: str) -> bool:
    positions = [html.find(t) for t in texts]
    return -1 not in positions and positions == sorted(positions)


# --- 一覧 ------------------------------------------------------------------
def test_グループごとに物理数学からITの順で登録した順に並ぶ(client, keywords):
    for group, word in [(IT, "GPU"), (MP, "量子"), (IT, "AI"), (MP, "トポロジー")]:
        keywords.add(Keyword(group=group, word=word))

    html = client.get("/keywords").text
    listing = html.split("</form>", 1)[1]  # 追加フォームの選択肢にもグループ名があるので、一覧の部分だけを見る

    assert appear_in_order(listing, "物理・数学", "量子", "トポロジー", "IT", "GPU", "AI")


def test_どの画面からもキーワードの画面へ行ける(client):
    assert 'href="/keywords"' in client.get("/tasks").text


# --- 追加 ------------------------------------------------------------------
def test_追加すると保存されてキーワードの画面へ戻る(client, keywords):
    res = client.post("/keywords", data={"group": "MATH_PHYSICS", "word": "演算子"}, follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/keywords"
    assert [(k.group, k.word) for k in keywords.list_all()] == [(MP, "演算子")]


def test_重複した語はエラーを表示して入力を残す(client, keywords):
    keywords.add(Keyword(group=IT, word="AI"))

    res = client.post("/keywords", data={"group": "IT", "word": "ai"})

    assert res.status_code == 400
    assert "登録済み" in res.text and 'value="ai"' in res.text
    assert len(keywords.list_all()) == 1


@pytest.mark.parametrize(
    "form",
    [{"group": "IT", "word": "  "}, {"group": "BIOLOGY", "word": "細胞"}],
    ids=["空の語", "存在しないグループ"],
)
def test_不正な入力は保存しない(client, keywords, form):
    res = client.post("/keywords", data=form)

    assert res.status_code == 400
    assert keywords.list_all() == []


# --- 削除 ------------------------------------------------------------------
def test_各キーワードに確認付きの削除ボタンがある(client, keywords):
    k = Keyword(group=IT, word="AI")
    keywords.add(k)

    html = client.get("/keywords").text

    assert f'method="post" action="/keywords/{k.id}/delete" data-confirm="「AI」を削除しますか?"' in html


def test_削除するとキーワードの画面へ戻り消えている(client, keywords):
    k = Keyword(group=IT, word="AI")
    keywords.add(k)

    res = client.post(f"/keywords/{k.id}/delete", follow_redirects=False)

    assert res.status_code == 303 and res.headers["location"] == "/keywords"
    assert keywords.list_all() == []


def test_存在しないキーワードは削除できない(client):
    assert client.post("/keywords/999/delete").status_code == 404
