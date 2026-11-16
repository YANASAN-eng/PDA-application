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
from datetime import time as time_of_day
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from pda import config
from pda.db.article_repository import ArticleRepository
from pda.db.event_repository import EventRepository
from pda.db.keyword_repository import KeywordRepository
from pda.db.migrate import connect, migrate_file
from pda.db.memo_repository import MemoRepository
from pda.db.task_repository import TaskRepository
from pda.domain.event import AllDayEvent, Event, TimedEvent, events_on, past_by_day, upcoming_by_day
from pda.domain.keyword import Keyword, KeywordGroup, as_groups
from pda.domain.memo import Memo, memos_by_updated, parse_tag_input, search_memos, tag_counts, with_tag
from pda.domain.task import Priority, Task, completed_by_newest, incomplete_by_priority
from pda.news.filter import matched_groups, news_by_day
from pda.web.pagination import paginate

EVENTS_PER_PAGE = 30  # 過去の予定
NEWS_PER_PAGE = 30  # 1 日に要約する件数の上限と同じ(だいたい 1 ページ = 1 日)
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
        return RedirectResponse("/today", status_code=303)  # 最初の画面は「今日」(2026-11-16 決定)

    @app.get("/today")
    def today_page(request: Request):
        """今日の予定(2026-11-16 決定: 今日の画面には予定だけを出す)。"""
        today = clock().date()
        with open_db() as conn:
            items = events_on(today, EventRepository(conn).list_all())
        return TEMPLATES.TemplateResponse(request, "today.html", {"today": today, "events": items})

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

    def task_or_404(conn, task_id: int) -> Task:
        task = TaskRepository(conn).get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="タスクが見つかりません")
        return task

    def render_task_edit(request: Request, task: Task, *, form: dict, error: str | None = None, status: int = 200):
        context = {
            "task_id": task.id,
            "back": "/tasks/done" if task.done else "/tasks",
            "priorities": list(Priority),
            "form": form,
            "error": error,
        }
        return TEMPLATES.TemplateResponse(request, "task_edit.html", context, status_code=status)

    @app.get("/tasks/{task_id}/edit")
    def task_edit_page(request: Request, task_id: int):
        """編集ページ(ポップアップが使えないときの代わり)。GET は何も変えない。"""
        with open_db() as conn:
            task = task_or_404(conn, task_id)
        form = {
            "title": task.title,
            "priority": task.priority.name,
            "due": task.due.isoformat() if task.due else "",
            "detail": task.detail,
        }
        return render_task_edit(request, task, form=form)

    @app.post("/tasks/{task_id}/edit")
    def task_edit(
        request: Request,
        task_id: int,
        title: str = Form(""),
        priority: str = Form(""),
        due: str = Form(""),
        detail: str = Form(""),
    ):
        form = {"title": title, "priority": priority, "due": due, "detail": detail}
        with open_db() as conn:
            task = task_or_404(conn, task_id)
            try:
                task.edit(title=title, priority=_parse_priority(priority), due=_parse_date(due), detail=detail)
            except ValueError as e:
                return render_task_edit(request, task, form=form, error=str(e), status=400)
            TaskRepository(conn).update(task)
        return RedirectResponse("/tasks/done" if task.done else "/tasks", status_code=303)

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

    # --- キーワード(ニュースの絞り込み) ---------------------------------------
    def render_keywords(request: Request, *, form: dict | None = None, error: str | None = None, status: int = 200):
        with open_db() as conn:
            all_keywords = KeywordRepository(conn).list_all()
        # グループの表示順は Enum の定義順。グループの中は登録した順
        by_group = [(g, [k for k in all_keywords if k.group == g]) for g in KeywordGroup]
        context = {
            "by_group": by_group,
            "groups": list(KeywordGroup),
            "form": form or {"group": KeywordGroup.MATH_PHYSICS.name, "word": ""},
            "error": error,
        }
        return TEMPLATES.TemplateResponse(request, "keywords.html", context, status_code=status)

    @app.get("/keywords")
    def keyword_list(request: Request):
        return render_keywords(request)

    @app.post("/keywords")
    def keyword_create(request: Request, group: str = Form(""), word: str = Form("")):
        form = {"group": group, "word": word}
        try:
            keyword = Keyword(group=_parse_group(group), word=word)
            with open_db() as conn:
                KeywordRepository(conn).add(keyword)  # 重複なら DuplicateKeywordError(ValueError)
        except ValueError as e:
            return render_keywords(request, form=form, error=str(e), status=400)
        return RedirectResponse("/keywords", status_code=303)

    @app.post("/keywords/{keyword_id}/delete")
    def keyword_delete(keyword_id: int):
        with open_db() as conn:
            try:
                KeywordRepository(conn).delete(keyword_id)
            except LookupError:
                raise HTTPException(status_code=404, detail="キーワードが見つかりません") from None
        return RedirectResponse("/keywords", status_code=303)

    # --- 予定 ----------------------------------------------------------------------
    def event_or_404(conn, event_id: int) -> Event:
        event = EventRepository(conn).get(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="予定が見つかりません")
        return event

    @app.get("/events")
    def event_list(request: Request):
        today = clock().date()
        with open_db() as conn:
            days = upcoming_by_day(EventRepository(conn).list_all(), today)
        return TEMPLATES.TemplateResponse(request, "events.html", {"days": days, "today": today, "past": False, "pager": None})

    @app.get("/events/past")
    def event_past(request: Request, page: int = 1):
        today = clock().date()
        with open_db() as conn:
            days = past_by_day(EventRepository(conn).list_all(), today)
        flat = [(day, e) for day, items in days for e in items]
        try:
            current = paginate(flat, page=page, per_page=EVENTS_PER_PAGE)
        except ValueError:
            raise HTTPException(status_code=404, detail="ページが見つかりません") from None
        sections: list[tuple] = []
        for day, e in current.items:  # ページの中で日ごとにまとめ直す
            if not sections or sections[-1][0] != day:
                sections.append((day, []))
            sections[-1][1].append(e)
        return TEMPLATES.TemplateResponse(request, "events.html", {"days": sections, "today": today, "past": True, "pager": current})

    def render_event_edit(request: Request, *, action: str, form: dict, delete_action: str | None = None,
                          error: str | None = None, status: int = 200):
        context = {"action": action, "form": form, "delete_action": delete_action, "error": error}
        return TEMPLATES.TemplateResponse(request, "event_edit.html", context, status_code=status)

    @app.get("/events/new")
    def event_new_page(request: Request):
        """追加のページ(ポップアップが使えないときの代わり)。"""
        return render_event_edit(request, action="/events", form=_event_form_from({}))

    @app.post("/events")
    def event_create(request: Request, form: dict = Depends(_event_form_fields)):
        try:
            event = _parse_event(form)
        except ValueError as e:
            return render_event_edit(request, action="/events", form=form, error=str(e), status=400)
        with open_db() as conn:
            EventRepository(conn).add(event)
        return RedirectResponse("/events", status_code=303)

    @app.get("/events/{event_id}/edit")
    def event_edit_page(request: Request, event_id: int):
        """編集ページ(ポップアップが使えないときの代わり)。GET は何も変えない。"""
        with open_db() as conn:
            event = event_or_404(conn, event_id)
        return render_event_edit(request, action=f"/events/{event_id}/edit", form=event_form(event),
                                 delete_action=f"/events/{event_id}/delete")

    @app.post("/events/{event_id}/edit")
    def event_edit(request: Request, event_id: int, form: dict = Depends(_event_form_fields)):
        with open_db() as conn:
            event_or_404(conn, event_id)
            try:
                event = _parse_event(form)  # 終日 ⇄ 時刻付きの種類の変更もあるので作り直す
            except ValueError as e:
                return render_event_edit(request, action=f"/events/{event_id}/edit", form=form,
                                         delete_action=f"/events/{event_id}/delete", error=str(e), status=400)
            event.id = event_id
            EventRepository(conn).update(event)
        return RedirectResponse("/events", status_code=303)

    @app.post("/events/{event_id}/delete")
    def event_delete(event_id: int):
        with open_db() as conn:
            try:
                EventRepository(conn).delete(event_id)
            except LookupError:
                raise HTTPException(status_code=404, detail="予定が見つかりません") from None
        return RedirectResponse("/events", status_code=303)

    # --- メモ ----------------------------------------------------------------------
    def memo_or_404(conn, memo_id: int) -> Memo:
        memo = MemoRepository(conn).get(memo_id)
        if memo is None:
            raise HTTPException(status_code=404, detail="メモが見つかりません")
        return memo

    @app.get("/memos")
    def memo_list(request: Request, q: str = "", tag: str = ""):
        with open_db() as conn:
            all_memos = MemoRepository(conn).list_all()
        shown = with_tag(all_memos, tag) if tag else all_memos
        shown = memos_by_updated(search_memos(shown, q))
        context = {"memos": shown, "chips": tag_counts(all_memos), "tag": tag, "q": q}
        return TEMPLATES.TemplateResponse(request, "memos.html", context)

    def render_memo_edit(request: Request, *, action: str, form: dict, delete_action: str | None = None,
                         error: str | None = None, status: int = 200):
        context = {"action": action, "form": form, "delete_action": delete_action, "error": error}
        return TEMPLATES.TemplateResponse(request, "memo_edit.html", context, status_code=status)

    @app.get("/memos/new")
    def memo_new_page(request: Request):
        """新規作成のページ(ポップアップが使えないときの代わり)。"""
        return render_memo_edit(request, action="/memos", form={"title": "", "body": "", "tags": ""})

    @app.post("/memos")
    def memo_create(request: Request, title: str = Form(""), body: str = Form(""), tags: str = Form("")):
        form = {"title": title, "body": body, "tags": tags}
        try:
            memo = Memo(title=title, body=body, tags=parse_tag_input(tags), created_at=clock())
        except ValueError as e:
            return render_memo_edit(request, action="/memos", form=form, error=str(e), status=400)
        with open_db() as conn:
            MemoRepository(conn).add(memo)
        return RedirectResponse("/memos", status_code=303)

    @app.get("/memos/{memo_id}/edit")
    def memo_edit_page(request: Request, memo_id: int):
        """編集ページ(ポップアップが使えないときの代わり)。GET は何も変えない。"""
        with open_db() as conn:
            memo = memo_or_404(conn, memo_id)
        form = {"title": memo.title, "body": memo.body, "tags": " ".join(sorted(memo.tags))}
        return render_memo_edit(request, action=f"/memos/{memo_id}/edit", form=form, delete_action=f"/memos/{memo_id}/delete")

    @app.post("/memos/{memo_id}/edit")
    def memo_edit(request: Request, memo_id: int, title: str = Form(""), body: str = Form(""), tags: str = Form("")):
        form = {"title": title, "body": body, "tags": tags}
        with open_db() as conn:
            memo = memo_or_404(conn, memo_id)
            try:
                memo.edit(title=title, body=body, tags=parse_tag_input(tags), now=clock())
            except ValueError as e:
                return render_memo_edit(request, action=f"/memos/{memo_id}/edit", form=form,
                                        delete_action=f"/memos/{memo_id}/delete", error=str(e), status=400)
            MemoRepository(conn).update(memo)
        return RedirectResponse("/memos", status_code=303)

    @app.post("/memos/{memo_id}/delete")
    def memo_delete(memo_id: int):
        with open_db() as conn:
            try:
                MemoRepository(conn).delete(memo_id)
            except LookupError:
                raise HTTPException(status_code=404, detail="メモが見つかりません") from None
        return RedirectResponse("/memos", status_code=303)

    # --- ニュース ------------------------------------------------------------------
    @app.get("/news")
    def news_list(request: Request, page: int = 1):
        with open_db() as conn:
            groups = as_groups(KeywordRepository(conn).list_all())
            days = news_by_day(ArticleRepository(conn).list_summarized(), groups)
        flat = [(day, a) for day, items in days for a in items]
        try:
            current = paginate(flat, page=page, per_page=NEWS_PER_PAGE)
        except ValueError:
            raise HTTPException(status_code=404, detail="ページが見つかりません") from None
        # ページの中で日ごとにまとめ直す(ページが変わっても日の見出しを出す)
        sections: list[tuple] = []
        for day, a in current.items:
            if not sections or sections[-1][0] != day:
                sections.append((day, []))
            hit = matched_groups(a, groups)
            sections[-1][1].append((a, [g for g in KeywordGroup if g.label in hit]))
        return TEMPLATES.TemplateResponse(request, "news.html", {"sections": sections, "pager": current})

    def set_read(article_id: int, read: bool, page: str):
        with open_db() as conn:
            repo = ArticleRepository(conn)
            try:
                repo.mark_read(article_id, now=clock()) if read else repo.mark_unread(article_id)
            except LookupError:
                raise HTTPException(status_code=404, detail="記事が見つかりません") from None
        # 戻り先はページ番号だけを受け取り、URL は組み立てる(任意の URL へ飛ばされないように)
        back = int(page) if page.isdigit() and int(page) >= 1 else 1
        return RedirectResponse(f"/news?page={back}", status_code=303)

    @app.post("/news/{article_id}/read")
    def news_read(article_id: int, page: str = Form("1")):
        return set_read(article_id, True, page)

    @app.post("/news/{article_id}/unread")
    def news_unread(article_id: int, page: str = Form("1")):
        return set_read(article_id, False, page)

    return app


