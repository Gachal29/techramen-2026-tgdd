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
uv run pytest tests/test_helpers.py tests/test_regression.py

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
| `tools/validate_test_data.py` | テストデータの検査 |
| `docs/test_data.schema.json` | テストデータの JSON Schema |
| `docs/slide-ir.md` | SlideIR の Page 型 |
| `docs/plans/` | 実装計画書 |
