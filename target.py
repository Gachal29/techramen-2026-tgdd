"""テスト対象のモジュール

作業メモ（Markdown 風のテキスト）をページに分け、SlideIR のページ（XML）に変換する。
仕様は docs/plans/2026-11-20-first-implementation.md の 2 章と docs/slide-ir.md。
"""

import re
import xml.etree.ElementTree as ET

# 半角・全角の `#` と、その後の半角・全角の空白を受け付ける
COVER_RE = re.compile(r"^[#＃][ \t　]+(?P<text>.*\S)\s*$")
# 見出しは `##` の後の空白がなくてもよい（`##見出し`）。`###` は見出しにしない
HEADING_RE = re.compile(r"^[#＃]{2}(?![#＃])[ \t　]*(?P<text>.*\S)\s*$")
# 見出しの末尾の、空白に続く閉じの `#`（`## 見出し ##`）
CLOSING_HASHES_RE = re.compile(r"[ \t　]+[#＃]+$")
# `-`・`*`・`+`（全角の `－`・`＊`・`＋` も）は箇条書き、`1.`・`1)` は番号付き。
# 中黒 `・`（半角の `･` も）も箇条書きにする。日本語のメモでは後ろに空白を置かないことが多いため、空白はなくてよい。
# 字下げは半角空白 2 つ（全角空白なら 1 つ）で 1 段
BULLET_RE = re.compile(
    r"^(?P<indent>[ \t　]*)"
    r"(?:(?:(?P<mark>[-*+－＊＋])|(?P<number>\d+)[.)])[ \t　]+|(?P<dot>[・･])[ \t　]*)"
    r"(?P<text>.*)$"
)
IMAGE_RE = re.compile(r"^\s*!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)\)\s*$")


def _heading_text(text: str) -> str:
    """見出しの文字から、閉じの `#` と前後の空白を除く"""
    return CLOSING_HASHES_RE.sub("", text.strip()).strip()


def _is_cover(line: str) -> bool:
    return COVER_RE.match(line) is not None


def _is_heading(line: str) -> bool:
    return HEADING_RE.match(line) is not None


def _is_image(line: str) -> bool:
    return IMAGE_RE.match(line) is not None


def text_to_page_grouper(raw_text: str) -> list[str]:
    """作業メモを、ページごとのテキストに分ける

    分割ルール
    1. `# ` の行は、それだけで 1 ページ（表紙）
    2. `## ` で始まる行から、次の見出し（`# `・`## `）の前までを 1 ページにする
    3. 見出しより前（または表紙の直後）にある図だけの行は、それだけで 1 ページ
    4. 見出しより前にあるそれ以外の行は、図だけの行を除き、続く行をまとめて 1 ページ（見出しのないページ）
    5. 行末の空白は除く。ページの前後の空行は除き、ページの途中の空行はそのまま残す
    """
    pages: list[list[str]] = []
    # 今のページの種類: "heading"（見出しのページ）、"body"（見出しのない本文のページ）、None（足せない）
    current: str | None = None
    # まだどのページにも入れていない空行の数（続く行が同じページに入るときだけ足す）
    pending_blanks = 0
    for raw_line in raw_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            pending_blanks += 1
            continue
        blanks, pending_blanks = pending_blanks, 0
        if current is not None and not _is_cover(line) and not _is_heading(line):
            if current == "heading" or (current == "body" and not _is_image(line)):
                pages[-1].extend([""] * blanks)
        if _is_cover(line):
            pages.append([line])
            current = None
        elif _is_heading(line):
            pages.append([line])
            current = "heading"
        elif current == "heading":
            pages[-1].append(line)
        elif _is_image(line):
            pages.append([line])
            current = None
        elif current == "body":
            pages[-1].append(line)
        else:
            pages.append([line])
            current = "body"
    return ["\n".join(page) for page in pages]


# -- インラインの記法 --

_DELIMITERS = [("**", "Strong"), ("~~", "Strike"), ("*", "Em")]
_LINK_RE = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<href>[^)\s]+)\)")


def _find_closing(text: str, delimiter: str, start: int) -> int:
    """`start` 以降で、閉じる記号の位置を返す。なければ -1

    閉じる記号の直前は空白でないこと。`*` は `**` の一部でないこと
    """
    position = start
    while True:
        position = text.find(delimiter, position)
        if position == -1:
            return -1
        if delimiter == "*":
            # `**` の一部なら、ひとまとまりで読み飛ばす（入れ子の太字）
            if text.startswith("**", position):
                closing = _find_closing(text, "**", position + 2)
                if closing == -1:
                    return -1
                position = closing + 2
                continue
        if position > start and not text[position - 1].isspace():
            return position
        position += len(delimiter)


