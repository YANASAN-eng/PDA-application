-- 0004: ニュースの絞り込みキーワードを DB で管理する(2026-11-16)。理由は docs/requirements.md のニュース節
-- 適用済みのこのファイルは書き換えない。変更は 0005 以降を追加して行う。
--
-- キーワードは使う人が画面から育てるデータなので、コード(config.py)から DB に移す。
-- grp はグループのコード(pda.domain.keyword.KeywordGroup の名前)。グループは固定なので CHECK で縛る
--   (優先順位が「当たったグループの数」なので、グループを自由に増やせる作りにはしない)

CREATE TABLE keywords (
    id   INTEGER PRIMARY KEY,
    grp  TEXT NOT NULL CHECK (grp IN ('MATH_PHYSICS', 'IT')),
    word TEXT NOT NULL CHECK (word <> '' AND word = trim(word))
);

-- 同じグループに、英字の大文字小文字だけが違う語は置かない(照合で同じとみなす語は登録でも同じ)。
-- NOCASE が同一視するのは ASCII の英字だけ。全角英字などはアプリ側(is_same_word)で検査する。ここは最後の防衛線
CREATE UNIQUE INDEX keywords_grp_word ON keywords (grp, word COLLATE NOCASE);

-- 初期データ: 2026-11-16 時点の config.KEYWORD_GROUPS(Claude の案)をそのまま移したもの
INSERT INTO keywords (grp, word) VALUES
    ('MATH_PHYSICS', '量子'),
    ('MATH_PHYSICS', '物理'),
    ('MATH_PHYSICS', '数学'),
    ('MATH_PHYSICS', '統計力学'),
    ('MATH_PHYSICS', '熱力学'),
    ('MATH_PHYSICS', '相対論'),
    ('MATH_PHYSICS', '素粒子'),
    ('MATH_PHYSICS', 'トポロジー'),
    ('MATH_PHYSICS', '位相'),
    ('MATH_PHYSICS', '幾何'),
    ('MATH_PHYSICS', '代数'),
    ('MATH_PHYSICS', '確率論'),
    ('MATH_PHYSICS', '微分方程式'),
    ('MATH_PHYSICS', '最適化'),
    ('MATH_PHYSICS', '定理'),
    ('MATH_PHYSICS', 'quantum'),
    ('MATH_PHYSICS', 'physics'),
    ('MATH_PHYSICS', 'mathematics'),
    ('MATH_PHYSICS', 'math'),
    ('MATH_PHYSICS', 'topology'),
    ('MATH_PHYSICS', 'topological'),
    ('MATH_PHYSICS', 'geometry'),
    ('MATH_PHYSICS', 'algebra'),
    ('MATH_PHYSICS', 'probability'),
    ('MATH_PHYSICS', 'thermodynamics'),
    ('MATH_PHYSICS', 'entropy'),
    ('MATH_PHYSICS', 'relativity'),
    ('MATH_PHYSICS', 'particle physics'),
    ('MATH_PHYSICS', 'differential equation'),
    ('MATH_PHYSICS', 'differential equations'),
    ('MATH_PHYSICS', 'optimization'),
    ('MATH_PHYSICS', 'theorem'),
    ('IT', '機械学習'),
    ('IT', '深層学習'),
    ('IT', '人工知能'),
    ('IT', '生成AI'),
    ('IT', 'アルゴリズム'),
    ('IT', '暗号'),
    ('IT', 'コンピュータ'),
    ('IT', 'ソフトウェア'),
    ('IT', 'プログラミング'),
    ('IT', 'データベース'),
    ('IT', 'セキュリティ'),
    ('IT', '半導体'),
    ('IT', 'AI'),
    ('IT', 'LLM'),
    ('IT', 'LLMs'),
    ('IT', 'machine learning'),
    ('IT', 'deep learning'),
    ('IT', 'neural network'),
    ('IT', 'neural networks'),
    ('IT', 'algorithm'),
    ('IT', 'algorithms'),
    ('IT', 'cryptography'),
    ('IT', 'encryption'),
    ('IT', 'software'),
    ('IT', 'programming'),
    ('IT', 'database'),
    ('IT', 'compiler'),
    ('IT', 'GPU'),
    ('IT', 'GPUs'),
    ('IT', 'semiconductor'),
    ('IT', 'computer'),
    ('IT', 'computers'),
    ('IT', 'computing');
