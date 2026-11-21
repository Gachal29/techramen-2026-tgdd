"""作業メモからスライドをつくる

使い方: python slide-demo/build.py [--memo 作業メモ] [--out 出力先のディレクトリ]

target.py を変更したコミットを 1 つの版として、版ごとに次のものをつくる。

- slides/<連番>-<コミット>.ltool        SlideIR の生成結果（正しいページだけ）
- slides/<連番>-<コミット>.report.json  生成の記録（原文との対応、変換できなかったページ、注意）
- index.html                            すべての版を表示する HTML

作業ツリーの target.py がコミットされたものと違うときは、「作業中」の版として最後に足す
"""

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests"))

import checks  # noqa: E402
import ltool  # noqa: E402
import render  # noqa: E402
from helpers import validate_page_xml  # noqa: E402

RUNNER_TIMEOUT = 300  # 1 つの版の実行全体の上限（秒）


# -- 版 --


def git_versions(repository: Path = ROOT) -> list[dict[str, str]]:
    """target.py を変更したコミットを古い順に。それぞれ target.py の中身を持つ"""

    def git(*arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments], cwd=repository, capture_output=True, text=True, check=True
        ).stdout

    versions: list[dict[str, str]] = []
    log = git("log", "--reverse", "--format=%H%x09%cI%x09%s", "--", "target.py")
    for line in log.splitlines():
        commit, date, message = line.split("\t", 2)
        versions.append(
            {"commit": commit[:7], "date": date, "message": message, "code": git("show", f"{commit}:target.py")}
        )
    working = repository / "target.py"
    if working.exists():
        code = working.read_text(encoding="utf-8")
        if not versions or versions[-1]["code"] != code:
            versions.append({"commit": "working", "date": "", "message": "作業中（コミットされていない）", "code": code})
    return versions


# -- 生成: target.py を実行して、.ltool と記録をつくる --


def run_version(code: str, memo: str) -> dict[str, Any]:
    """1 つの版の target.py を別のプロセスで実行する。実行そのものが失敗したら load_error に入れる"""
    with tempfile.TemporaryDirectory() as directory:
        target_path = Path(directory) / "versioned_target.py"
        memo_path = Path(directory) / "memo.md"
        output_path = Path(directory) / "result.json"
        target_path.write_text(code, encoding="utf-8")
        memo_path.write_text(memo, encoding="utf-8")
        try:
            subprocess.run(
                [sys.executable, str(HERE / "runner.py"), str(target_path), str(memo_path), str(output_path)],
                cwd=directory,
                capture_output=True,
                timeout=RUNNER_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"load_error": f"{RUNNER_TIMEOUT} 秒以内に終わらなかった"}
        if not output_path.exists():
            return {"load_error": "実行が途中で止まった"}
        return json.loads(output_path.read_text(encoding="utf-8"))


