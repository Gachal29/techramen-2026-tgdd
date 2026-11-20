"""テストデータのプルリクエストの変更が、テストデータの追加 1 つだけであることを確かめる

使い方: git diff --name-status --no-renames <base>...<head> | python tools/check_pr_changes.py <ブランチ名>

- ブランチ名は claude-YYYY-MM-DD-hh
- 変更は、tests/test_data/YYYY-MM-DD-hh.json（ブランチ名と同じ日時）の追加 1 つだけ

問題がなければ、追加されたファイルのパスを表示して終了コード 0 で終わる
"""

import re
import sys

BRANCH = re.compile(r"claude-(\d{4}-\d{2}-\d{2}-\d{2})")


def check(branch: str, name_status: str) -> tuple[str | None, list[str]]:
    """(追加されたファイルのパス, 問題の説明の配列) を返す"""
    match = BRANCH.fullmatch(branch)
    if not match:
        return None, [f"ブランチ名が claude-YYYY-MM-DD-hh の形ではない: {branch!r}"]
    expected = f"tests/test_data/{match.group(1)}.json"

    changes = [line.split("\t") for line in name_status.splitlines() if line.strip()]
    if not changes:
        return None, ["変更がない"]
    errors = [
        f"許可されていない変更: {' '.join(change)}"
        for change in changes
        if change != ["A", expected]
    ]
    if errors:
        return None, [*errors, f"許可される変更は {expected} の追加だけ"]
    return expected, []


def main(arguments: list[str]) -> int:
    if len(arguments) != 1:
        print(__doc__)
        return 2
    path, errors = check(arguments[0], sys.stdin.read())
    if errors:
        for error in errors:
            print(f"NG {error}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
