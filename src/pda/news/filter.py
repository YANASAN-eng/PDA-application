"""記事の絞り込みと優先順位(I/O なし)。

キーワードは「グループ名 → 語の並び」で受け取る(例: {"物理・数学": [...], "IT": [...]})。
  - 英字だけ(ASCII)の語: 単語単位で照合し、大文字小文字を区別しない
      前後が英数字でないことを単語の境界とみなす。\\b を使わないのは、
      "C++" のように記号で終わる語では \\b が期待どおりに働かないため
  - それ以外の語(日本語など): 部分一致(英字が混じっても大文字小文字は区別しない)
優先順位: 当たったグループの数が多い順 → 公開日時の新しい順(公開日時なしは後)→ 元の順序。
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, datetime

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


def sort_by_priority(articles: Iterable[Article], groups: KeywordGroups) -> list[Article]:
    """優先順位の高い順に並べる(どのグループにも当たらない記事も落とさず、最後に回す)。"""

    def key(a: Article):
        has_date = a.published_at is not None
        return (len(matched_groups(a, groups)), has_date, a.published_at or datetime.min)

    # reverse=True でも sorted は安定なので、キーが同じなら元の順序を保つ
    return sorted(articles, key=key, reverse=True)


def rank(articles: Iterable[Article], groups: KeywordGroups) -> list[Article]:
    """どれかのグループに当たる記事だけを、優先順位の高い順に返す。"""
    return [a for a in sort_by_priority(articles, groups) if matched_groups(a, groups)]


def news_by_day(articles: Iterable[Article], groups: KeywordGroups) -> list[tuple[date, list[Article]]]:
    """一覧の並び: 要約済みの記事だけを、要約した日ごと(新しい日が先)に、日の中は優先順位で。

    一覧では記事を落とさない(キーワードを消して当たらなくなった記事は、その日の最後に回る)。
    """
    by_day: dict[date, list[Article]] = defaultdict(list)
    for a in articles:
        if a.summarized_at is not None:
            by_day[a.summarized_at.date()].append(a)
    return [(day, sort_by_priority(by_day[day], groups)) for day in sorted(by_day, reverse=True)]


def pick_for_summary(articles: Iterable[Article], groups: KeywordGroups, *, limit: int) -> list[Article]:
    """要約する記事: 未要約の対象記事を、優先順位の高い順に limit 件まで。"""
    if limit < 0:
        raise ValueError("上限は 0 以上にしてください")
    return rank((a for a in articles if not a.is_summarized), groups)[:limit]
