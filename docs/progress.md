# 進捗記録

作業を中断・再開するときの引き継ぎ用。**再開したらまずここを読む。** 区切りごとに更新する。

## 最終更新: 2026-11-16
- `main` は全テスト緑(213 件)。作業中のブランチなし
- 再開時の確認コマンド:
  ```powershell
  cd C:\development\pda
  .\.venv\Scripts\Activate.ps1
  pytest -q            # 213 passed のはず
  git log --oneline --graph -10
  ```

## できたもの
| 層 | ToDo | 予定 | メモ | ニュース |
|---|---|---|---|---|
| ドメイン(`src/pda/domain/`) | ✅ `task.py` | ✅ `event.py` | ✅ `memo.py` | ⬜ 未着手 |
| スキーマ(`src/pda/db/migrations/0001_initial.sql`) | ✅ | ✅ | ✅(`memos`・`tags`・`memo_tags`) | ⬜ `0002` で追加予定 |
| リポジトリ(`src/pda/db/`) | ✅ `task_repository.py` | ✅ `event_repository.py` | ✅ `memo_repository.py` | ⬜ |
| Web 画面(`src/pda/web/`) | ✅ 一覧・追加・完了・完了済み・削除(編集は未) | ⬜ | ⬜ | ⬜ |

基盤:
- マイグレーションの仕組み `src/pda/db/migrate.py`(1 ファイル = 1 トランザクション、適用前バックアップ、番号検査)
- マイグレーションの凍結検査 `tests/integration/test_migration_freeze.py`(`0001`・`0002` 登録済み)
- 開発サーバー: `uvicorn pda.web.app:create_app_from_env --factory --reload`(DB は `data/pda.db`。git 管理外)
- ER 図 `docs/db/er.md`(閲覧用ページ: https://claude.ai/artifact/HVduwaWzGh3SGvVeWrv6uS)

## 直近にやったこと(2026-11-16)
- メモのリポジトリ `MemoRepository`(保存は `memos`・`tags`・`memo_tags` を 1 トランザクション。使われなくなったタグも残す)
- ToDo の Web 画面(`feature/web-todo`): 一覧(優先度順・超過の印)/ 追加(詳細つき)/ 完了 / 完了済み一覧(作成日時の新しい順)と未完了に戻す / 削除(ブラウザ標準の確認ポップアップ・物理削除)
- マイグレーション `0002`: `tasks.detail`(「なし」は空文字)
- 決定の詳細は `docs/requirements.md`(2026-11-16 の行)

## その後の候補(順番は未決定)
- ToDo の編集(タイトル・優先度・期限・詳細の変更)
- 予定 → メモの Web 画面、最後に「今日」のまとめ画面(この順は決定済み)
- タグの候補一覧を返す処理(タグを残すと決めた理由が「候補に出すため」なので、Web 画面で必要になったら作る。並び順は要相談)
- ニュースのドメイン(記事の形、IT × 物理・数学の絞り込み、モック要約)→ `0002` でニュースのテーブル追加
- Web 画面(FastAPI + Jinja2)
- GitHub へ push(リモート未作成。公開/非公開をユーザーと決めてから)

## 確認待ち(⚠ が付いている項目)
| 項目 | 場所 | 現状 |
|---|---|---|
| このアプリの役割の文面 | `CLAUDE.md` / `docs/requirements.md` のミッション節 | Claude の案のまま |
| タグの英字の大文字小文字を区別するか | `docs/requirements.md` のメモ節 | 区別する(`AI` と `ai` は別)で実装済み。変えるならスキーマの照合順序も変わる |

## これまでに決めた進め方(詳細は CLAUDE.md)
- TDD(Red → Green → Refactor)。Red では「未実装が理由で失敗している」ことまで確認する
- GitHub Flow。`main` に直接コミットしない。`種類/内容` のブランチ → `--no-ff` でマージ → マージ後に main でテスト → ブランチ削除
- 業務ルールは勝手に決めず質問してから。決めたこと・やらないことは `docs/requirements.md` に日付と理由付きで残す
- main にマージしたマイグレーションは凍結(書き換えない)。変更は新しい番号で追加
- 費用は上限(生活を圧迫しない)、品質はその中で最大化。要約は当面モック(API を呼ばない)
