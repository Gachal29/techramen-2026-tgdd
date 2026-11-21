"""slide-demo（作業メモからスライドをつくる仕組み）のテスト"""

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

import build
import checks
import ltool
import render
from helpers import validate_page_xml

HEADING = '<HeadingPage id="p1"><title><Str>見出し</Str></title></HeadingPage>'
GENERAL = (
    '<GeneralPage id="p2"><title><Str>題</Str></title><blocks>'
    '<TextBlock><Paragraph><Str>a &lt; b</Str><Strong><Str>太字</Str></Strong><Code>x</Code><Break />'
    '<Anchor href="https://example.com/"><Str>リンク</Str></Anchor></Paragraph></TextBlock>'
    '<Cluster ordered="true" marker="true"><TextBlock><Paragraph><Str>一</Str></Paragraph></TextBlock>'
    '<Cluster marker="true"><TextBlock><Paragraph><Str>子</Str></Paragraph></TextBlock></Cluster></Cluster>'
    '<Table><TableRow><TableCell header="true"><TextBlock><Paragraph><Str>列</Str></Paragraph></TextBlock></TableCell></TableRow></Table>'
    "</blocks></GeneralPage>"
)
FIGURE = '<FigurePage id="p3"><ImageFigure src="https://example.com/a.png" alt="図" /></FigurePage>'
COVER = '<CoverPage id="cover"><title><Str>題名</Str></title><subtitle><Str>副題</Str></subtitle></CoverPage>'
BODY = '<BodyPage id="p4"><blocks><TextBlock><Paragraph><Str>本文</Str></Paragraph></TextBlock></blocks></BodyPage>'


def _element(xml: str) -> ET.Element:
    return ET.fromstring(xml)


# -- .ltool --


def test_ltool_document_has_namespace_and_keeps_order():
    document = ltool.build_document([COVER, HEADING, GENERAL])
    root = ET.fromstring(document.encode("utf-8"))
    namespace = "{https://docs.ltool.io/ns/slide-ir}"
    assert document.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert root.tag == f"{namespace}SlideIR"
    assert root.get("version") == "0.1"
    assert [page.tag for page in root.find(f"{namespace}PagePool")] == [
        f"{namespace}CoverPage",
        f"{namespace}HeadingPage",
        f"{namespace}GeneralPage",
    ]
    assert all(node.tag.startswith(namespace) for node in root.iter())


def test_ltool_pages_can_be_read_back_as_valid_fragments():
    pages = ltool.read_pages(ltool.build_document([COVER, HEADING, GENERAL, FIGURE, BODY]))
    assert list(pages) == ["cover", "p1", "p2", "p3", "p4"]
    for page in pages.values():
        assert validate_page_xml(ET.tostring(page, encoding="unicode")) == []


def test_ltool_rejects_other_documents():
    with pytest.raises(ValueError):
        ltool.read_pages("<SlideIR><PagePool /></SlideIR>")


# -- 表示 --


@pytest.mark.parametrize(
    ("xml", "kind"),
    [(COVER, "cover"), (HEADING, "heading"), (GENERAL, "general"), (BODY, "body"), (FIGURE, "figure")],
)
def test_render_page_types(xml: str, kind: str):
    assert render.page(_element(xml)).startswith(f'<section class="page {kind}">')


def test_render_contents():
    html = render.page(_element(GENERAL))
    assert "<h1>題</h1>" in html
    assert "a &lt; b" in html
    assert "<strong>太字</strong>" in html
    assert "<code>x</code>" in html
    assert "<br>" in html
    assert '<a href="https://example.com/"' in html
    assert "<ol><li><p>一</p></li>" in html
    assert '<li class="nested"><ul><li><p>子</p></li></ul></li>' in html
    assert "<th><p>列</p></th>" in html
    assert '<img src="https://example.com/a.png" alt="図">' in render.page(_element(FIGURE))
    assert '<p class="subtitle">副題</p>' in render.page(_element(COVER))


def test_render_escapes_text_and_drops_unsafe_urls():
    xml = (
        '<BodyPage id="p1"><blocks><TextBlock><Paragraph><Str>&lt;script&gt;alert(1)&lt;/script&gt;</Str>'
        '<Anchor href="javascript:alert(1)"><Str>押す</Str></Anchor></Paragraph></TextBlock>'
        '<ImageFigure src="javascript:alert(1)" alt="&quot;&gt;&lt;b&gt;" /></blocks></BodyPage>'
    )
    html = render.page(_element(xml))
    assert "<script>" not in html
    assert "javascript:" not in html
    assert "<b>" not in html
    assert "押す" in html


def test_fallback_shows_source_escaped():
    html = render.fallback("変換できませんでした", "ValueError: <x>", "## 見出し\n- <b>a</b>")
    assert 'class="page fallback"' in html
    assert "## 見出し\n- &lt;b&gt;a&lt;/b&gt;" in html
    assert "ValueError: &lt;x&gt;" in html


