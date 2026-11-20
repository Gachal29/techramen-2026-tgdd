"""CI で使うツール（通知、プルリクエストの変更の確認）のテスト"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import check_pr_changes  # noqa: E402
import notify_discord  # noqa: E402

# -- 通知 --


def _result(failed: list[tuple[str, str]], total: int = 5) -> dict[str, Any]:
    return {
        "test_data_file": "2026-11-20-09.json",
        "total": total,
        "failed_test_data": len({name for name, _ in failed}),
        "failed": [{"test_data_id": name, "target": target, "message": "x"} for name, target in failed],
    }


def test_no_message_without_failures():
    assert notify_discord.build_message(_result([])) is None


def test_message_lists_failed_test_data_with_targets():
    message = notify_discord.build_message(
        _result([("a1", "text_to_page_grouper"), ("a2", "page_to_slideir_page"), ("a1", "page_to_slideir_page")]),
        "https://example.com/run/1",
    )
    assert message is not None
    assert "`2026-11-20-09.json`" in message
    assert "失敗: 2 / 5 件" in message
    assert "- `a1`: `text_to_page_grouper`・`page_to_slideir_page`" in message
    assert "- `a2`: `page_to_slideir_page`" in message
    assert message.endswith("https://example.com/run/1")


def test_long_message_is_cut_within_limit():
    failed = [(f"test-data-{index:04}", "page_to_slideir_page") for index in range(200)]
    message = notify_discord.build_message(_result(failed, total=200), "https://example.com/run/1")
    assert message is not None
    assert len(message) <= notify_discord.LIMIT
    assert "失敗: 200 / 200 件" in message
    assert "ほか " in message
    assert message.endswith("https://example.com/run/1")


def _write(tmp_path: Path, result: dict[str, Any]) -> str:
    path = tmp_path / "gacha-result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    return str(path)


def test_main_does_not_post_without_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    posted: list[str] = []
    monkeypatch.setattr(notify_discord, "post", lambda url, message: posted.append(message))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.com/hook")
    assert notify_discord.main([_write(tmp_path, _result([]))]) == 0
    assert posted == []


def test_main_posts_failures_and_writes_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    posted: list[tuple[str, str]] = []
    summary = tmp_path / "summary.md"
    monkeypatch.setattr(notify_discord, "post", lambda url, message: posted.append((url, message)))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.com/hook")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert notify_discord.main([_write(tmp_path, _result([("a1", "text_to_page_grouper")]))]) == 0
    assert len(posted) == 1
    assert posted[0][0] == "https://example.com/hook"
    assert "`a1`" in posted[0][1]
    assert "`a1`" in summary.read_text(encoding="utf-8")


def test_main_fails_without_webhook_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert notify_discord.main([_write(tmp_path, _result([("a1", "text_to_page_grouper")]))]) == 1


def test_main_fails_without_leaking_url_when_post_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    def fail(url: str, message: str) -> None:
        raise OSError(f"cannot connect to {url}")

    monkeypatch.setattr(notify_discord, "post", fail)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.com/secret-hook")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert notify_discord.main([_write(tmp_path, _result([("a1", "text_to_page_grouper")]))]) == 1
    captured = capsys.readouterr()
    assert "secret-hook" not in captured.out + captured.err


def test_dry_run_does_not_post(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr(notify_discord, "post", lambda url, message: pytest.fail("投稿してはいけない"))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert notify_discord.main([_write(tmp_path, _result([("a1", "text_to_page_grouper")])), "--dry-run"]) == 0
    assert "`a1`" in capsys.readouterr().out


# -- プルリクエストの変更の確認 --

BRANCH = "claude-2026-11-20-09"
FILE = "tests/test_data/2026-11-20-09.json"


def test_single_added_test_data_is_allowed():
    assert check_pr_changes.check(BRANCH, f"A\t{FILE}\n") == (FILE, [])


@pytest.mark.parametrize(
    ("branch", "name_status"),
    [
        (BRANCH, ""),  # 変更がない
        (BRANCH, f"M\t{FILE}\n"),  # 既存のファイルの変更
        (BRANCH, f"D\t{FILE}\n"),  # 削除
        (BRANCH, "A\ttests/test_data/2026-11-20-10.json\n"),  # ブランチ名と日時が違う
        (BRANCH, f"A\t{FILE}\nA\ttests/test_data/2026-11-20-10.json\n"),  # 2 つ追加
        (BRANCH, f"A\t{FILE}\nM\ttarget.py\n"),  # ほかのファイルの変更
        (BRANCH, f"A\t{FILE}\nM\t.github/workflows/validate-test-data.yml\n"),  # ワークフローの変更
        (BRANCH, f"A\t{FILE}\nM\ttools/validate_test_data.py\n"),  # 検査のツールの変更
        (BRANCH, f"A\t{FILE}\nM\ttests/test_data/2026-11-20-00.json\n"),  # 過去のテストデータの変更
        (BRANCH, "A\ttests/test_data/sub/2026-11-20-09.json\n"),  # 別の場所
        ("claude-2026-11-20", "A\ttests/test_data/2026-11-20.json\n"),  # ブランチ名の形
        ("feature-x", f"A\t{FILE}\n"),
    ],
)
def test_other_changes_are_rejected(branch: str, name_status: str):
    path, errors = check_pr_changes.check(branch, name_status)
    assert path is None
    assert errors
