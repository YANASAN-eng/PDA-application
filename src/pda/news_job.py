"""ニュースの日次処理の入口(本物の DB・HTTP・設定を組み立てて run_daily を呼ぶ)。

実行: python -m pda.news_job   (DB は config.db_path()。環境変数 PDA_DB で変えられる)
スケジューラ(Windows タスクスケジューラ等)は未決定。決まったらこのコマンドを登録する。

news は db を知らない決まりなので、両方を組み立てるこのファイルは news の外(web と同じ外側)に置く。
"""

import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pda import config
from pda.db.article_repository import ArticleRepository
from pda.db.keyword_repository import KeywordRepository
from pda.db.migrate import connect, migrate_file
from pda.domain.article import Feed
from pda.domain.keyword import as_groups
from pda.news.daily import DailyReport, run_daily
from pda.news.fetcher import Fetcher, HttpFetcher
from pda.news.summarizer import MockSummarizer, Summarizer


def make_summarizer(name: str) -> Summarizer:
    if name == "mock":
        return MockSummarizer(max_chars=config.MOCK_SUMMARY_MAX_CHARS)
    # 本物(Claude API)はユーザーの指示があるまで作らない。意図せず API を呼ぶ経路を作らないため
    raise ValueError(f"使えない要約器です: {name!r}(今は 'mock' だけ)")


def run_job(
    db_path: Path,
    *,
    now: datetime,
    feeds: Sequence[Feed] | None = None,
    fetcher: Fetcher | None = None,
) -> DailyReport:
    """DB を最新のスキーマにしてから日次処理を行う。feeds / fetcher は省略すると設定と HTTP。"""
    migrate_file(db_path, now=now)
    conn = connect(db_path)
    try:
        return run_daily(
            feeds=config.FEEDS if feeds is None else feeds,
            fetcher=fetcher or HttpFetcher(),
            repo=ArticleRepository(conn),
            summarizer=make_summarizer(config.SUMMARIZER),
            groups=as_groups(KeywordRepository(conn).list_all()),  # キーワードは DB で管理(画面で編集)
            limit=config.DAILY_SUMMARY_LIMIT,
            now=now,
        )
    finally:
        conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db_path = config.db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().replace(microsecond=0)  # DB は秒単位
    report = run_job(db_path, now=now)
    logging.info(
        "新しい記事 %d 件 / 要約 %d 件 / 失敗したフィード %s",
        report.added, report.summarized, report.failed_feeds or "なし",
    )


if __name__ == "__main__":
    main()
