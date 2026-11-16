"""Web 画面(FastAPI + Jinja2。サーバー側で HTML を描画する)。

起動: uvicorn pda.web.app:create_app_from_env --factory --reload
  モジュールの読み込み時にアプリを作らないのは、テストが import しただけで
  本番の DB ファイルが作られないようにするため。

ルートの関数は同期関数(def)にしている。FastAPI はそれをスレッドプールで動かすので、
SQLite の接続は「開いた関数の中で使い切って閉じる」(sqlite3 の接続は作ったスレッドでしか使えない)。
"""

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from pda.db.migrate import connect, migrate_file
from pda.db.task_repository import TaskRepository
from pda.domain.task import incomplete_by_priority

TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")
DEFAULT_DB = Path("data/pda.db")


def _system_clock() -> datetime:
    # DB は秒単位で保存する(マイクロ秒はリポジトリが拒否する)ので、ここで落とす
    return datetime.now().replace(microsecond=0)


def create_app_from_env() -> FastAPI:
    """環境変数 PDA_DB(既定 data/pda.db)の DB で本番用のアプリを作る。"""
    db_path = Path(os.environ.get("PDA_DB", DEFAULT_DB))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_app(db_path)


def create_app(db_path: Path, *, clock: Callable[[], datetime] = _system_clock) -> FastAPI:
    """db_path の DB を最新のスキーマにしてからアプリを作る。clock は「今」を返す関数。"""
    migrate_file(db_path, now=clock())
    app = FastAPI()

    @contextmanager
    def open_db() -> Iterator:
        conn = connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    @app.get("/")
    def home():
        return RedirectResponse("/tasks", status_code=303)

    @app.get("/tasks")
    def task_list(request: Request):
        with open_db() as conn:
            items = incomplete_by_priority(TaskRepository(conn).list_all())
        return TEMPLATES.TemplateResponse(request, "tasks.html", {"tasks": items, "today": clock().date()})

    return app
