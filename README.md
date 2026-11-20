# TechRamen 2026 Conference LT

「TechRamen 2026 Conference」でLT登壇するネタのコード置き場。
プロポーザルは ./PROPOSAL.md にあります。

## 使い方

```bash
uv sync

# テストガチャ（考慮漏れを探す）。結果は gacha-result.json にも出る
uv run pytest tests/test_gacha.py
TGDD_TEST_DATA=2026-11-20-00.json uv run pytest tests/test_gacha.py  # テストデータを指定する

# テストの仕組みのテストと、再発を見つけるテスト
uv run pytest --ignore=tests/test_gacha.py

# 通知の文面を確かめる（投稿はしない）
uv run python tools/notify_discord.py gacha-result.json --dry-run

# テストデータの検査
uv run python tools/validate_test_data.py tests/test_data/2026-11-20-00.json
```

## ファイル説明

| ファイル | 内容 |
|---|---|
| `target.py` | テスト対象のモジュール |
| `tests/test_gacha.py` | 考慮漏れを見つけるためのテスト。テストデータ 1 ファイルを読んで実行する |
| `tests/test_regression.py` | 発見・修正した考慮漏れの再発を見つけるためのテスト |
| `tests/test_helpers.py` | テストの仕組み（比較・検査・集計）そのもののテスト |
| `tests/helpers.py`・`tests/conftest.py` | XML の比較、テストデータの検査、結果の集計 |
| `tests/test_data/YYYY-MM-DD-hh.json` | Claude のスケジュールタスクで作成されるテストデータ |
| `tests/test_tools.py` | CI で使うツールのテスト |
| `tools/validate_test_data.py` | テストデータの検査 |
| `tools/check_pr_changes.py` | プルリクエストの変更が、テストデータの追加 1 つだけであることの確認 |
| `tools/notify_discord.py` | テストガチャの結果を Discord に通知する |
| `.github/workflows/ci.yml` | ふだんの変更の確認（テストガチャ以外のテスト） |
| `.github/workflows/gacha.yml` | テストガチャの実行（手動）と通知 |
| `.github/workflows/validate-test-data.yml` | `claude-*` ブランチのテストデータの検査と自動マージ |
| `docs/test_data.schema.json` | テストデータの JSON Schema |
| `docs/slide-ir.md` | SlideIR の Page 型 |
| `docs/plans/` | 実装計画書 |

## GitHub の設定

| 設定 | 内容 |
|---|---|
| Secrets の `DISCORD_WEBHOOK_URL` | 通知先の Discord の Webhook の URL |
| Settings → Actions → General → Workflow permissions | 「Read and write permissions」にする（自動マージのため） |
| Settings → General → Pull Requests | 「Allow squash merging」を有効にする |
