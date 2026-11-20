"""考慮漏れを見つけるためのテスト（テストガチャ）

テストデータ 1 ファイルを読み、1 件ごとに分割と変換を別々に確かめる。

- TGDD_TEST_DATA: テストデータのファイル（パスか、tests/test_data/ の中のファイル名）。
  省略時は tests/test_data/ の中でファイル名が最も新しいもの
- TGDD_TARGET_MODULE: テスト対象のモジュール名（省略時は target）。テストの仕組みのテストで差し替える
"""

import importlib
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from helpers import diff_page_groups, diff_xml, page_id

DATA_DIR = Path(__file__).parent / "test_data"
_FILE_NAME = re.compile(r"\d{4}-\d{2}-\d{2}-\d{2}\.json")


def _data_file() -> Path | None:
    specified = os.environ.get("TGDD_TEST_DATA")
    if specified:
        path = Path(specified)
        return path if path.exists() else DATA_DIR / specified
    files = sorted(path for path in DATA_DIR.glob("*.json") if _FILE_NAME.fullmatch(path.name))
    return files[-1] if files else None


DATA_FILE = _data_file()
if DATA_FILE is None:
    pytest.skip("テストデータがない", allow_module_level=True)

CASES: list[dict[str, Any]] = json.loads(DATA_FILE.read_text(encoding="utf-8"))

pytestmark = pytest.mark.parametrize("case", CASES, ids=[case["test_data_id"] for case in CASES])


@pytest.fixture(scope="module")
def target() -> Any:
    return importlib.import_module(os.environ.get("TGDD_TARGET_MODULE", "target"))


@pytest.mark.gacha(target="text_to_page_grouper")
def test_text_to_page_grouper(case: dict[str, Any], target: Any) -> None:
    actual = target.text_to_page_grouper(case["input_text"])
    problem = diff_page_groups(case["expected_page_group"], actual)
    if problem:
        pytest.fail(problem, pytrace=False)


@pytest.mark.gacha(target="page_to_slideir_page")
def test_page_to_slideir_page(case: dict[str, Any], target: Any) -> None:
    """分割の期待値を入力にする（分割の考慮漏れを、変換のテストに波及させない）"""
    problems: list[str] = []
    pairs = zip(case["expected_page_group"], case["expected_slideir_page"], strict=True)
    for index, (page_text, expected) in enumerate(pairs, start=1):
        try:
            actual = target.page_to_slideir_page(page_text, page_id(expected))
        except Exception as error:  # noqa: BLE001  1 ページの例外で、残りのページの確認を止めない
            problems.append(f"=== {index} ページ目: 例外 {type(error).__name__}: {error}")
            continue
        problem = diff_xml(expected, actual)
        if problem:
            problems.append(f"=== {index} ページ目\n{problem}")
    if problems:
        pytest.fail("\n".join(problems), pytrace=False)
