"""1 つの版の target.py を実行する（build.py から別のプロセスで呼ばれる）

使い方: python runner.py <target.py のパス> <作業メモのパス> <結果を書く JSON のパス>

- 作業メモを分割し、ページごとに変換する。あわせて、すべてのテストデータでテストガチャを実行する
- 例外や時間切れがあっても止まらず、起きたことを結果に書く
"""

import contextlib
import importlib.util
import io
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from helpers import diff_page_groups, diff_xml, page_id  # noqa: E402

LIMIT_SECONDS = int(os.environ.get("TGDD_CALL_LIMIT", "5"))  # 1 回の呼び出しの上限


class _Timeout(Exception):
    pass


def _on_alarm(signum: int, frame: Any) -> None:
    raise _Timeout(f"{LIMIT_SECONDS} 秒以内に終わらなかった")


def call(function: Any, *arguments: Any) -> tuple[bool, Any]:
    """(成功したか, 戻り値か例外の説明)。標準出力への出力は捨てる"""
    signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(LIMIT_SECONDS)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return True, function(*arguments)
    except KeyboardInterrupt:
        raise
    except BaseException as error:  # noqa: BLE001  テスト対象のどんな失敗でも止まらない
        return False, f"{type(error).__name__}: {error}"
    finally:
        signal.alarm(0)


def assign_ids(pages: list[str]) -> list[str]:
    """`# ` で始まるページは cover、ほかは現れた順に p1・p2・…"""
    ids: list[str] = []
    number = 0
    for page in pages:
        first = next((line for line in page.splitlines() if line.strip()), "")
        if first.startswith("# "):
            ids.append("cover")
        else:
            number += 1
            ids.append(f"p{number}")
    return ids


def convert_memo(target: Any, memo: str) -> dict[str, Any]:
    ok, grouped = call(target.text_to_page_grouper, memo)
    if ok and not (isinstance(grouped, list) and all(isinstance(page, str) for page in grouped)):
        ok, grouped = False, f"戻り値が文字列の配列ではない: {grouped!r}"[:500]
    if not ok:
        return {"group_error": grouped, "pages": []}
    pages = []
    for text, identifier in zip(grouped, assign_ids(grouped)):
        ok, result = call(target.page_to_slideir_page, text, identifier)
        if ok and not isinstance(result, str):
            ok, result = False, f"戻り値が文字列ではない: {result!r}"[:500]
        pages.append({"text": text, "id": identifier, "ok": ok, "result": result})
    return {"group_error": None, "pages": pages}


def run_gacha(target: Any) -> dict[str, int]:
    """現在のすべてのテストデータ（除外を除く）のうち、分割と変換の両方が通った件数"""
    excluded_file = ROOT / "tests" / "excluded_test_data.json"
    excluded = (
        {entry["test_data_id"] for entry in json.loads(excluded_file.read_text(encoding="utf-8"))}
        if excluded_file.exists()
        else set()
    )
    total = passed = 0
    for path in sorted((ROOT / "tests" / "test_data").glob("*.json")):
        for case in json.loads(path.read_text(encoding="utf-8")):
            if case["test_data_id"] in excluded:
                continue
            total += 1
            ok, grouped = call(target.text_to_page_grouper, case["input_text"])
            if not ok or diff_page_groups(case["expected_page_group"], grouped) is not None:
                continue
            for text, expected in zip(case["expected_page_group"], case["expected_slideir_page"]):
                ok, result = call(target.page_to_slideir_page, text, page_id(expected))
                if not ok or diff_xml(expected, result) is not None:
                    break
            else:
                passed += 1
    return {"total": total, "passed": passed}


def main(arguments: list[str]) -> int:
    target_path, memo_path, output_path = arguments
    try:
        spec = importlib.util.spec_from_file_location("versioned_target", target_path)
        assert spec and spec.loader
        target = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(target)
        for name in ("text_to_page_grouper", "page_to_slideir_page"):
            if not callable(getattr(target, name, None)):
                raise AttributeError(f"{name} がない")
    except BaseException as error:  # noqa: BLE001
        result: dict[str, Any] = {"load_error": f"{type(error).__name__}: {error}"}
    else:
        result = {"load_error": None, **convert_memo(target, Path(memo_path).read_text(encoding="utf-8"))}
        result["gacha"] = run_gacha(target)
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
