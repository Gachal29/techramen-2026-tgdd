# TechRamen 2026 Conference LT

「TechRamen 2026 Conference」でLT登壇するネタのコード置き場。
プロポーザルは ./PROPOSAL.md にあります。

## 使い方

```bash
uv sync

# テストガチャ（考慮漏れを探す）。結果は gacha-result.json にも出る
uv run pytest tests/test_gacha.py
TGDD_TEST_DATA=2026-11-20-00.json uv run pytest tests/test_gacha.py  # テストデータを指定する
uv run python tools/run_all_gacha.py --verbose   # すべてのテストデータで実行する

# テストの仕組みのテストと、再発を見つけるテスト
uv run pytest --ignore=tests/test_gacha.py

# 通知の文面を確かめる（投稿はしない）
uv run python tools/notify_discord.py gacha-result.json --dry-run

# テストデータの検査
uv run python tools/validate_test_data.py tests/test_data/2026-11-20-00.json
```

## スライドをつくる

LT のスライドは、作業メモ（`slide-demo/memo.md`）から `target.py` でつくる。

```bash
git pull origin main
uv run python slide-demo/build.py
open slide-demo/dist/index.html
```

- `target.py` を変更したコミットごとに 1 つの版ができる。考慮漏れの修正がマージされるたびに、版が増える
- `slide-demo/dist/slides/` に、版ごとの SlideIR（`.ltool`）と生成の記録（`.report.json`）ができる
- 変換できなかったページは、原文をそのまま載せた代わりのスライドになる

| キー | 動作 |
|---|---|
| `←` `→` | ページ送り |
| `↑` `↓` | `target.py` の版を切り替える |
| `s` | 原文（作業メモ）を並べて表示する |
| `x` | SlideIR の XML を表示する |
| `g` | 版ごとの推移（テストガチャの通過率、原文の再現率） |
| `f` | 全画面 |

URL の `?v=<コミット>#<ページ>` で、版とページを指定できる。

## ファイル説明

| ファイル | 内容 |
|---|---|
| `target.py` | テスト対象のモジュール |
| `tests/test_gacha.py` | 考慮漏れを見つけるためのテスト。テストデータ 1 ファイルを読んで実行する |
| `tests/test_regression.py`・`tests/regression_data.json` | 発見・修正した考慮漏れの再発を見つけるためのテストと、そのデータ |
| `tests/excluded_test_data.json` | 期待値の誤りと判断して、テストガチャから除外するテストデータ |
| `tests/test_helpers.py` | テストの仕組み（比較・検査・集計）そのもののテスト |
| `tests/helpers.py`・`tests/conftest.py` | XML の比較、テストデータの検査、結果の集計 |
| `tests/test_data/YYYY-MM-DD-hh.json` | Claude のスケジュールタスクで作成されるテストデータ |
| `tests/test_tools.py` | CI で使うツールのテスト |
| `tools/validate_test_data.py` | テストデータの検査 |
| `tools/check_pr_changes.py` | プルリクエストの変更が、テストデータの追加 1 つだけであることの確認 |
| `tools/notify_discord.py` | テストガチャの結果を Discord に通知する |
| `.github/workflows/ci.yml` | ふだんの変更の確認（テストガチャ以外のテスト） |
| `.github/workflows/gacha.yml` | テストガチャの実行と通知。テストデータのマージの後に自動で動く。手動でも実行できる |
| `.github/workflows/validate-test-data.yml` | `claude-*` ブランチのテストデータの検査と自動マージ。マージの後にテストガチャを呼び出す |
| `docs/test_data.schema.json` | テストデータの JSON Schema |
| `tools/run_all_gacha.py` | すべてのテストデータでテストガチャを実行する |
| `docs/test-data-generation.md` | テストデータを作るスケジュールタスクへの指示 |
| `docs/fix-instructions.md` | 考慮漏れを修正するスケジュールタスクへの指示 |
| `docs/slide-ir.md` | SlideIR の Page 型 |
| `slide-demo/` | 作業メモからスライドをつくる仕組みと、LT の原稿（`memo.md`） |
| `tests/test_slide_demo.py` | スライドをつくる仕組みのテスト |
| `docs/plans/` | 実装計画書 |

## GitHub の設定

| 設定 | 内容 |
|---|---|
| Secrets の `DISCORD_WEBHOOK_URL` | 通知先の Discord の Webhook の URL |
| Settings → Actions → General → Workflow permissions | 「Read and write permissions」にする（自動マージのため） |
| Settings → General → Pull Requests | 「Allow squash merging」を有効にする |
