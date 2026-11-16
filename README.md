# PDA

自分専用の PDA(Personal Digital Assistant)Web アプリ。
毎日の **日課・予定・ToDo・メモ** をひとつの場所で扱い、物理・数学・IT が交わる分野の **ニュース** を RSS で集めて要約して並べる。

- 利用者は自分 1 人。PC のブラウザで使い、スマホからは Tailscale 経由で使う(インターネットには公開しない)
- 要件・決定事項の正本は [`docs/requirements.md`](docs/requirements.md)、作業の引き継ぎは [`docs/progress.md`](docs/progress.md)

## できること
| 画面 | URL | 内容 |
|---|---|---|
| 今日 | `/today`(最初の画面) | 今日の曜日の **日課** をチェック(進み具合つき)と、**今日の予定** |
| ToDo | `/tasks` | 優先度順の一覧(期限超過の印)、追加・編集・完了・完了済み一覧・削除 |
| 予定 | `/events` | 今日から先を日ごとに表示(終日・時刻付き・日をまたぐ予定)、過去の予定 |
| メモ | `/memos` | 2 列のカード、検索、タグの絞り込み、作成・編集 |
| ニュース | `/news` | 要約済みの記事を要約した日ごと・優先順位順に表示、既読の管理 |
| キーワード | `/keywords` | ニュースの絞り込みキーワードの追加・削除(ニュースの画面から開く) |
| 日課の編集 | `/routines` | 日課(曜日を選べる)の追加・編集・削除(今日の画面から開く) |

## 動かすのに必要なもの
- Windows(開発と動作確認は Windows 11 + PowerShell で行っている)
- Python 3.12 以上
- git

## 環境構築
```powershell
git clone https://github.com/YANASAN-eng/PDA-application.git
cd PDA-application

python -m venv .venv                  # 仮想環境を作る(.venv/ は git 管理外)
.\.venv\Scripts\Activate.ps1          # 仮想環境に入る
pip install -e ".[dev]"               # アプリとテスト用の依存をインストール

pytest -q                             # 全テストが通ることを確認する
```

PowerShell でスクリプトの実行が止められる場合は、`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` を一度実行するか、`Activate.ps1` を使わずに `.\.venv\Scripts\python.exe -m pytest` のように直接呼ぶ。

## 使い方
### Web 画面を起動する
```powershell
uvicorn pda.web.app:create_app_from_env --factory --reload
```
ブラウザで http://127.0.0.1:8000/ を開く。

- DB は `data/pda.db`(SQLite)。初回の起動で自動的に作られる。環境変数 `PDA_DB` で場所を変えられる
- 起動するたびに、未適用のマイグレーション(`src/pda/db/migrations/`)を当てる。既存の DB に当てるときは、事前に `data/pda.<日時>.bak` へバックアップを取る
- `127.0.0.1` だけで待ち受けるので、ほかの機器からは直接つながらない
- ⚠ `--reload` は `.py` の変更しか見ていない。マイグレーション(`.sql`)を足したらサーバーを再起動する

### ニュースを取得する(1 日 1 回)
```powershell
python -m pda.news_job
```
`src/pda/config.py` の `FEEDS` の RSS を取得し、DB のキーワード(画面 `/keywords` で編集)で絞り込み、1 日の上限(既定 30 件)まで要約して保存する。

- 要約は **モック**(概要文の先頭 200 文字)。Claude API は呼ばないので費用はかからない
- 同じ日に何度実行しても、要約の件数はその日の合計で上限まで
- 取得に失敗したフィードはログに残し、ほかのフィードの処理は続ける
- arXiv の RSS は土日は空

### 設定(`src/pda/config.py`)
| 項目 | 内容 |
|---|---|
| `FEEDS` | 取得する RSS(Qiita・Zenn の数学・物理系タグ、arXiv の quant-ph / cs.IT / cs.LG) |
| `DAILY_SUMMARY_LIMIT` | 1 日に要約する件数の上限 |
| `SUMMARIZER` | 要約器。今は `"mock"` だけ |
| `MOCK_SUMMARY_MAX_CHARS` | モック要約の文字数 |

キーワードは設定ファイルではなく DB にある(画面で編集する)。初期データは `0004_add_keywords.sql`。

### スマホから使う(Tailscale)
インターネットには公開せず、自分の端末だけをつなぐ Tailscale を使う。

1. PC とスマホに Tailscale を入れ、同じアカウントでログインする
2. Tailscale の管理画面の DNS で MagicDNS と HTTPS Certificates を有効にする
3. PC で Web 画面を起動したうえで、次を実行する(一度でよい。設定は残る)
   ```powershell
   tailscale serve --bg 8000
   ```
4. スマホのブラウザで `https://<PC の名前>.<tailnet 名>.ts.net/` を開く(`tailscale serve status` で確認できる)

- やめるときは `tailscale serve --https=443 off`
- PC が起動していて、Web 画面が動いているときだけ使える
- ⚠ Funnel(インターネットへの公開)は使わない。アプリには認証がないので、一般公開する前に認証とフォームの偽造対策を必ず作ること

### データのバックアップ
`data/` は git の管理外(個人のデータを履歴に残さないため)。必要に応じて `data/pda.db` を別の場所にコピーしておく。

## 開発
### 構成
```
src/pda/
├─ domain/     エンティティと純粋なロジック(I/O なし。どこにも依存しない)
├─ db/         SQLite のリポジトリとマイグレーション(migrations/*.sql)
├─ news/       RSS の取得・解析、絞り込みと優先順位、要約器、日次処理
├─ web/        FastAPI のルート・テンプレート・ページ分け
├─ config.py   設定
└─ news_job.py ニュースの日次処理の入口
tests/
├─ unit/         domain・news の単体テスト、依存の向きの検査
├─ integration/  リポジトリ(実 SQLite)・Web(TestClient)・マイグレーションのテスト
└─ fixtures/     RSS / Atom のサンプル
docs/
├─ requirements.md  要件・決定事項・やらないこと(正本)
├─ progress.md      進捗と次にやること
├─ db/er.md         ER 図(正本)
└─ design/          画面のモックアップ(参照用)
```
依存の向き: `web → (domain, db, news)`、`db → domain`、`news → domain`。`tests/unit/test_architecture.py` が import を検査して守る。

### 進め方
詳しくは [`CLAUDE.md`](CLAUDE.md)。
- **TDD**(Red → Green → Refactor)。テストより先に本番コードを書かない
- テストは外部(ネットワーク)に出ない。`tests/conftest.py` が全テストで外部への接続をエラーにする
- **GitHub Flow**。`main` に直接コミットせず、`種類/内容` のブランチで作業して `--no-ff` でマージする
- **マイグレーションは追加だけ**。`main` に入ったものは凍結し、`tests/integration/test_migration_freeze.py` がチェックサムで検査する
- 業務ルールは利用者と相談して決め、決めたこと・やらないことは `docs/requirements.md` に日付と理由つきで残す

### よく使うコマンド
```powershell
pytest                     # 全テスト
pytest tests/unit -q       # 単体テストだけ
pytest -k メモ             # 名前で絞る
```

## 技術
Python 3.12 / FastAPI + Jinja2(サーバー側で HTML を描画)/ SQLite(標準ライブラリ `sqlite3`、ORM なし)/ feedparser / pytest
