import pytest

from pda.db.keyword_repository import DuplicateKeywordError, KeywordRepository
from pda.db.migrate import connect, migrate
from pda.domain.keyword import Keyword, KeywordGroup

IT, MP = KeywordGroup.IT, KeywordGroup.MATH_PHYSICS


@pytest.fixture
def repo():
    conn = connect(":memory:")
    migrate(conn)
    conn.execute("DELETE FROM keywords")  # 初期データを除く
    yield KeywordRepository(conn)
    conn.close()


def test_追加したキーワードを登録した順に取り出せてidが振られる(repo):
    a, b, c = Keyword(group=IT, word="AI"), Keyword(group=MP, word="量子"), Keyword(group=IT, word="GPU")
    for k in (a, b, c):
        repo.add(k)

    assert repo.list_all() == [a, b, c]
    assert all(isinstance(k.id, int) for k in (a, b, c))


@pytest.mark.parametrize(
    "existing, dup",
    [("AI", "AI"), ("AI", "ai"), ("AI", "Ai"), ("ＡＩ", "ａｉ"), ("量子", " 量子 ")],
    ids=["同じ", "小文字", "混在", "全角英字", "前後の空白"],
)
def test_同じグループに同じ語は登録できない(repo, existing, dup):
    repo.add(Keyword(group=IT, word=existing))

    with pytest.raises(DuplicateKeywordError):
        repo.add(Keyword(group=IT, word=dup))


def test_重複で断られたとき何も増えない(repo):
    repo.add(Keyword(group=IT, word="AI"))
    dup = Keyword(group=IT, word="ai")

    with pytest.raises(DuplicateKeywordError):
        repo.add(dup)

    assert (len(repo.list_all()), dup.id) == (1, None)


def test_別のグループなら同じ語を登録できる(repo):
    repo.add(Keyword(group=IT, word="量子コンピュータ"))
    repo.add(Keyword(group=MP, word="量子コンピュータ"))

    assert len(repo.list_all()) == 2


def test_重複のエラーは日本語の説明を持つ(repo):
    repo.add(Keyword(group=IT, word="AI"))

    with pytest.raises(DuplicateKeywordError, match="登録済み"):
        repo.add(Keyword(group=IT, word="ai"))


def test_保存済みのキーワードを二重に追加できない(repo):
    k = Keyword(group=IT, word="AI")
    repo.add(k)

    with pytest.raises(ValueError):
        repo.add(k)


def test_削除すると一覧から消える(repo):
    k = Keyword(group=IT, word="AI")
    repo.add(k)

    repo.delete(k.id)

    assert repo.list_all() == []


def test_存在しないキーワードは削除できない(repo):
    with pytest.raises(LookupError):
        repo.delete(999)
