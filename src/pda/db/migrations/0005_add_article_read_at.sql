-- 0005: 記事の既読を記録する(2026-11-16)。理由は docs/requirements.md の「ニュースの表示」
-- 適用済みのこのファイルは書き換えない。変更は 0006 以降を追加して行う。
--
-- read_at: 既読にした日時。NULL は未読。0/1 ではなく日時にしたのは、手間が同じで後で使える情報が増えるため
--   既存の記事は NULL(未読)になる。CHECK は 0001 と同じ書き方(IS で NULL を素通りさせない)

ALTER TABLE articles ADD COLUMN read_at TEXT
    CHECK (read_at IS NULL OR read_at IS strftime('%Y-%m-%dT%H:%M:%S', read_at));

-- 一覧は「要約済みの記事を要約した日ごと」に取り出すので、summarized_at に索引を作る
CREATE INDEX articles_summarized_at ON articles (summarized_at);
