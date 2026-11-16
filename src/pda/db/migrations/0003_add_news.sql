-- 0003: ニュース(フィードと記事)を足す(2026-11-16)。業務ルールは docs/requirements.md のニュース節
-- 適用済みのこのファイルは書き換えない。変更は 0004 以降を追加して行う。
--
-- 日時の形式の検査は 0001 の冒頭のコメントと同じ(x IS strftime(...) で形式と値を同時に縛る)。
-- URL は http / https だけ(画面でリンクにするので javascript: 等を防ぐ)。大文字小文字は問わない。
--   ドメイン(pda.domain.article.require_web_url)と同じ規則を、最後の防衛線として DB にも持つ。
--   ホストの有無まではここでは見ない(SQL で URL を分解するのは不正確になるため、ドメインに任せる)。

-- フィード(取得元)。一覧は config.py が正本で、取得のたびに名前を合わせる。
-- 設定から消したフィードも、記事が残っている限り消さない(articles からの参照で守られる)
CREATE TABLE feeds (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (trim(name) <> ''),
    url  TEXT NOT NULL UNIQUE
         CHECK (lower(substr(url, 1, 7)) = 'http://' OR lower(substr(url, 1, 8)) = 'https://')
);

-- 記事。同じ URL の記事は 1 件(url は代替キー)。対象になった記事だけを保存する
--   description: RSS の概要文(HTML タグ除去済み)。「なし」は空文字なので NOT NULL
--   summary:     NULL は「まだ要約していない」。空文字は「要約した結果が空」(意味が違うので NULL を使う)
CREATE TABLE articles (
    id            INTEGER PRIMARY KEY,
    feed_id       INTEGER NOT NULL REFERENCES feeds (id),
    url           TEXT    NOT NULL UNIQUE
                  CHECK (lower(substr(url, 1, 7)) = 'http://' OR lower(substr(url, 1, 8)) = 'https://'),
    title         TEXT    NOT NULL CHECK (trim(title) <> ''),
    description   TEXT    NOT NULL DEFAULT '',
    published_at  TEXT             CHECK (published_at IS NULL OR published_at IS strftime('%Y-%m-%dT%H:%M:%S', published_at)),
    fetched_at    TEXT    NOT NULL CHECK (fetched_at IS strftime('%Y-%m-%dT%H:%M:%S', fetched_at)),
    summary       TEXT,
    summarized_at TEXT             CHECK (summarized_at IS NULL OR summarized_at IS strftime('%Y-%m-%dT%H:%M:%S', summarized_at)),
    -- 要約文と要約日時は両方あるか両方ないか(IS NULL は 0/1 を返し NULL にならないので = でよい)
    CHECK ((summary IS NULL) = (summarized_at IS NULL))
);

-- 外部キーの列には SQLite が自動で索引を作らない。フィードごとの絞り込みとフィード削除時の検査用
CREATE INDEX articles_feed_id ON articles (feed_id);