# -- 注意の検出 --


def test_no_notes_for_faithful_page():
    source = "## 題\na < b**太字**`x`\n[リンク](https://example.com/)\n1. 一\n  - 子\n列"
    assert checks.page_notes(source, _element(GENERAL)) == []


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("## 見出し", "#"),
        ("- 項目", "箇条書きの記号"),
        ("1. 項目", "番号"),
        ("これは**太字**", "**"),
        ("これは *斜体* です", "*"),
        ("見つかるかどうかは*偶然*", "*"),
        ("~~消す~~", "~~"),
        ("`code`", "`"),
        ("![図](https://x/a.png)", "リンク・図の記号"),
    ],
)
def test_leftover_markup_is_noted(text: str, name: str):
    page = ET.fromstring('<HeadingPage id="p1"><title><Str /></title></HeadingPage>')
    page[0][0].text = text
    notes = checks.page_notes(text, page)
    assert any(note.startswith("未解釈の記号") and name in note for note in notes), notes


def test_plain_asterisk_is_not_leftover():
    page = ET.fromstring('<HeadingPage id="p1"><title><Str>3 * 4 = 12</Str></title></HeadingPage>')
    assert checks.page_notes("## 3 * 4 = 12", page) == []


def test_missing_and_extra_text_are_noted():
    notes = checks.page_notes("## 見出し\n本文があります", _element(HEADING))
    assert any(note.startswith("原文の抜け") for note in notes)
    notes = checks.page_notes("## 見", _element(HEADING))
    assert any(note.startswith("原文にない文字") for note in notes)


def test_orphan_lines():
    memo = "# 題名\n\n## a\n- b\n\n## a\nあまり\n"
    assert checks.orphan_lines(memo, ["## a\n- b", "## a"]) == ["# 題名", "あまり"]
    assert checks.orphan_lines(memo, ["# 題名", "## a\n- b", "## a\nあまり"]) == []


# -- 生成（段階の判定） --

MEMO = "# 題名\n\n## 見出し\n\n## 題\n- 項目\n"


