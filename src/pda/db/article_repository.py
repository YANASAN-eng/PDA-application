"""ニュースのフィードと記事の保存と取り出し(SQLite)。

記事は URL で 1 件に決まる(articles.url は UNIQUE)。既にある URL の記事は保存しない。
記事の feed はフィードの URL で feeds の行に対応づける。
画面に出す並び順はドメイン(pda.news.filter.rank)が決め、ここでは保存した順で返す。
"""

import sqlite3
from collections.abc import Iterable, Sequence
from datetime import date, datetime, time, timedelta

from pda.db._convert import datetime_from_db, datetime_to_db
from pda.db._transaction import transaction
from pda.domain.article import Article, Feed

# 列名はコード内の定数なので f-string で埋め込んでよい。値は必ず ? プレースホルダで渡す
_SELECT = (
    "SELECT a.id, f.name, f.url, a.url, a.title, a.description, a.published_at, a.fetched_at,"
    " a.summary, a.summarized_at, a.read_at FROM articles a JOIN feeds f ON f.id = a.feed_id"
)


def _optional_dt(text: str | None):
    return datetime_from_db(text) if text is not None else None


def _from_row(row: tuple) -> Article:
    id_, feed_name, feed_url, url, title, description, published_at, fetched_at, summary, summarized_at, read_at = row
    return Article(
        id=id_,
        feed=Feed(name=feed_name, url=feed_url),
        url=url,
        title=title,
        description=description,
        published_at=_optional_dt(published_at),
        fetched_at=datetime_from_db(fetched_at),
        summary=summary,
        summarized_at=_optional_dt(summarized_at),
        read_at=_optional_dt(read_at),
    )


class ArticleRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def register_feeds(self, feeds: Iterable[Feed]) -> None:
        """フィードを登録する。同じ URL が既にあれば名前を合わせる(設定が正本)。"""
        with transaction(self._conn):
            for feed in feeds:
                self._conn.execute(
                    "INSERT INTO feeds (name, url) VALUES (?, ?) ON CONFLICT (url) DO UPDATE SET name = excluded.name",
                    (feed.name, feed.url),
                )

    def add_new(self, articles: Sequence[Article]) -> list[Article]:
        """まだない URL の記事だけを保存して id を振り、保存した記事を返す。

        1 回の呼び出しの中で同じ URL が重なったら最初の 1 件だけ保存する。
        全体で 1 トランザクション(途中で失敗したら 1 件も残らず、id も振らない)。
        """
        # 値の変換(マイクロ秒の拒否など)は書き込みの前に済ませる
        rows = [
            (
                a.url,
                a.title,
                a.description,
                datetime_to_db(a.published_at) if a.published_at is not None else None,
                datetime_to_db(a.fetched_at),
            )
            for a in articles
        ]
        added: list[tuple[Article, int]] = []
        with transaction(self._conn):
            for a, row in zip(articles, rows):
                cur = self._conn.execute(
                    "INSERT INTO articles (feed_id, url, title, description, published_at, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (url) DO NOTHING",
                    (self._feed_id(a.feed), *row),
                )
                if cur.rowcount == 1:  # 0 なら既にある URL(lastrowid はこのとき当てにならない)
                    added.append((a, cur.lastrowid))
        for a, new_id in added:  # COMMIT できてから振る
            a.id = new_id
        return [a for a, _ in added]

    def list_all(self) -> list[Article]:
        """保存した順(id の昇順)。"""
        return [_from_row(r) for r in self._conn.execute(f"{_SELECT} ORDER BY a.id")]

    def list_unsummarized(self) -> list[Article]:
        """未要約の記事を保存した順に。"""
        return [_from_row(r) for r in self._conn.execute(f"{_SELECT} WHERE a.summary IS NULL ORDER BY a.id")]

    def list_summarized(self) -> list[Article]:
        """要約済みの記事を保存した順に(一覧の並びはドメインの news_by_day が決める)。"""
        return [_from_row(r) for r in self._conn.execute(f"{_SELECT} WHERE a.summary IS NOT NULL ORDER BY a.id")]

    def mark_read(self, article_id: int, *, now: datetime) -> None:
        self._set_read_at(article_id, datetime_to_db(now))

    def mark_unread(self, article_id: int) -> None:
        self._set_read_at(article_id, None)

    def _set_read_at(self, article_id: int, value: str | None) -> None:
        cur = self._conn.execute("UPDATE articles SET read_at = ? WHERE id = ?", (value, article_id))
        if cur.rowcount == 0:
            raise LookupError(f"記事が見つかりません(id={article_id})")

    def save_summaries(self, articles: Iterable[Article]) -> None:
        """要約文と要約日時を書き込む(1 トランザクション)。"""
        rows = []
        for a in articles:
            if a.id is None:
                raise ValueError("保存前の記事の要約は保存できません")
            if a.summary is None or a.summarized_at is None:
                raise ValueError(f"要約のない記事です(id={a.id})")
            rows.append((a.summary, datetime_to_db(a.summarized_at), a.id))
        with transaction(self._conn):
            for row in rows:
                cur = self._conn.execute("UPDATE articles SET summary = ?, summarized_at = ? WHERE id = ?", row)
                if cur.rowcount == 0:
                    raise LookupError(f"記事が見つかりません(id={row[2]})")

    def count_summarized_on(self, day: date) -> int:
        """day に要約した記事の件数(1 日の上限の計算用)。

        日時は固定形式の TEXT なので、文字列の大小 = 時刻の前後。[day 0:00, 翌日 0:00) の範囲で数える。
        """
        start = datetime.combine(day, time.min)
        row = self._conn.execute(
            "SELECT count(*) FROM articles WHERE summarized_at >= ? AND summarized_at < ?",
            (datetime_to_db(start), datetime_to_db(start + timedelta(days=1))),
        ).fetchone()
        return row[0]

    def _feed_id(self, feed: Feed) -> int:
        row = self._conn.execute("SELECT id FROM feeds WHERE url = ?", (feed.url,)).fetchone()
        if row is None:
            raise LookupError(f"登録されていないフィードです: {feed.url}")
        return row[0]
