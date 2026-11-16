"""CLAUDE.md の「依存の向き」をテストで守る。

  web → (domain, db, news) / db → domain / news → domain / domain はどこにも依存しない
このテストが失敗したら、依存の向きを破る import が入っている。
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent.parent / "src" / "pda"

# パッケージ → import してよい pda の中のパッケージ(自分自身を含む)
ALLOWED = {
    "domain": {"pda.domain"},
    "news": {"pda.domain", "pda.news"},
    "db": {"pda.domain", "pda.db"},
}


def pda_imports(path: Path) -> set[str]:
    """ファイルが import している pda の中のモジュール名。"""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
            names |= {f"{node.module}.{a.name}" for a in node.names}
    return {n for n in names if n == "pda" or n.startswith("pda.")}


def cases():
    for package, allowed in ALLOWED.items():
        for path in sorted((SRC / package).glob("*.py")):
            yield pytest.param(path, allowed, id=f"{package}/{path.name}")


@pytest.mark.parametrize("path, allowed", list(cases()))
def test_依存の向きを破るimportがない(path, allowed):
    bad = {n for n in pda_imports(path) if not any(n == a or n.startswith(a + ".") for a in allowed)}

    assert bad == set(), f"{path.name} が依存してはいけないものを import しています: {sorted(bad)}"


def test_検査は禁止されたimportを見つけられる(tmp_path):
    # 検査そのものが働いていることの確認(何も見つけられない検査は常に通ってしまうため)
    f = tmp_path / "bad.py"
    f.write_text("from pda.db.migrate import connect\nimport pda.web\nfrom pda import config\n", encoding="utf-8")

    assert pda_imports(f) >= {"pda.db.migrate", "pda.web", "pda", "pda.config"}
