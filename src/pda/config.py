"""設定(フィード一覧・キーワード・上限・要約器)。

ここを書き換えれば、コードを変えずにニュースの取得元や絞り込みを変えられる。
業務ルールの背景は docs/requirements.md のニュース節。
"""

import os
from pathlib import Path

from pda.domain.article import Feed

# DB ファイル(Web 画面とニュースの処理で共通)。環境変数 PDA_DB で変えられる
DEFAULT_DB_PATH = Path("data/pda.db")


def db_path() -> Path:
    return Path(os.environ.get("PDA_DB", DEFAULT_DB_PATH))


# 取得元のフィード(2026-11-16: ユーザーが後で指定する。それまでは空)
# 例: Feed(name="サイト名", url="https://example.com/feed.xml")
FEEDS: list[Feed] = []

# 絞り込みのキーワード(⚠ 案。2026-11-16 Claude 作成。ユーザー確認待ち)
#   どちらかのグループの語がタイトルか概要文にあれば対象。両方なら優先(pda.news.filter)
#   英字だけの語は単語単位・大文字小文字を区別しない(複数形には当たらないので必要なら足す)
#   日本語は部分一致
KEYWORD_GROUPS: dict[str, list[str]] = {
    "物理・数学": [
        "量子", "物理", "数学", "統計力学", "熱力学", "相対論", "素粒子", "トポロジー", "位相",
        "幾何", "代数", "確率論", "微分方程式", "最適化", "定理",
        "quantum", "physics", "mathematics", "math", "topology", "topological", "geometry",
        "algebra", "probability", "thermodynamics", "entropy", "relativity", "particle physics",
        "differential equation", "differential equations", "optimization", "theorem",
    ],
    "IT": [
        "機械学習", "深層学習", "人工知能", "生成AI", "アルゴリズム", "暗号", "コンピュータ",
        "ソフトウェア", "プログラミング", "データベース", "セキュリティ", "半導体",
        "AI", "LLM", "LLMs", "machine learning", "deep learning", "neural network", "neural networks",
        "algorithm", "algorithms", "cryptography", "encryption", "software", "programming",
        "database", "compiler", "GPU", "GPUs", "semiconductor", "computer", "computers", "computing",
    ],
}

# 1 日に要約する件数の上限(同じ日に何度実行しても合計で数える)
DAILY_SUMMARY_LIMIT = 30

# 要約器。"mock" だけ(本物の Claude API への切り替えはユーザーの指示があるまで行わない)
SUMMARIZER = "mock"
MOCK_SUMMARY_MAX_CHARS = 200
