"""ドメインモデル共通の入力検証。"""


def require_title(title: str) -> None:
    """タイトルが空(空白のみを含む)なら ValueError。"""
    if not title.strip():
        raise ValueError("タイトルは空にできません")
