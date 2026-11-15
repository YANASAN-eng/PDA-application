"""ToDo タスクのドメインモデル(I/O なし)。"""

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Priority(Enum):
    """優先度。定義順 = 高い順。"""

    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"

    @property
    def label(self) -> str:
        return self.value


@dataclass
class Task:
    title: str
    priority: Priority
    due: date | None = None
    done: bool = False

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("タイトルは空にできません")
