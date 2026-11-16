# 進捗記録

作業を中断・再開するときの引き継ぎ用。**再開したらまずここを読む。** 区切りごとに更新する。

## 最終更新: 2026-11-16
- `main` は全テスト緑(363 件)。作業中のブランチなし
- 再開時の確認コマンド:
  ```powershell
  cd C:\development\pda
  .\.venv\Scripts\Activate.ps1
  pytest -q            # 363 passed のはず
  git log --oneline --graph -10
  ```

## できたもの
| 層 | ToDo | 予定 | メモ | ニュース |
|---|---|---|---|---|
| ドメイン(`src/pda/domain/`) | ✅ `task.py` | ✅ `event.py` | ✅ `memo.py` | ✅ `article.py`(記事・フィード) |
| スキーマ(`src/pda/db/migrations/0001_initial.sql`) | ✅ | ✅ | ✅(`memos`・`tags`・`memo_tags`) | ✅ `0003`(`feeds`・`articles`) |
| リポジトリ(`src/pda/db/`) | ✅ `task_repository.py` | ✅ `event_repository.py` | ✅ `memo_repository.py` | ✅ `article_repository.py` |
| Web 画面(`src/pda/web/`) | ✅ 一覧・追加・完了・完了済み・削除(編集は未) | ⬜ | ⬜ | ⬜ |

基盤:
- マイグレーションの仕組み `src/pda/db/migrate.py`(1 ファイル = 1 トランザクション、適用前バックアップ、番号検査)
- マイグレーションの凍結検査 `tests/integration/test_migration_freeze.py`(`0001`〜`0004` 登録済み)
- ニュースの処理(`src/pda/news/`): 絞り込みと優先順位 `filter.py` / 要約器 `summarizer.py`(モック)/ RSS・Atom の解析と取得 `fetcher.py` / 日次処理 `daily.py`
- ニュースの入口 `python -m pda.news_job`、設定 `src/pda/config.py`(フィード: Qiita・Zenn の数学・物理系タグ、arXiv quant-ph / cs.IT / cs.LG)
- キーワードは DB で管理し、画面 `/keywords` で追加・削除(`0004`)
- ⚠ 開発サーバーの `--reload` は `.py` しか監視しない。マイグレーション(`.sql`)を足したらサーバーを再起動する
- 開発サーバー: `uvicorn pda.web.app:create_app_from_env --factory --reload`(DB は `data/pda.db`。git 管理外)
- ER 図 `docs/db/er.md`(閲覧用ページ: https://claude.ai/artifact/HVduwaWzGh3SGvVeWrv6uS)

## 直近にやったこと(2026-11-16)
- メモのリポジトリ、ToDo の Web 画面(詳細つき・完了済み・確認ポップアップで物理削除)、`0002`(`tasks.detail`)
- ニュースのビジネスロジック一式(`feature/news-domain` → `news-storage` → `news-fetch`)。決定は `docs/requirements.md` のニュース節
  - 1 日の要約上限は「その日の合計」で数える(同じ日に何度実行しても超えない。本物の API に切り替えたときの費用のため)
  - news は db を知らない。保存先は `pda.news.daily.ArticleStore` Protocol。組み立ては `pda/news_job.py`
- フィードを設定(Qiita・Zenn・arXiv。Mathlog は RSS がないので外す)
- キーワードを DB 管理にして編集画面 `/keywords` を追加(`feature/keywords-db`)。大文字小文字だけの違いは同じ語として重複を断る

## その後の候補(順番は未決定)
- 平日に `python -m pda.news_job` を本物で動かし、arXiv の件数・概要文の形を確かめる(土日は arXiv が空)
- フィードも DB 管理にするか(今の正本は `config.FEEDS`。`feeds` テーブルは写し)
- ニュースの Web 画面(要約済みの記事を優先順位順に)
- 日次処理のスケジューラ(Windows タスクスケジューラ等)
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
| ニュースの絞り込みキーワード | DB(画面 `/keywords` で編集。初期データは `0004`) | Claude の案のまま。使いながら育てる |
| タグの英字の大文字小文字を区別するか | `docs/requirements.md` のメモ節 | 区別する(`AI` と `ai` は別)で実装済み。変えるならスキーマの照合順序も変わる |

## これまでに決めた進め方(詳細は CLAUDE.md)
- TDD(Red → Green → Refactor)。Red では「未実装が理由で失敗している」ことまで確認する
- GitHub Flow。`main` に直接コミットしない。`種類/内容` のブランチ → `--no-ff` でマージ → マージ後に main でテスト → ブランチ削除
- 業務ルールは勝手に決めず質問してから。決めたこと・やらないことは `docs/requirements.md` に日付と理由付きで残す
- main にマージしたマイグレーションは凍結(書き換えない)。変更は新しい番号で追加
- 費用は上限(生活を圧迫しない)、品質はその中で最大化。要約は当面モック(API を呼ばない)
