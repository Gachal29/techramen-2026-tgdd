"""テストデータの検査

使い方: python tools/validate_test_data.py tests/test_data/2026-11-20-09.json [...]

問題があれば内容を表示して、終了コード 1 で終わる
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from helpers import validate_test_data  # noqa: E402

FILE_NAME = re.compile(r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])-([01]\d|2[0-3])\.json")


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not FILE_NAME.fullmatch(path.name):
        errors.append("ファイル名が YYYY-MM-DD-hh.json の形ではない")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [*errors, f"JSON として読めない（{error}）"]
    schema = json.loads((ROOT / "docs" / "test_data.schema.json").read_text(encoding="utf-8"))
    return [*errors, *validate_test_data(data, schema)]


def main(arguments: list[str]) -> int:
    if not arguments:
        print(__doc__)
        return 2
    failed = False
    for argument in arguments:
        errors = validate_file(Path(argument))
        if errors:
            failed = True
            print(f"NG {argument}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"OK {argument}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
