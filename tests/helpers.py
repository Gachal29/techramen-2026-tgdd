"""テストの仕組みで使う処理（XML の比較、テストデータの検査）

テスト対象（target.py）には依存しない。tools/validate_test_data.py からも使う
"""

import copy
import difflib
import re
import xml.etree.ElementTree as ET
from typing import Any

from jsonschema import Draft202012Validator

# -- 分割の結果の比較 --


def normalize_page_text(text: str) -> str:
    """行末の空白と、前後の空行を除く"""
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def diff_page_groups(expected: list[str], actual: object) -> str | None:
    """分割の結果が一致すれば None、違えば差分の説明を返す"""
    if not isinstance(actual, list) or not all(isinstance(x, str) for x in actual):
        return f"戻り値が文字列の配列ではない: {actual!r}"
    want = [normalize_page_text(page) for page in expected]
    got = [normalize_page_text(page) for page in actual]
    if want == got:
        return None
    lines = [f"ページ数: 期待 {len(want)} / 実際 {len(got)}"]
    for index in range(max(len(want), len(got))):
        w = want[index] if index < len(want) else None
        g = got[index] if index < len(got) else None
        if w != g:
            lines.append(f"--- {index + 1} ページ目 期待 ---\n{w if w is not None else '（なし）'}")
            lines.append(f"--- {index + 1} ページ目 実際 ---\n{g if g is not None else '（なし）'}")
    return "\n".join(lines)


# -- XML の比較 --


def _drop_layout_whitespace(element: ET.Element) -> None:
    """要素の間にある空白だけのテキストを取り除く

    子要素を持つ要素の中の空白は、字下げのためのものとして除く。
    子要素を持たない要素（<Str> など）の中身は、空白も含めてそのまま残す
    """
    children = list(element)
    if children:
        if element.text is not None and not element.text.strip():
            element.text = None
        for child in children:
            if child.tail is not None and not child.tail.strip():
                child.tail = None
            _drop_layout_whitespace(child)


def _parse(xml: str) -> ET.Element:
    root = ET.fromstring(xml.strip())
    root.tail = None
    _drop_layout_whitespace(root)
    return root


def normalize_xml(xml: str) -> str:
    """比較のために XML を正規化する

    属性の順序、空要素の書き方（<Break/> と <Break />）、要素の間の空白の違いをなくす。
    文字列の中の空白は残す。整形式でなければ ET.ParseError
    """
    return ET.canonicalize(ET.tostring(_parse(xml), encoding="unicode"))


def _pretty(xml: str) -> str:
    root = copy.deepcopy(_parse(xml))
    ET.indent(root)
    return ET.canonicalize(ET.tostring(root, encoding="unicode"))


def diff_xml(expected: str, actual: object) -> str | None:
    """XML が一致すれば None、違えば差分の説明を返す。expected は整形式であること"""
    if not isinstance(actual, str):
        return f"戻り値が文字列ではない: {actual!r}"
    try:
        actual_normalized = normalize_xml(actual)
    except ET.ParseError as error:
        return f"戻り値が整形式の XML ではない（{error}）: {actual!r}"
    if normalize_xml(expected) == actual_normalized:
        return None
    diff = difflib.unified_diff(
        _pretty(expected).splitlines(),
        _pretty(actual).splitlines(),
        "期待",
        "実際",
        lineterm="",
    )
    return "\n".join(diff)


def page_id(xml: str) -> str:
    """ページの XML の id 属性"""
    return ET.fromstring(xml.strip()).get("id", "")


# -- ページの XML の検査（docs/slide-ir.md の 2 章） --

PAGE_ELEMENTS = ("CoverPage", "HeadingPage", "GeneralPage", "BodyPage", "FigurePage")
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_BOOL = ("true", "false")
_DECORATIONS = ("Strong", "Em", "Strike", "Underline", "Highlight")
# 図・メディア: 要素名 → (必須の属性, 省略できる属性)
_FIGURES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "ImageFigure": (("src",), ("alt", "href", "width", "height")),
    "VideoFigure": (("src",), ("alt",)),
    "AudioFigure": (("src",), ("alt",)),
    "EmbedFigure": (("url",), ("provider", "alt")),
    "FileFigure": (("src",), ("name", "mimeType", "size")),
    "ChartFigure": ((), ("alt",)),
    "DiagramFigure": ((), ("alt",)),
}
_URL_ATTRIBUTES = ("src", "href", "url")
_NUMBER_ATTRIBUTES = ("width", "height", "size")


