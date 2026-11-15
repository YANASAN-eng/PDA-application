import pytest

from pda.domain.task import Priority, Task


def test_優先度は高中低の3段階():
    assert [p.label for p in Priority] == ["高", "中", "低"]


def test_タスクはタイトルと優先度を指定して作る():
    task = Task(title="レポートを書く", priority=Priority.HIGH)

    assert task.title == "レポートを書く"
    assert task.priority is Priority.HIGH


def test_作ったばかりのタスクは未完了():
    task = Task(title="レポートを書く", priority=Priority.MEDIUM)

    assert task.done is False


def test_期限は指定しなくてもよい():
    task = Task(title="本を読む", priority=Priority.LOW)

    assert task.due is None


@pytest.mark.parametrize("title", ["", "   "])
def test_空のタイトルではタスクを作れない(title):
    with pytest.raises(ValueError):
        Task(title=title, priority=Priority.MEDIUM)
