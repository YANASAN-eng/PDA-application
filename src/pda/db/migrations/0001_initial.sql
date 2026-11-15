-- 0001: PDA 側(ToDo・予定・メモ・タグ)の初期スキーマ。ER 図は docs/db/er.md
-- 適用済みのこのファイルは書き換えない。変更は 0002 以降を追加して行う。
--
-- 日付・日時は ISO 8601 の TEXT で持つ(SQLite に日付型はない)
--   日付: YYYY-MM-DD            → 検査: x IS date(x)
--   日時: YYYY-MM-DDTHH:MM:SS   → 検査: x IS strftime('%Y-%m-%dT%H:%M:%S', x)
--   date() / strftime() は不正な値に NULL を返すか形式を正規化するので、
--   「元の値と一致すること」で形式と値の正しさを同時に縛れる。
--   ⚠ 比較は = ではなく IS を使う。CHECK は結果が NULL だと「違反なし」とみなすため、
--     x = date(x) だと不正な値(date(x) が NULL)が素通りする。IS は NULL が絡んでも 0/1 を返す。
--     (NOT NULL 列どうしの比較、例えば updated_at >= created_at は NULL にならないので = や >= でよい)
--   この形式どうしは文字列の大小比較が時刻の前後と一致する。
--
-- ドメイン(src/pda/domain/)と同じ規則を制約でも持つのは、
-- アプリのバグや手で打った SQL からデータを守る最後の防衛線にするため。

CREATE TABLE tasks (
    id         INTEGER PRIMARY KEY,
    title      TEXT    NOT NULL CHECK (trim(title) <> ''),
    priority   TEXT    NOT NULL CHECK (priority IN ('HIGH', 'MEDIUM', 'LOW')),
    due        TEXT             CHECK (due IS NULL OR due IS date(due)),
    done       INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1)),
    created_at TEXT    NOT NULL CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%S', created_at))
);

-- 終日予定と時刻付き予定を 1 テーブルで持つ。all_day で start_at / end_at の形式が決まる
CREATE TABLE events (
    id       INTEGER PRIMARY KEY,
    title    TEXT    NOT NULL CHECK (trim(title) <> ''),
    all_day  INTEGER NOT NULL CHECK (all_day IN (0, 1)),
    start_at TEXT    NOT NULL,
    end_at   TEXT,
    location TEXT,
    memo     TEXT,
    CHECK (
        (all_day = 1
            AND start_at IS date(start_at)
            AND (end_at IS NULL OR end_at IS date(end_at)))
        OR
        (all_day = 0
            AND start_at IS strftime('%Y-%m-%dT%H:%M:%S', start_at)
            AND (end_at IS NULL OR end_at IS strftime('%Y-%m-%dT%H:%M:%S', end_at)))
    ),
    CHECK (end_at IS NULL OR end_at >= start_at)
);

CREATE TABLE memos (
    id         INTEGER PRIMARY KEY,
    title      TEXT NOT NULL CHECK (trim(title) <> ''),
    body       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%S', created_at)),
    updated_at TEXT NOT NULL CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%S', updated_at)),
    CHECK (updated_at >= created_at)
);

-- タグ名は英字の大文字小文字を区別する(UNIQUE は既定の BINARY 照合)
CREATE TABLE tags (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK (name <> '' AND name = trim(name))
);

-- メモとタグの多対多。メモかタグを消すと、その結び付きも消える
CREATE TABLE memo_tags (
    memo_id INTEGER NOT NULL REFERENCES memos (id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    PRIMARY KEY (memo_id, tag_id)
);