class _Checker:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def attributes(self, element: ET.Element, required: tuple[str, ...], optional: tuple[str, ...]) -> None:
        for name in required:
            if name not in element.attrib:
                self.error(f"<{element.tag}> に {name} 属性がない")
        for name, value in element.attrib.items():
            if name not in required and name not in optional:
                self.error(f"<{element.tag}> に知らない属性 {name} がある")
            elif name in _URL_ATTRIBUTES and not _URL.fullmatch(value):
                self.error(f"<{element.tag}> の {name} が http・https の URL ではない: {value!r}")
            elif name in _NUMBER_ATTRIBUTES and not re.fullmatch(r"[0-9]+", value):
                self.error(f"<{element.tag}> の {name} が数値ではない: {value!r}")
            elif name in ("ordered", "marker", "header") and value not in _BOOL:
                self.error(f"<{element.tag}> の {name} が true・false ではない: {value!r}")

    def no_text(self, element: ET.Element) -> None:
        """子要素を並べる要素に、文字列が直接書かれていないこと"""
        texts = [element.text, *(child.tail for child in element)]
        if any(text and text.strip() for text in texts):
            self.error(f"<{element.tag}> の直下に文字列がある（文字列は <Str> に入れる）")

    def inlines(self, parent: ET.Element, in_anchor: bool = False) -> None:
        self.no_text(parent)
        for inline in parent:
            tag = inline.tag
            if tag in ("Str", "Code"):
                self.attributes(inline, (), ())
                if len(inline):
                    self.error(f"<{tag}> の中に要素がある")
                if "\n" in (inline.text or "") or "\r" in (inline.text or ""):
                    self.error(f"<{tag}> の中に改行がある（改行は <Break /> で表す）")
            elif tag == "Break":
                self.attributes(inline, (), ())
                if len(inline) or (inline.text or "").strip():
                    self.error("<Break> に中身がある")
            elif tag in _DECORATIONS:
                self.attributes(inline, (), ("style",) if tag in ("Underline", "Highlight") else ())
                self.inlines(inline, in_anchor)
            elif tag == "Anchor":
                if in_anchor:
                    self.error("<Anchor> の中に <Anchor> がある")
                self.attributes(inline, ("href",), ())
                self.inlines(inline, True)
            else:
                self.error(f"<{parent.tag}> の中に、インラインではない <{tag}> がある")

    def blocks(self, parent: ET.Element) -> None:
        self.no_text(parent)
        for block in parent:
            self.block(block, parent)

    def block(self, block: ET.Element, parent: ET.Element) -> None:
        tag = block.tag
        if tag == "TextBlock":
            self.attributes(block, (), ())
            self.no_text(block)
            for paragraph in block:
                if paragraph.tag != "Paragraph":
                    self.error(f"<TextBlock> の中に <{paragraph.tag}> がある（<Paragraph> だけを置ける）")
                    continue
                self.attributes(paragraph, (), ())
                self.inlines(paragraph)
        elif tag == "Cluster":
            self.attributes(block, (), ("ordered", "marker"))
            self.blocks(block)
        elif tag == "Table":
            self.attributes(block, (), ())
            self.no_text(block)
            for row in block:
                if row.tag != "TableRow":
                    self.error(f"<Table> の中に <{row.tag}> がある（<TableRow> だけを置ける）")
                    continue
                self.attributes(row, (), ())
                self.no_text(row)
                for cell in row:
                    if cell.tag != "TableCell":
                        self.error(f"<TableRow> の中に <{cell.tag}> がある（<TableCell> だけを置ける）")
                        continue
                    self.attributes(cell, (), ("header",))
                    self.blocks(cell)
        elif tag in _FIGURES:
            self.figure(block)
        else:
            self.error(f"<{parent.tag}> の中に、ブロックではない <{tag}> がある")

    def figure(self, figure: ET.Element) -> None:
        required, optional = _FIGURES[figure.tag]
        self.attributes(figure, required, optional)
        if len(figure) or (figure.text or "").strip():
            self.error(f"<{figure.tag}> に中身がある")

    def page(self, page: ET.Element) -> None:
        tag = page.tag
        if tag not in PAGE_ELEMENTS:
            self.error(f"ルートの要素 <{tag}> がページではない（{'・'.join(PAGE_ELEMENTS)} のどれかにする。名前空間は付けない）")
            return
        self.attributes(page, ("id",), ())
        identifier = page.get("id", "")
        if "id" in page.attrib and not _ID.fullmatch(identifier):
            self.error(f"id が英数字・ハイフン・アンダースコアの 1〜64 文字ではない: {identifier!r}")
        if (tag == "CoverPage") != (identifier == "cover") and "id" in page.attrib:
            self.error(f"<{tag}> の id が {identifier!r}（id が cover なのは <CoverPage> だけ）")
        self.no_text(page)

        children = list(page)
        names = [child.tag for child in children]
        # 型ごとの、持てる子要素（この順に並べる）。"Figure" は図・メディアの要素 1 つ
        allowed = {
            "CoverPage": ["title", "subtitle"],
            "HeadingPage": ["title"],
            "GeneralPage": ["title", "blocks"],
            "BodyPage": ["blocks"],
            "FigurePage": ["Figure"],
        }[tag] + ["notes", "option"]
        required = {
            "CoverPage": ["title"],
            "HeadingPage": ["title"],
            "GeneralPage": ["title", "blocks"],
            "BodyPage": ["blocks"],
            "FigurePage": ["Figure"],
        }[tag]
        kinds = ["Figure" if name in _FIGURES else name for name in names]
        for kind, name in zip(kinds, names):
            if kind not in allowed:
                self.error(f"<{tag}> に <{name}> を置けない")
        for kind in required:
            if kind not in kinds:
                self.error(f"<{tag}> に {'図・メディアの要素' if kind == 'Figure' else f'<{kind}>'} がない")
        for kind in set(kinds):
            if kinds.count(kind) > 1:
                what = "図・メディアの要素" if kind == "Figure" else f"<{kind}>"
                self.error(f"<{tag}> に {what} が複数ある")
        known = [kind for kind in kinds if kind in allowed]
        if known != sorted(known, key=allowed.index):
            self.error(f"<{tag}> の子要素の順序が違う（{' → '.join(allowed)} の順にする）")

        for child in children:
            if child.tag in ("title", "subtitle"):
                self.attributes(child, (), ())
                self.inlines(child)
                if child.tag == "title" and len(child) == 0:
                    self.error("<title> が空（見出しにはインラインが 1 つ以上必要）")
            elif child.tag == "blocks":
                self.attributes(child, (), ())
                self.blocks(child)
                if len(child) == 0:
                    self.error(f"<{tag}> の <blocks> が空（本文は 1 つ以上必要）")
                if tag == "BodyPage" and len(child) == 1 and child[0].tag in _FIGURES:
                    self.error("<BodyPage> の本文が図・メディア 1 つだけ（<FigurePage> にする）")
            elif child.tag in ("notes", "option"):
                self.attributes(child, (), ())
                if len(child):
                    self.error(f"<{child.tag}> の中に要素がある")
            elif child.tag in _FIGURES and tag == "FigurePage":
                self.figure(child)