def _parse_group(name: str) -> KeywordGroup:
    try:
        return KeywordGroup[name]
    except KeyError:
        raise ValueError("グループが正しくありません") from None


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

# --- 予定のフォームと表示 ---------------------------------------------------------
_WEEKDAYS = "月火水木金土日"


def jp_day(day: date) -> str:
    """'11月16日(月)'"""
    return f"{day.month}月{day.day}日({_WEEKDAYS[day.weekday()]})"


def event_time_label(event: Event) -> str:
    """一覧の時刻の表示: 終日 / 09:00 / 10:00–11:30 / 11/20 23:00 → 11/21 01:00"""
    if isinstance(event, AllDayEvent):
        return "終日"
    start, end = event.start, event.end
    if end is None or end == start:
        return f"{start:%H:%M}"
    if end.date() == start.date():
        return f"{start:%H:%M}–{end:%H:%M}"
    return f"{start:%m/%d %H:%M} → {end:%m/%d %H:%M}"


def _event_form_fields(
    title: str = Form(""),
    all_day: str = Form(""),
    start_date: str = Form(""),
    start_time: str = Form(""),
    end_date: str = Form(""),
    end_time: str = Form(""),
    location: str = Form(""),
    memo: str = Form(""),
) -> dict:
    return {
        "title": title, "all_day": bool(all_day), "start_date": start_date, "start_time": start_time,
        "end_date": end_date, "end_time": end_time, "location": location, "memo": memo,
    }


