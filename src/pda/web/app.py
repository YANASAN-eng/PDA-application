"""Web 画面(FastAPI + Jinja2。サーバー側で HTML を描画する)。

起動: uvicorn pda.web.app:create_app_from_env --factory --reload
  モジュールの読み込み時にアプリを作らないのは、テストが import しただけで
  本番の DB ファイルが作られないようにするため。

ルートの関数は同期関数(def)にしている。FastAPI はそれをスレッドプールで動かすので、
SQLite の接続は「開いた関数の中で使い切って閉じる」(sqlite3 の接続は作ったスレッドでしか使えない)。
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from pda import config
from pda.db.migrate import connect, migrate_file
from pda.db.task_repository import TaskRepository
from pda.domain.task import Priority, Task, completed_by_newest, incomplete_by_priority

TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _system_clock() -> datetime:
    # DB は秒単位で保存する(マイクロ秒はリポジトリが拒否する)ので、ここで落とす
    return datetime.now().replace(microsecond=0)


def create_app_from_env() -> FastAPI:
    """設定の DB(config.db_path()。環境変数 PDA_DB で変更可)で本番用のアプリを作る。"""
    db_path = config.db_path()
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

    def render_task_list(request: Request, *, form: dict | None = None, error: str | None = None, status: int = 200):
        with open_db() as conn:
            items = incomplete_by_priority(TaskRepository(conn).list_all())
        context = {
            "tasks": items,
            "today": clock().date(),
            "priorities": list(Priority),
            "form": form or {"title": "", "priority": Priority.MEDIUM.name, "due": "", "detail": ""},
            "error": error,
        }
        return TEMPLATES.TemplateResponse(request, "tasks.html", context, status_code=status)

    @app.get("/tasks")
    def task_list(request: Request):
        return render_task_list(request)

    @app.post("/tasks")
    def task_create(
        request: Request,
        title: str = Form(""),
        priority: str = Form(""),
        due: str = Form(""),
        detail: str = Form(""),
    ):
        form = {"title": title, "priority": priority, "due": due, "detail": detail}
        try:
            task = Task(
                title=title,
                priority=_parse_priority(priority),
                due=_parse_date(due),
                detail=detail,
                created_at=clock(),
            )
        except ValueError as e:
            return render_task_list(request, form=form, error=str(e), status=400)
        with open_db() as conn:
            TaskRepository(conn).add(task)
        return RedirectResponse("/tasks", status_code=303)

    @app.get("/tasks/done")
    def task_done_list(request: Request):
        with open_db() as conn:
            items = completed_by_newest(TaskRepository(conn).list_all())
        return TEMPLATES.TemplateResponse(request, "tasks_done.html", {"tasks": items})

    def set_done(task_id: int, done: bool) -> None:
        with open_db() as conn:
            repo = TaskRepository(conn)
            task = repo.get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="タスクが見つかりません")
            task.done = done
            repo.update(task)

    @app.post("/tasks/{task_id}/done")
    def task_done(task_id: int):
        set_done(task_id, True)
        return RedirectResponse("/tasks", status_code=303)

    @app.post("/tasks/{task_id}/undone")
    def task_undone(task_id: int):
        set_done(task_id, False)
        return RedirectResponse("/tasks/done", status_code=303)

    @app.post("/tasks/{task_id}/delete")
    def task_delete(task_id: int):
        """削除して、そのタスクが出ていたページ(未完了の一覧 / 完了済み)へ戻る。

        戻り先はフォームから受け取らずサーバーで決める(任意の URL へ飛ばされないように)。
        """
        with open_db() as conn:
            repo = TaskRepository(conn)
            task = repo.get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="タスクが見つかりません")
            repo.delete(task_id)
        return RedirectResponse("/tasks/done" if task.done else "/tasks", status_code=303)

    return app


def _parse_priority(name: str) -> Priority:
    try:
        return Priority[name]
    except KeyError:
        raise ValueError("優先度が正しくありません") from None


def _parse_date(text: str) -> date | None:
    """空欄なら None。'YYYY-MM-DD' として読めなければ ValueError。"""
    if not text.strip():
        return None
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise ValueError("日付が正しくありません(YYYY-MM-DD)") from None
