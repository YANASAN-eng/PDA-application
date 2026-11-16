"""ニュースの絞り込みキーワード(I/O なし)。

キーワードは使う人が読みながら育てるデータなので DB で管理する(2026-11-16 ユーザー決定)。
照合の規則は pda.news.filter にある。ここの「同じ語」の定義はそれと一致させる:
  照合では英字の大文字小文字を区別しない → 登録でも AI と ai は同じ語(重複登録を断る)
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class KeywordGroup(Enum):
    """分野。定義順 = 表示順。優先順位は「当たったグループの数」なので、グループは固定する。"""

    MATH_PHYSICS = "物理・数学"
    IT = "IT"

    @property
    def label(self) -> str:
        return self.value


def is_same_word(a: str, b: str) -> bool:
    """大文字小文字だけが違う語は同じ語(照合でも同じとみなすため)。"""
    return a.casefold() == b.casefold()


@dataclass(kw_only=True)
class Keyword:
    group: KeywordGroup
    word: str
    id: int | None = None  # 保存前は None。リポジトリが保存時に振る

    def __post_init__(self) -> None:
        self.word = self.word.strip()
        if not self.word:
            raise ValueError("空のキーワードは登録できません")


def as_groups(keywords: Iterable[Keyword]) -> dict[str, list[str]]:
    """絞り込み(pda.news.filter)に渡す形: グループ名 → 語の並び。語のないグループも含める。"""
    groups: dict[str, list[str]] = {g.label: [] for g in KeywordGroup}
    for k in keywords:
        groups[k.group.label].append(k.word)
    return groups
