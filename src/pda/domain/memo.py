"""メモのドメインモデル(I/O なし)。"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from pda.domain._validation import require_title


def _normalize_tags(tags: Iterable[str]) -> frozenset[str]:
    """前後の空白を除き、重複をまとめる。空のタグがあれば ValueError。"""
    normalized = [t.strip() for t in tags]
    if any(t == "" for t in normalized):
        raise ValueError("空のタグは付けられません")
    return frozenset(normalized)


@dataclass(kw_only=True)
class Memo:
    title: str
    created_at: datetime
    body: str = ""
    tags: Iterable[str] = ()
    updated_at: datetime | None = None  # 省略時は created_at と同じ
    id: int | None = None  # 保存前は None。リポジトリが保存時に振る

    def __post_init__(self) -> None:
        require_title(self.title)
        self.tags = _normalize_tags(self.tags)  # 以後は frozenset[str]
        if self.updated_at is None:
            self.updated_at = self.created_at

    def edit(self, *, title: str, body: str, tags: Iterable[str], now: datetime) -> None:
        """内容を書き換えて更新日時を now にする。検証に失敗したら何も変えない。"""
        # 先にすべて検証してから代入する(途中まで書き換わった状態を残さない)
        require_title(title)
        new_tags = _normalize_tags(tags)
        if now < self.created_at:
            raise ValueError("作成日時より前の時刻では編集できません")
        self.title, self.body, self.tags, self.updated_at = title, body, new_tags, now

    def matches(self, keyword: str) -> bool:
        """keyword がタイトルか本文に含まれるか(英字の大文字・小文字は区別しない)。"""
        k = keyword.casefold()
        return k in self.title.casefold() or k in self.body.casefold()


def with_tag(memos: Iterable[Memo], tag: str) -> list[Memo]:
    return [m for m in memos if tag in m.tags]


def search_memos(memos: Iterable[Memo], keyword: str) -> list[Memo]:
    """キーワードを含むメモを返す。キーワードが空(空白のみ)なら全件。"""
    k = keyword.strip()
    return [m for m in memos if not k or m.matches(k)]


def memos_by_updated(memos: Iterable[Memo]) -> list[Memo]:
    """更新日時の新しい順。同じ日時では元の順序を保つ(sorted は安定ソート)。"""
    return sorted(memos, key=lambda m: m.updated_at, reverse=True)
