"""発見・修正した考慮漏れの再発を見つけるためのテスト

test_gacha.py で見つけた考慮漏れを修正したら、そのテストデータを tests/regression_data.json に写す
（形はテストデータと同じ）。ここにあるテストデータは、すべて通らなければならない
"""

import json
from pathlib import Path
from typing import Any

import pytest

import target
from helpers import diff_page_groups, diff_xml, page_id

CASES: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "regression_data.json").read_text(encoding="utf-8")
)

pytestmark = pytest.mark.parametrize("case", CASES, ids=[case["test_data_id"] for case in CASES])


def test_text_to_page_grouper(case: dict[str, Any]) -> None:
    problem = diff_page_groups(case["expected_page_group"], target.text_to_page_grouper(case["input_text"]))
    if problem:
        pytest.fail(problem, pytrace=False)


def test_page_to_slideir_page(case: dict[str, Any]) -> None:
    problems: list[str] = []
    pairs = zip(case["expected_page_group"], case["expected_slideir_page"], strict=True)
    for index, (page_text, expected) in enumerate(pairs, start=1):
        problem = diff_xml(expected, target.page_to_slideir_page(page_text, page_id(expected)))
        if problem:
            problems.append(f"=== {index} ページ目\n{problem}")
    if problems:
        pytest.fail("\n".join(problems), pytrace=False)
