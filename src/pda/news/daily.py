"""1 日 1 回のニュース処理。

取得 → 解析 → 絞り込み → 新しい記事だけ保存 → 今日の残り枠まで要約 → 要約を保存。

news は db を知らない(依存の向きは news → domain)。保存先は ArticleStore Protocol で受け取る。
本物の部品(DB・HTTP・設定)の組み立ては pda.news_job が行う。
"""

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from pda.domain.article import Article, Feed
from pda.news.fetcher import Fetcher, parse_feed
from pda.news.filter import KeywordGroups, matched_groups, pick_for_summary
from pda.news.summarizer import Summarizer, apply_summaries

logger = logging.getLogger(__name__)


class ArticleStore(Protocol):
    def register_feeds(self, feeds: Iterable[Feed]) -> None: ...
    def add_new(self, articles: Sequence[Article]) -> list[Article]: ...
    def list_unsummarized(self) -> list[Article]: ...
    def save_summaries(self, articles: Iterable[Article]) -> None: ...
    def count_summarized_on(self, day: date) -> int: ...


@dataclass
class DailyReport:
    added: int = 0  # 新しく保存した記事の数
    summarized: int = 0  # 今回要約した記事の数
    failed_feeds: list[str] = field(default_factory=list)  # 取得・解析に失敗したフィードの名前


def run_daily(
    *,
    feeds: Sequence[Feed],
    fetcher: Fetcher,
    repo: ArticleStore,
    summarizer: Summarizer,
    groups: KeywordGroups,
    limit: int,
    now: datetime,
) -> DailyReport:
    """limit は 1 日に要約する件数の上限。同じ日に何度実行しても、その日の合計で数える。"""
    report = DailyReport()
    repo.register_feeds(feeds)

    relevant: list[Article] = []
    for feed in feeds:
        try:
            articles = parse_feed(feed, fetcher.fetch(feed.url), fetched_at=now)
        except Exception:  # 1 フィードの障害で全体を止めない。握りつぶさずログに残す
            logger.exception("%s: 取得または解析に失敗しました(%s)", feed.name, feed.url)
            report.failed_feeds.append(feed.name)
            continue
        relevant.extend(a for a in articles if matched_groups(a, groups))
    report.added = len(repo.add_new(relevant))

    remaining = max(0, limit - repo.count_summarized_on(now.date()))
    picked = pick_for_summary(repo.list_unsummarized(), groups, limit=remaining)
    done = apply_summaries(picked, summarizer, now=now)
    repo.save_summaries(done)
    report.summarized = len(done)
    return report
