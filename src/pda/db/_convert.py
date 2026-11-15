"""ドメインの値と DB の TEXT の相互変換(リポジトリ共通)。"""

from datetime import date, datetime

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


def datetime_to_db(value: datetime) -> str:
    """秒単位の日時を 'YYYY-MM-DDTHH:MM:SS' にする。マイクロ秒があれば ValueError(黙って切り捨てない)。"""
    if value.microsecond:
        raise ValueError("日時は秒単位で渡してください(DB は秒単位で保存します)")
    return value.strftime(DATETIME_FORMAT)


def datetime_from_db(text: str) -> datetime:
    return datetime.strptime(text, DATETIME_FORMAT)


def date_to_db(value: date) -> str:
    return value.isoformat()


def date_from_db(text: str) -> date:
    return date.fromisoformat(text)
