-- 0002: ToDo に詳細(任意)を足す(2026-11-16)。理由は docs/requirements.md の ToDo 節
-- 適用済みのこのファイルは書き換えない。変更は 0003 以降を追加して行う。
--
-- 「なし」は空文字だけで表す(NULL と空文字の 2 通りにしない)ので NOT NULL DEFAULT ''。
-- SQLite の ADD COLUMN で NOT NULL の列を足すには NULL でない既定値が要る。既存の行には '' が入る。

ALTER TABLE tasks ADD COLUMN detail TEXT NOT NULL DEFAULT '';