def _parse_inline(text: str) -> list[tuple]:
    """インラインの記法を解析し、(種類, 中身) の配列にする

    種類は "Str"（中身は文字列）、"Code"（文字列）、"Anchor"（(href, 子の配列)）、
    "Strong"・"Em"・"Strike"（子の配列）
    """
    nodes: list[tuple] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            nodes.append(("Str", "".join(buffer)))
            buffer.clear()

    index = 0
    while index < len(text):
        char = text[index]
        if char == "`":
            closing = text.find("`", index + 1)
            if closing > index + 1:
                flush()
                nodes.append(("Code", text[index + 1 : closing]))
                index = closing + 1
                continue
        if char == "[":
            link = _LINK_RE.match(text, index)
            if link:
                flush()
                nodes.append(("Anchor", (link["href"], _parse_inline(link["text"]))))
                index = link.end()
                continue
        matched = False
        for delimiter, kind in _DELIMITERS:
            if not text.startswith(delimiter, index):
                continue
            inner_start = index + len(delimiter)
            if inner_start >= len(text) or text[inner_start].isspace():
                continue
            closing = _find_closing(text, delimiter, inner_start)
            if closing == -1:
                continue
            flush()
            nodes.append((kind, _parse_inline(text[inner_start:closing])))
            index = closing + len(delimiter)
            matched = True
            break
        if matched:
            continue
        buffer.append(char)
        index += 1
    flush()
    return nodes


def _append_inlines(parent: ET.Element, text: str) -> None:
    _append_nodes(parent, _parse_inline(text))


def _append_nodes(parent: ET.Element, nodes: list[tuple]) -> None:
    for kind, value in nodes:
        if kind in ("Str", "Code"):
            ET.SubElement(parent, kind).text = value
        elif kind == "Anchor":
            href, children = value
            _append_nodes(ET.SubElement(parent, "Anchor", {"href": href}), children)
        else:
            _append_nodes(ET.SubElement(parent, kind), value)


# -- ブロック --


def _text_block(parent: ET.Element, text: str) -> None:
    paragraph = ET.SubElement(ET.SubElement(parent, "TextBlock"), "Paragraph")
    _append_inlines(paragraph, text)


def _image_figure(parent: ET.Element, line: str) -> None:
    match = IMAGE_RE.match(line)
    assert match is not None
    attributes = {"src": match["src"]}
    if match["alt"].strip():
        attributes["alt"] = match["alt"]
    ET.SubElement(parent, "ImageFigure", attributes)


def _indent_level(indent: str) -> int:
    # 全角空白は半角空白 2 つ分の幅として数える
    return len(indent.replace("　", "  ").expandtabs(2)) // 2


def _build_blocks(lines: list[str]) -> ET.Element:
    """本文の行を `<blocks>` にする

    - 図だけの行は ImageFigure、箇条書きは Cluster（字下げは入れ子）、それ以外は段落 1 行で TextBlock 1 つ
    """
    blocks = ET.Element("blocks")
    # 箇条書きの入れ子: (Cluster 要素, 番号付きか) の配列。添字が段
    stack: list[tuple[ET.Element, bool]] = []
    for line in lines:
        bullet = BULLET_RE.match(line)
        if bullet and bullet["text"].strip():
            ordered = bullet["number"] is not None
            level = min(_indent_level(bullet["indent"]), len(stack))
            del stack[level + 1 :]
            if len(stack) > level and stack[level][1] != ordered:
                del stack[level:]
            if len(stack) <= level:
                parent = stack[level - 1][0] if level > 0 else blocks
                attributes = {"marker": "true"}
                if ordered:
                    attributes = {"ordered": "true", "marker": "true"}
                stack.append((ET.SubElement(parent, "Cluster", attributes), ordered))
            _text_block(stack[level][0], bullet["text"].strip())
            continue
        stack.clear()
        if _is_image(line):
            _image_figure(blocks, line)
        else:
            _text_block(blocks, line.strip())
    return blocks


FIGURE_TAGS = {"ImageFigure", "VideoFigure", "AudioFigure", "EmbedFigure", "FileFigure", "ChartFigure", "DiagramFigure"}


def page_to_slideir_page(page_text: str, page_id: str) -> str:
    """1 ページ分のテキストを、SlideIR のページの XML にする

    変換ルール（slide-ir.md の 2.1 の順番）
    1. `# ` の行は CoverPage
    2. `## ` の見出しがあり、本文があれば GeneralPage、なければ HeadingPage
    3. 見出しがなく、本文が図 1 つだけなら FigurePage、それ以外は BodyPage
    """
    lines = [line.rstrip() for line in page_text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("空のページは作らない")

    cover = COVER_RE.match(lines[0])
    if cover:
        page = ET.Element("CoverPage", {"id": page_id})
        _append_inlines(ET.SubElement(page, "title"), _heading_text(cover["text"]))
        return ET.tostring(page, encoding="unicode")

    heading = HEADING_RE.match(lines[0])
    if heading:
        blocks = _build_blocks(lines[1:])
        page = ET.Element("GeneralPage" if len(blocks) else "HeadingPage", {"id": page_id})
        _append_inlines(ET.SubElement(page, "title"), _heading_text(heading["text"]))
        if len(blocks):
            page.append(blocks)
        return ET.tostring(page, encoding="unicode")

    blocks = _build_blocks(lines)
    if len(blocks) == 1 and blocks[0].tag in FIGURE_TAGS:
        page = ET.Element("FigurePage", {"id": page_id})
        page.append(blocks[0])
    else:
        page = ET.Element("BodyPage", {"id": page_id})
        page.append(blocks)
    return ET.tostring(page, encoding="unicode")