def generate(memo: str, run: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """実行の結果から、(.ltool の中身, 記録) をつくる

    段階: ok = 正常、A = 変換できない、B = SlideIR として正しくない
    """
    pages: list[dict[str, Any]] = []
    whole_error = run.get("load_error") or run.get("group_error")
    if whole_error:
        # 分割できなかったときは、作業メモ全体を 1 ページとして扱う
        pages.append({"source": memo.strip("\n"), "stage": "A", "problem": whole_error, "output": None})
    seen: set[str] = set()
    has_cover = False
    for item in run.get("pages", []):
        page: dict[str, Any] = {"source": item["text"], "stage": "ok", "problem": None, "output": item["result"]}
        if not item["ok"]:
            page.update(stage="A", problem=item["result"], output=None)
        else:
            problems = validate_page_xml(item["result"])
            if not problems:
                element = ET.fromstring(item["result"].strip())
                identifier = element.get("id", "")
                if identifier in seen:
                    problems = [f"id {identifier!r} が重複している"]
                elif element.tag == "CoverPage" and has_cover:
                    problems = ["表紙が 2 つある"]
                else:
                    seen.add(identifier)
                    has_cover = has_cover or element.tag == "CoverPage"
                    page["id"] = identifier
            if problems:
                page.update(stage="B", problem=problems[0] + (f"（ほか {len(problems) - 1} 件）" if len(problems) > 1 else ""))
        pages.append(page)

    document = ltool.build_document([page["output"] for page in pages if page["stage"] == "ok"])
    elements = ltool.read_pages(document)
    for page in pages:
        page["notes"] = checks.page_notes(page["source"], elements[page["id"]]) if page["stage"] == "ok" else []
    orphans = [] if whole_error else checks.orphan_lines(memo, [page["source"] for page in pages])
    report = {"gacha": run.get("gacha"), "pages": pages, "orphan_lines": orphans}
    return document, report


# -- 表示: .ltool と記録から HTML をつくる --


def _pretty(xml: str) -> str:
    try:
        element = ET.fromstring(xml.strip())
    except ET.ParseError:
        return xml
    ET.indent(element)
    return ET.tostring(element, encoding="unicode")


def view(document: str, report: dict[str, Any]) -> dict[str, Any]:
    """1 つの版の、表示用のデータ"""
    elements = ltool.read_pages(document)
    pages: list[dict[str, Any]] = []
    shown = total = 0
    for page in report["pages"]:
        if page["stage"] == "ok":
            element = elements[page["id"]]
            html = render.page(element)
            part = checks.coverage(page["source"], element)
            shown, total = shown + part[0], total + part[1]
        else:
            heading = "変換できませんでした" if page["stage"] == "A" else "SlideIR として正しくありません"
            html = render.fallback(heading, page["problem"] or "", page["source"])
            total += checks.coverage(page["source"], ET.Element("x"))[1]
        pages.append(
            {
                "html": html,
                "source": page["source"],
                "xml": _pretty(page["output"]) if page["output"] else "",
                "stage": page["stage"],
                "problem": page["problem"],
                "notes": page["notes"],
            }
        )
    if report["orphan_lines"]:
        source = "\n".join(report["orphan_lines"])
        total += checks.coverage(source, ET.Element("x"))[1]
        pages.append(
            {
                "html": render.fallback("どのページにも入らなかった行", f"{len(report['orphan_lines'])} 行", source),
                "source": source,
                "xml": "",
                "stage": "orphan",
                "problem": None,
                "notes": [],
            }
        )
    return {
        "pages": pages,
        "gacha": report["gacha"],
        "stats": {
            "pages": len(pages),
            "flagged": sum(1 for page in pages if page["stage"] != "ok" or page["notes"]),
            "coverage": round(shown * 100 / total) if total else 100,
        },
    }


def build(memo: str, versions: list[dict[str, str]], out: Path) -> Path:
    slides = out / "slides"
    slides.mkdir(parents=True, exist_ok=True)
    for old in [*slides.glob("*.ltool"), *slides.glob("*.report.json")]:
        old.unlink()
    views: list[dict[str, Any]] = []
    for number, version in enumerate(versions, start=1):
        name = f"{number:02}-{version['commit']}"
        document, report = generate(memo, run_version(version["code"], memo))
        report = {"commit": version["commit"], "date": version["date"], "message": version["message"], **report}
        (slides / f"{name}.ltool").write_text(document, encoding="utf-8")
        (slides / f"{name}.report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        # 表示は、書き出したファイルだけを入力にする
        loaded_document = (slides / f"{name}.ltool").read_text(encoding="utf-8")
        loaded_report = json.loads((slides / f"{name}.report.json").read_text(encoding="utf-8"))
        views.append(
            {
                "number": number,
                "commit": version["commit"],
                "date": version["date"],
                "message": version["message"],
                "file": f"slides/{name}.ltool",
                **view(loaded_document, loaded_report),
            }
        )
        if number == len(versions):
            (slides / "latest.ltool").write_text(document, encoding="utf-8")

    data = json.dumps({"versions": views}, ensure_ascii=False).replace("</", "<\\/")
    template = (HERE / "template.html").read_text(encoding="utf-8")
    index = out / "index.html"
    index.write_text(template.replace("/*__DATA__*/null", data), encoding="utf-8")
    return index


def main(arguments: list[str]) -> int:
    def option(name: str, default: Path) -> Path:
        return Path(arguments[arguments.index(name) + 1]) if name in arguments else default

    memo_path = option("--memo", HERE / "memo.md")
    out = option("--out", HERE / "dist")
    versions = git_versions()
    if not versions:
        print("target.py の版が見つからない", file=sys.stderr)
        return 1
    index = build(memo_path.read_text(encoding="utf-8"), versions, out)
    print(f"{len(versions)} 版のスライドをつくった: {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