def validate_page_xml(xml: str) -> list[str]:
    """ページ 1 つの XML が docs/slide-ir.md の 2 章に合っているか。問題の説明の配列を返す（空なら問題なし）"""
    try:
        root = ET.fromstring(xml.strip())
    except ET.ParseError as error:
        return [f"整形式の XML ではない（{error}）"]
    checker = _Checker()
    checker.page(root)
    return checker.errors


# -- テストデータの検査 --


def validate_test_data(data: Any, schema: dict[str, Any]) -> list[str]:
    """テストデータ（1 ファイル分）の検査。問題の説明の配列を返す（空なら問題なし）"""
    errors = [
        f"スキーマ違反 {'/'.join(str(part) for part in error.absolute_path) or '(ルート)'}: {error.message}"
        for error in sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(map(str, e.absolute_path)))
    ]
    if errors:
        return errors

    seen: set[str] = set()
    for case in data:
        name = case["test_data_id"]
        if name in seen:
            errors.append(f"{name}: test_data_id が重複している")
        seen.add(name)
        groups = case["expected_page_group"]
        pages = case["expected_slideir_page"]
        if len(groups) != len(pages):
            errors.append(
                f"{name}: expected_page_group（{len(groups)} 件）と expected_slideir_page（{len(pages)} 件）の数が違う"
            )
        for index, group in enumerate(groups, start=1):
            if not normalize_page_text(group):
                errors.append(f"{name}: expected_page_group の {index} 件目が空")
        ids: set[str] = set()
        for index, xml in enumerate(pages, start=1):
            problems = validate_page_xml(xml)
            errors.extend(f"{name}: expected_slideir_page の {index} 件目: {problem}" for problem in problems)
            if not problems:
                identifier = page_id(xml)
                if identifier in ids:
                    errors.append(f"{name}: expected_slideir_page の id {identifier!r} が重複している")
                ids.add(identifier)
    return errors
