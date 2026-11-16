"""ニュース記事とフィードのドメインモデル(I/O なし)。

時刻はタイムゾーンを持たない日本時間(naive datetime)として扱う(予定と同じ)。
"""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from pda.domain._validation import require_title


def require_web_url(url: str) -> None:
    """http / https で、ホストのある URL でなければ ValueError。

    画面ではこの URL をリンクにする。javascript: などを通すと、クリックで攻撃コードが動くため。
    """
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        raise ValueError(f"http / https の URL ではありません: {url!r}")


@dataclass(frozen=True)
class Feed:
    """記事の取得元。URL で 1 つに決まる。"""

    name: str
    url: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("フィードの名前は空にできません")
        require_web_url(self.url)


@dataclass(kw_only=True)
class Article:
    """記事。URL で 1 つに決まる(同じ URL の記事は 1 件)。"""

    feed: Feed
    url: str
    title: str
    fetched_at: datetime
    description: str = ""  # RSS の概要文(HTML タグを除いたもの)。「なし」は空文字
    published_at: datetime | None = None  # フィードに無ければ None
    summary: str | None = None  # 要約前は None
    summarized_at: datetime | None = None  # summary と必ず同時に入る
    read_at: datetime | None = None  # 既読にした日時。None は未読
    id: int | None = None  # 保存前は None。リポジトリが保存時に振る

    def __post_init__(self) -> None:
        require_title(self.title)
        require_web_url(self.url)
        if (self.summary is None) != (self.summarized_at is None):
            raise ValueError("要約文と要約日時は両方そろえて持ちます")

    @property
    def is_summarized(self) -> bool:
        return self.summary is not None

    def set_summary(self, summary: str, *, now: datetime) -> None:
        self.summary, self.summarized_at = summary, now

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_read(self, *, now: datetime) -> None:
        self.read_at = now

    def mark_unread(self) -> None:
        self.read_at = None
