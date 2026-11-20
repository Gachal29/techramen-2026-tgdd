"""テストガチャの結果を Discord に通知する

使い方: python tools/notify_discord.py gacha-result.json [--dry-run]

- 失敗したテストデータがなければ、何も投稿しない
- Webhook の URL は環境変数 DISCORD_WEBHOOK_URL、実行結果への URL は RUN_URL で渡す
- --dry-run を付けると、投稿せずに文面を表示する
- 環境変数 GITHUB_STEP_SUMMARY があれば、同じ内容を Actions の実行結果の画面にも書く
"""

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

LIMIT = 2000  # Discord のメッセージの上限（文字数）


def build_message(result: dict[str, Any], run_url: str = "") -> str | None:
    """通知の文面。失敗がなければ None"""
    failed = result["failed"]
    if not failed:
        return None
    targets: dict[str, list[str]] = {}
    for entry in failed:
        targets.setdefault(entry["test_data_id"], []).append(entry["target"])

    head = [
        "**テストガチャで考慮漏れの候補が見つかりました**",
        f"テストデータ: `{result['test_data_file']}`",
        f"失敗: {len(targets)} / {result['total']} 件",
    ]
    tail = [run_url] if run_url else []
    lines = [f"- `{name}`: {'・'.join(f'`{target}`' for target in names)}" for name, names in targets.items()]

    # 上限を超えるときは、一覧を途中で切って残りの件数を書く
    shown = list(lines)
    while shown and len("\n".join([*head, *shown, f"ほか {len(lines)} 件", *tail])) > LIMIT:
        shown.pop()
    rest = len(lines) - len(shown)
    return "\n".join([*head, *shown, *([f"ほか {rest} 件"] if rest else []), *tail])


def post(webhook_url: str, message: str) -> None:
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps({"content": message}).encode("utf-8"),
        # 既定の User-Agent（Python-urllib）は Discord に拒否されることがある
        headers={"Content-Type": "application/json", "User-Agent": "tgdd-gacha-notifier"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30):
        pass


def main(arguments: list[str]) -> int:
    dry_run = "--dry-run" in arguments
    paths = [argument for argument in arguments if not argument.startswith("--")]
    if len(paths) != 1:
        print(__doc__)
        return 2
    result = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    message = build_message(result, os.environ.get("RUN_URL", ""))

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        text = message or f"テストデータ `{result['test_data_file']}`（{result['total']} 件）: 考慮漏れは見つからなかった"
        with open(summary, "a", encoding="utf-8") as file:
            file.write(text + "\n")

    if message is None:
        print("失敗したテストデータはない。通知しない")
        return 0
    if dry_run:
        print(message)
        return 0
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL が設定されていないため、通知できない", file=sys.stderr)
        return 1
    try:
        post(webhook_url, message)
    except OSError as error:
        # URL を含む可能性があるので、例外の中身は表示しない
        print(f"Discord への通知に失敗した（{type(error).__name__}）", file=sys.stderr)
        return 1
    print("Discord に通知した")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
