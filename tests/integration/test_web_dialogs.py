"""ポップアップ(<dialog>)の共通の決まり: 右上の × ボタンで閉じる(2026-11-16 ユーザー提案)。"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from pda.web.app import create_app

NOW = datetime(2026, 11, 16, 21, 0)


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "pda.db", clock=lambda: NOW))


def dialog_of(html: str, dialog_id: str) -> str:
    start = html.index(f'<dialog id="{dialog_id}"')
    return html[start:html.index("</dialog>", start)]


@pytest.mark.parametrize("path, dialog_id", [("/routines", "routine-dialog"), ("/today", "event-dialog"), ("/events", "event-dialog"), ("/memos", "memo-dialog"), ("/tasks", "task-edit-dialog"), ("/tasks/done", "task-edit-dialog")])
def test_ポップアップは閉じるという名前のバツボタンで閉じる(client, path, dialog_id):
    dialog = dialog_of(client.get(path).text, dialog_id)

    assert '<button type="button" class="dialog-close" aria-label="閉じる" title="閉じる" data-close>' in dialog
    assert "やめる" not in dialog
