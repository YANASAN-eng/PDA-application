from datetime import date

import pytest

from pda.domain.routine import EVERY_DAY, Routine, routines_on, weekdays_label

MON, WED, FRI, SAT, SUN = 0, 2, 4, 5, 6
MONDAY = date(2026, 11, 16)  # 月曜日
SATURDAY = date(2026, 11, 21)


# --- 作成 ------------------------------------------------------------------
def test_曜日を省略すると毎日():
    assert Routine(title="英単語").weekdays == EVERY_DAY == frozenset(range(7))


@pytest.mark.parametrize("title", ["", "   "])
def test_空のタイトルでは日課を作れない(title):
    with pytest.raises(ValueError):
        Routine(title=title)


def test_曜日が1つもない日課は作れない():
    with pytest.raises(ValueError):
        Routine(title="筋トレ", weekdays=[])


@pytest.mark.parametrize("weekday", [-1, 7])
def test_範囲外の曜日は指定できない(weekday):
    with pytest.raises(ValueError):
        Routine(title="筋トレ", weekdays=[weekday])


def test_同じ曜日は1つにまとまる():
    assert Routine(title="筋トレ", weekdays=[MON, MON, WED]).weekdays == {MON, WED}


# --- その日の日課 ---------------------------------------------------------------
def test_選んだ曜日の日だけに出る():
    gym = Routine(title="筋トレ", weekdays=[MON, WED, FRI])

    assert (gym.is_due_on(MONDAY), gym.is_due_on(SATURDAY)) == (True, False)


def test_その日の日課を登録した順に返す():
    words = Routine(title="英単語")
    gym = Routine(title="筋トレ", weekdays=[MON, WED, FRI])
    weekend = Routine(title="部屋の掃除", weekdays=[SAT, SUN])

    assert routines_on(MONDAY, [words, gym, weekend]) == [words, gym]
    assert routines_on(SATURDAY, [words, gym, weekend]) == [words, weekend]


# --- 曜日の表示 ----------------------------------------------------------------
@pytest.mark.parametrize(
    "weekdays, label",
    [(EVERY_DAY, "毎日"), ({MON, WED, FRI}, "月・水・金"), ({SUN, MON}, "月・日"), ({SAT}, "土")],
)
def test_曜日の表示は全曜日なら毎日でそれ以外は月曜から順に並べる(weekdays, label):
    assert weekdays_label(weekdays) == label
