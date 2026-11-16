"""RSS / Atom の取得と解析。

  parse_feed   … 取得済みのバイト列を記事にする(I/O なし。テストはフィクスチャの XML で行う)
  Fetcher      … 取得の Protocol。バッチ処理はこれだけを知り、テストでは Fake に差し替える
  HttpFetcher  … 本物の取得(ネットワークに出るのでテストしない。薄く保つ)
"""

import logging
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Protocol

import feedparser

from pda.domain.article import Article, Feed

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


class FeedError(Exception):
    """フィードとして読めない内容だった。"""


class Fetcher(Protocol):
    def fetch(self, url: str) -> bytes:
        """URL の内容を返す。取得できなければ例外を投げる。"""
        ...


class HttpFetcher:
    """HTTP で取得する。利用者を特定できる情報は送らない(User-Agent は汎用の名前)。"""

    def __init__(self, *, timeout_seconds: float = 30) -> None:
        self._timeout = timeout_seconds

    def fetch(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "pda-news-reader/0.1"})
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            return response.read()


class _TextExtractor(HTMLParser):
    """HTML から文字だけを取り出す(文字参照 &amp; などは convert_charrefs で戻る)。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(html: str) -> str:
    """タグを除き、文字参照を戻し、連続する空白(改行を含む)を 1 つの空白にまとめる。"""
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    return " ".join("".join(extractor.parts).split())


def _to_jst(parsed: time.struct_time | None) -> datetime | None:
    """feedparser の日時(UTC の struct_time)を、タイムゾーンなしの日本時間にする。"""
    if parsed is None:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc).astimezone(JST).replace(tzinfo=None)


def parse_feed(feed: Feed, content: bytes, *, fetched_at: datetime) -> list[Article]:
    """フィードの内容を記事の並びにする。

    記事にできない項目(空のタイトル・http(s) 以外のリンク等)は、その項目だけ飛ばして警告を残す。
    フィードとして読めず項目が 1 つもなければ FeedError(正常で項目 0 件なら空のリスト)。
    """
    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise FeedError(f"{feed.name}: フィードとして読めません({parsed.get('bozo_exception')!r})")

    articles = []
    for entry in parsed.entries:
        try:
            articles.append(
                Article(
                    feed=feed,
                    url=entry.get("link", ""),
                    title=html_to_text(entry.get("title", "")),
                    description=html_to_text(entry.get("summary", "")),
                    published_at=_to_jst(entry.get("published_parsed") or entry.get("updated_parsed")),
                    fetched_at=fetched_at,
                )
            )
        except ValueError as e:
            logger.warning("%s: 項目を飛ばしました(%s)", feed.name, e)
    return articles
