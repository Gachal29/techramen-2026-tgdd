"""すべてのテストデータでテストガチャを実行し、結果をまとめる

使い方: python tools/run_all_gacha.py [--json 結果のファイル] [--verbose]

- tests/test_data/ のファイルを 1 つずつ tests/test_gacha.py に渡して実行する
- 失敗したテストデータがあれば終了コード 1、なければ 0、実行できないファイルがあれば 2
- --verbose を付けると、失敗の内容（期待値と実際の値の差分）も表示する
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def run_file(path: Path) -> dict[str, Any] | None:
    """1 ファイル分の結果。テストを実行できなければ None"""
    with tempfile.TemporaryDirectory() as directory:
        result_file = Path(directory) / "result.json"
        env = {**os.environ, "TGDD_TEST_DATA": str(path), "TGDD_RESULT_FILE": str(result_file)}
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_gacha.py", "-q", "-p", "no:cacheprovider"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode not in (0, 1):
            print(completed.stdout[-2000:], completed.stderr[-2000:], file=sys.stderr)
            return None
        if not result_file.exists():  # すべて除外されている
            return {"test_data_file": path.name, "total": 0, "failed_test_data": 0, "failed": []}
        return json.loads(result_file.read_text(encoding="utf-8"))


def main(arguments: list[str]) -> int:
    verbose = "--verbose" in arguments
    output = arguments[arguments.index("--json") + 1] if "--json" in arguments else None
    results: list[dict[str, Any]] = []
    broken: list[str] = []
    for path in sorted((ROOT / "tests" / "test_data").glob("*.json")):
        result = run_file(path)
        if result is None:
            broken.append(path.name)
            print(f"{path.name}: 実行できなかった")
            continue
        results.append(result)
        print(f"{path.name}: {result['total']} 件中 {result['failed_test_data']} 件が失敗")
        for entry in result["failed"]:
            print(f"  - {entry['test_data_id']}: {entry['target']}")
            if verbose:
                print("\n".join(f"      {line}" for line in entry["message"].splitlines()))
    total = sum(result["total"] for result in results)
    failed = sum(result["failed_test_data"] for result in results)
    print(f"合計: {total} 件中 {failed} 件が失敗")
    if output:
        Path(output).write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if broken:
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
