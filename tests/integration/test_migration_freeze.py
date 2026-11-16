"""main にマージしたマイグレーションが書き換えられていないかを検査する。

凍結の手順(マイグレーションを含むブランチを main にマージする直前に行う):
  1. 次のコマンドでチェックサムを出す
       python -c "from pda.db.migrate import checksum, MIGRATIONS_DIR as d; print(checksum(d / 'NNNN_xxx.sql'))"
  2. 下の FROZEN に「ファイル名: チェックサム」を 1 行足す

このテストが失敗したら、凍結済みのファイルを書き換えている。
変更を元に戻し(git restore)、やりたい変更は新しい番号のマイグレーションとして追加すること。
FROZEN の値を書き換えてテストを通すのは禁止(それは凍結を破ること)。
"""

import pytest

from pda.db.migrate import MIGRATIONS_DIR, _NAME, checksum

FROZEN: dict[str, str] = {
    "0001_initial.sql": "21dc1d9a78e6341572b5cd3586c33e84d5d2a5147ec4dc0e8369494c5160a451",
    "0002_add_task_detail.sql": "1713a955c82c1556d619342b9193c2737bc677e35be2dadda9010ffd5b800602",
    "0003_add_news.sql": "48c3556f8a0a87f2aea19fa81eae1e718c6b528f58cf1d6e7d05b5af08b7b607",
}


def _number(name: str) -> int:
    return int(_NAME.match(name).group(1))


@pytest.mark.parametrize("name", sorted(FROZEN))
def test_凍結したマイグレーションは書き換えられていない(name):
    path = MIGRATIONS_DIR / name

    assert path.exists(), f"凍結済みの {name} が消えています。git restore で戻してください"
    assert checksum(path) == FROZEN[name], (
        f"凍結済みの {name} が書き換えられています。git restore で戻し、"
        "変更は新しい番号のマイグレーションとして追加してください"
    )


def test_凍結した番号は1から連続している():
    assert sorted(_number(n) for n in FROZEN) == list(range(1, len(FROZEN) + 1))


def test_凍結していないマイグレーションは凍結済みより後の番号だけ():
    # 作業ブランチで追加中の新しいマイグレーションは凍結前でよいが、
    # 凍結済みの番号と同じか前の番号のファイルが増えていたら、それは差し替えの疑い
    latest_frozen = max(_number(n) for n in FROZEN)
    unfrozen = [p.name for p in MIGRATIONS_DIR.glob("*.sql") if p.name not in FROZEN]

    assert all(_number(n) > latest_frozen for n in unfrozen), unfrozen
