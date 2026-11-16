"""一覧のページ分け(I/O なし)。"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    page: int  # 1 始まり
    total_pages: int  # 0 件でも 1

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages


def paginate(items: Sequence[T], *, page: int, per_page: int) -> Page[T]:
    """page ページ目(1 始まり)の分を返す。範囲外のページなら ValueError(画面では 404)。"""
    if per_page < 1:
        raise ValueError("1 ページの件数は 1 以上にしてください")
    total_pages = max(1, ceil(len(items) / per_page))
    if not 1 <= page <= total_pages:
        raise ValueError(f"ページは 1〜{total_pages} です(指定: {page})")
    start = (page - 1) * per_page
    return Page(items=list(items[start : start + per_page]), page=page, total_pages=total_pages)