def _event_form_from(values: dict) -> dict:
    base = {"title": "", "all_day": False, "start_date": "", "start_time": "", "end_date": "", "end_time": "",
            "location": "", "memo": ""}
    return {**base, **values}


def event_form(event: Event) -> dict:
    """予定をフォームの値にする(編集ページ・ポップアップ用)。"""
    if isinstance(event, AllDayEvent):
        values = {"all_day": True, "start_date": event.start.isoformat(),
                  "end_date": event.end.isoformat() if event.end else ""}
    else:
        values = {
            "start_date": event.start.date().isoformat(), "start_time": f"{event.start:%H:%M}",
            "end_date": event.end.date().isoformat() if event.end else "",
            "end_time": f"{event.end:%H:%M}" if event.end else "",
        }
    return _event_form_from({**values, "title": event.title, "location": event.location or "", "memo": event.memo or ""})


def _parse_time(text: str) -> time_of_day:
    try:
        value = time_of_day.fromisoformat(text.strip())
    except ValueError:
        raise ValueError("時刻が正しくありません(HH:MM)") from None
    if value.microsecond:
        raise ValueError("時刻が正しくありません(HH:MM)")
    return value


def _parse_event(form: dict) -> Event:
    """フォームの値から予定を作る。終日なら時刻の欄は無視する。場所・メモが空欄なら None。"""
    location = form["location"].strip() or None
    memo = form["memo"] if form["memo"].strip() else None
    if not form["start_date"].strip():
        raise ValueError("開始日を入れてください")
    start_day = _parse_date(form["start_date"])
    if form["all_day"]:
        return AllDayEvent(title=form["title"], start=start_day, end=_parse_date(form["end_date"]),
                           location=location, memo=memo)
    if not form["start_time"].strip():
        raise ValueError("開始の時刻を入れてください")
    start = datetime.combine(start_day, _parse_time(form["start_time"]))
    end = None
    if form["end_time"].strip():
        # 終了の日付が空なら開始と同じ日
        end = datetime.combine(_parse_date(form["end_date"]) or start_day, _parse_time(form["end_time"]))
    elif form["end_date"].strip():
        raise ValueError("終了の時刻を入れてください")
    return TimedEvent(title=form["title"], start=start, end=end, location=location, memo=memo)


TEMPLATES.env.globals.update(jp_day=jp_day, event_time_label=event_time_label, event_form=event_form)
