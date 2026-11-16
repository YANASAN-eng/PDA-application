"""記事の絞り込みと優先順位(I/O なし)。

キーワードは「グループ名 → 語の並び」で受け取る(例: {"物理・数学": [...], "IT": [...]})。
  - 英字だけ(ASCII)の語: 単語単位で照合し、大文字小文字を区別しない
      前後が英数字でないことを単語の境界とみなす。\\b を使わないのは、
      "C++" のように記号で終わる語では \\b が期待どおりに働かないため
  - それ以外の語(日本語など): 部分一致(英字が混じっても大文字小文字は区別しない)
優先順位: 当たったグループの数が多い順 → 公開日時の新しい順(公開日時なしは後)→ 元の順序。
"""

import re
from collections.abc import Iterable, Mapping
from datetime import datetime

from pda.domain.article import Article

KeywordGroups = Mapping[str, Iterable[str]]


def _matches(keyword: str, text: str) -> bool:
    if keyword.isascii():
        pattern = rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])"
        return re.search(pattern, text, re.IGNORECASE) is not None
    return keyword.casefold() in text.casefold()


def matched_groups(article: Article, groups: KeywordGroups) -> set[str]:
    """タイトルか概要文に語が 1 つでも含まれるグループの名前。"""
    text = f"{article.title}\n{article.description}"
    return {name for name, keywords in groups.items() if any(_matches(k, text) for k in keywords)}


def rank(articles: Iterable[Article], groups: KeywordGroups) -> list[Article]:
    """どれかのグループに当たる記事だけを、優先順位の高い順に返す。"""
    scored = [(a, len(matched_groups(a, groups))) for a in articles]

    def key(item: tuple[Article, int]):
        a, score = item
        has_date = a.published_at is not None
        return (score, has_date, a.published_at or datetime.min)

    # reverse=True でも sorted は安定なので、キーが同じなら元の順序を保つ
    return [a for a, score in sorted(scored, key=key, reverse=True) if score > 0]


def pick_for_summary(articles: Iterable[Article], groups: KeywordGroups, *, limit: int) -> list[Article]:
    """要約する記事: 未要約の対象記事を、優先順位の高い順に limit 件まで。"""
    if limit < 0:
        raise ValueError("上限は 0 以上にしてください")
    return rank((a for a in articles if not a.is_summarized), groups)[:limit]