def _run(pages: list[tuple[str, str, bool, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "load_error": None,
        "group_error": None,
        "pages": [{"text": text, "id": identifier, "ok": ok, "result": result} for text, identifier, ok, result in pages],
        "gacha": {"total": 3, "passed": 1},
        **extra,
    }


def test_generate_keeps_only_valid_pages_in_ltool():
    run = _run(
        [
            ("# 題名", "cover", True, COVER),
            ("## 見出し", "p1", False, "ValueError: boom"),  # A: 例外
            ("## 題\n- 項目", "p2", True, "<GeneralPage"),  # B: 整形式ではない
            ("## x", "p3", True, '<HeadingPage id="p3"></HeadingPage>'),  # B: 境界に合わない
            ("## y", "p4", True, BODY),
        ]
    )
    document, report = build.generate(MEMO, run)
    assert [page["stage"] for page in report["pages"]] == ["ok", "A", "B", "B", "ok"]
    assert list(ltool.read_pages(document)) == ["cover", "p4"]
    assert report["pages"][1]["problem"] == "ValueError: boom"
    assert report["pages"][2]["problem"]
    assert report["gacha"] == {"total": 3, "passed": 1}


def test_generate_rejects_duplicate_ids_and_second_cover():
    second_cover = COVER.replace('id="cover"', 'id="cover"')
    run = _run(
        [
            ("# 題名", "cover", True, COVER),
            ("## 見出し", "p1", True, HEADING),
            ("## 見出し", "p1", True, HEADING),
            ("# 題名", "cover", True, second_cover),
        ]
    )
    document, report = build.generate(MEMO, run)
    assert [page["stage"] for page in report["pages"]] == ["ok", "ok", "B", "B"]
    assert list(ltool.read_pages(document)) == ["cover", "p1"]


@pytest.mark.parametrize("run", [{"load_error": "SyntaxError: x"}, {"load_error": None, "group_error": "RuntimeError: x", "pages": []}])
def test_generate_whole_memo_fallback(run: dict[str, Any]):
    document, report = build.generate(MEMO, run)
    assert [page["stage"] for page in report["pages"]] == ["A"]
    assert report["pages"][0]["source"] == MEMO.strip("\n")
    assert report["orphan_lines"] == []
    assert ltool.read_pages(document) == {}


def test_view_shows_every_page_and_orphans():
    run = _run([("## 見出し", "p1", True, HEADING), ("## 題\n- 項目", "p2", False, "ValueError: boom")])
    document, report = build.generate(MEMO, run)
    data = build.view(document, json.loads(json.dumps(report)))
    assert [page["stage"] for page in data["pages"]] == ["ok", "A", "orphan"]
    assert 'class="page heading"' in data["pages"][0]["html"]
    assert "変換できませんでした" in data["pages"][1]["html"]
    assert "## 題\n- 項目" in data["pages"][1]["html"]
    assert "# 題名" in data["pages"][2]["html"]
    assert data["stats"]["pages"] == 3
    assert data["stats"]["flagged"] == 2
    assert 0 < data["stats"]["coverage"] < 100


# -- 版の実行とビルド全体 --

GOOD = '''
import xml.etree.ElementTree as ET

def text_to_page_grouper(raw_text):
    print("標準出力への出力は無視される")
    return [line for line in raw_text.splitlines() if line.strip()]

def page_to_slideir_page(page_text, page_id):
    page = ET.Element("HeadingPage", {"id": page_id})
    ET.SubElement(ET.SubElement(page, "title"), "Str").text = page_text.lstrip("# ")
    return ET.tostring(page, encoding="unicode")
'''
BROKEN_VERSIONS = {
    "構文エラー": "def text_to_page_grouper(:",
    "関数がない": "def text_to_page_grouper(raw_text):\n    return []\n",
    "分割で例外": GOOD + "\ndef text_to_page_grouper(raw_text):\n    raise RuntimeError('boom')\n",
    "分割の戻り値が不正": GOOD + "\ndef text_to_page_grouper(raw_text):\n    return 'x'\n",
}


def test_run_version_good():
    run = build.run_version(GOOD, "## a\n\n## b\n")
    assert run["load_error"] is None and run["group_error"] is None
    assert [(page["id"], page["ok"]) for page in run["pages"]] == [("p1", True), ("p2", True)]
    assert run["gacha"]["total"] > 0
    assert 0 <= run["gacha"]["passed"] <= run["gacha"]["total"]


@pytest.mark.parametrize("code", BROKEN_VERSIONS.values(), ids=BROKEN_VERSIONS.keys())
def test_run_version_broken_still_produces_fallback(code: str):
    run = build.run_version(code, "## a\n")
    assert run.get("load_error") or run.get("group_error")
    document, report = build.generate("## a\n", run)
    assert [page["stage"] for page in report["pages"]] == ["A"]


def test_run_version_page_errors_do_not_stop_other_pages(monkeypatch: pytest.MonkeyPatch):
    code = GOOD + (
        "\n_original = page_to_slideir_page\n"
        "def page_to_slideir_page(page_text, page_id):\n"
        "    if page_id == 'p1':\n        raise ValueError('boom')\n"
        "    if page_id == 'p2':\n        return 123\n"
        "    if page_id == 'p3':\n        while True:\n            pass\n"
        "    return _original(page_text, page_id)\n"
    )
    monkeypatch.setenv("TGDD_CALL_LIMIT", "1")
    run = build.run_version(code, "## a\n## b\n## c\n## d\n")
    assert [page["ok"] for page in run["pages"]] == [False, False, False, True]
    assert "ValueError" in run["pages"][0]["result"]
    assert "文字列ではない" in run["pages"][1]["result"]
    assert "終わらなかった" in run["pages"][2]["result"]


def test_build_from_git_history(tmp_path: Path):
    repository = tmp_path / "repo"
    repository.mkdir()

    def git(*arguments: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
        )

    git("init", "-q", "-b", "main")
    for number, code in enumerate([BROKEN_VERSIONS["分割で例外"], GOOD], start=1):
        (repository / "target.py").write_text(code, encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", f"版 {number}")
    (repository / "other.txt").write_text("x", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "target.py 以外の変更")
    (repository / "target.py").write_text(GOOD + "\n# 作業中\n", encoding="utf-8")

    versions = build.git_versions(repository)
    assert [version["message"] for version in versions] == ["版 1", "版 2", "作業中（コミットされていない）"]

    index = build.build("## a\n\n## b\n", versions, tmp_path / "out")
    names = sorted(path.name for path in (tmp_path / "out" / "slides").iterdir())
    assert len([name for name in names if name.endswith(".ltool")]) == 4  # 3 版と latest
    assert len([name for name in names if name.endswith(".report.json")]) == 3
    assert "latest.ltool" in names

    html = index.read_text(encoding="utf-8")
    assert "/*__DATA__*/null" not in html
    data = json.loads(html.split("const DATA = ", 1)[1].split(";\nconst versions", 1)[0].replace("<\\/", "</"))
    assert [version["number"] for version in data["versions"]] == [1, 2, 3]
    assert [page["stage"] for page in data["versions"][0]["pages"]] == ["A"]
    assert [page["stage"] for page in data["versions"][1]["pages"]] == ["ok", "ok"]
    assert list(ltool.read_pages((tmp_path / "out" / "slides" / "latest.ltool").read_text(encoding="utf-8"))) == ["p1", "p2"]
