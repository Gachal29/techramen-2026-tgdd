"""テストガチャの結果の集計

gacha のマークが付いたテストケースの結果を集め、最後に JSON に書き出す。
書き出す先は環境変数 TGDD_RESULT_FILE（省略時は gacha-result.json）
"""

import json
import os
from pathlib import Path

import pytest

_results: list[dict[str, str]] = []
_data_file: list[str] = []


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    marker = item.get_closest_marker("gacha")
    if marker is None or call.when != "call":
        return
    case = item.callspec.params["case"]  # type: ignore[attr-defined]
    if not _data_file:
        _data_file.append(item.module.DATA_FILE.name)  # type: ignore[attr-defined]
    _results.append(
        {
            "test_data_id": case["test_data_id"],
            "target": marker.kwargs["target"],
            "outcome": "passed" if call.excinfo is None else "failed",
            "message": "" if call.excinfo is None else str(call.excinfo.value),
        }
    )


def pytest_sessionfinish(session: pytest.Session) -> None:
    if not _results:
        return
    failed = [
        {key: result[key] for key in ("test_data_id", "target", "message")}
        for result in _results
        if result["outcome"] == "failed"
    ]
    summary = {
        "test_data_file": _data_file[0],
        "total": len({result["test_data_id"] for result in _results}),
        "failed_test_data": len({result["test_data_id"] for result in failed}),
        "failed": failed,
    }
    path = Path(os.environ.get("TGDD_RESULT_FILE", "gacha-result.json"))
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    if not _results:
        return
    failed = [result for result in _results if result["outcome"] == "failed"]
    total = len({result["test_data_id"] for result in _results})
    terminalreporter.section("テストガチャの結果")
    terminalreporter.write_line(f"テストデータ: {_data_file[0]}（{total} 件）")
    if not failed:
        terminalreporter.write_line("考慮漏れは見つからなかった")
        return
    terminalreporter.write_line(f"考慮漏れの候補: {len({r['test_data_id'] for r in failed})} 件")
    for result in failed:
        terminalreporter.write_line(f"  - {result['test_data_id']}: {result['target']}")
