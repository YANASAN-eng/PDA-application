-- 0006: 日課(Daily)を足す(2026-11-16)。業務ルールは docs/requirements.md の「日課(Daily)」
-- 適用済みのこのファイルは書き換えない。変更は 0007 以降を追加して行う。
--
-- 曜日は 1 つの列に詰めず(例: '0,2,4' やビットの数)、routine_weekdays に 1 行ずつ持つ。
--   1 つの欄に複数の値を入れると第一正規形に反し、「月曜の日課」を探すにも文字列の分解が要るため。
-- 「曜日が 1 つ以上」は行の数の制約で、CHECK(1 行の中しか見られない)では表せない。
--   ドメイン(pda.domain.routine.Routine)が守り、リポジトリが 1 トランザクションで保存する。
-- 曜日の番号は Python の date.weekday() と同じ: 月=0 … 日=6。

CREATE TABLE routines (
    id    INTEGER PRIMARY KEY,
    title TEXT NOT NULL CHECK (trim(title) <> '')
);

CREATE TABLE routine_weekdays (
    routine_id INTEGER NOT NULL REFERENCES routines (id) ON DELETE CASCADE,
    weekday    INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    PRIMARY KEY (routine_id, weekday)
);

-- 実行の記録: どの日課を、どの日にやったか。行がなければその日は未完了(リセットの処理は要らない)
-- 日課を消すと記録も消える(物理削除)
CREATE TABLE routine_checks (
    routine_id INTEGER NOT NULL REFERENCES routines (id) ON DELETE CASCADE,
    day        TEXT    NOT NULL CHECK (day IS date(day)),
    PRIMARY KEY (routine_id, day)
);
