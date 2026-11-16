"""記事の要約。

他のモジュールは Summarizer Protocol だけを知る。
現在はモック要約(MockSummarizer)で運用し、Claude API は呼ばない(費用 0 円)。
本物(ClaudeSummarizer)への切り替えはユーザーの指示があるまで行わない。
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from pda.domain.article import Article


class Summarizer(Protocol):
    def summarize(self, articles: Sequence[Article]) -> dict[str, str]:
        """記事をまとめて要約し、URL → 要約文 を返す。

        要約できなかった記事(本物の API での拒否・打ち切りなど)は結果に含めない。
        複数記事を 1 回で受け取るのは、本物の API で指示文を記事ごとに繰り返さないため(費用)。
        """
        ...


class MockSummarizer:
    """概要文の先頭 max_chars 文字を要約とみなす(API を呼ばない)。"""

    def __init__(self, *, max_chars: int) -> None:
        if max_chars < 1:
            raise ValueError("上限文字数は 1 以上にしてください")
        self._max_chars = max_chars

    def summarize(self, articles: Sequence[Article]) -> dict[str, str]:
        return {a.url: self._truncate(a.description) for a in articles}

    def _truncate(self, text: str) -> str:
        return text if len(text) <= self._max_chars else text[: self._max_chars] + "…"


def apply_summaries(articles: Sequence[Article], summarizer: Summarizer, *, now: datetime) -> list[Article]:
    """要約して記事に反映し、要約できた記事を返す。要約が返らなかった記事は未要約のまま。"""
    if not articles:
        return []  # 空で呼ばない(本物の API では空のリクエストにも費用がかかりうる)
    results = summarizer.summarize(articles)
    done = []
    for a in articles:
        if a.url in results:
            a.set_summary(results[a.url], now=now)
            done.append(a)
    return done
