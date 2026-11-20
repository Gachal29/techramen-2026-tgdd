"""テスト対象のモジュール

作業メモ（Markdown 風のテキスト）をページに分け、SlideIR のページ（XML）に変換する。
仕様は docs/plans/2026-11-20-first-implementation.md の 2 章と docs/slide-ir.md。

最初の版は、TGDD の検証を始めるための単純な実装で、考慮していない書き方が多い
"""

import xml.etree.ElementTree as ET

HEADING = "## "
BULLET = "- "


def text_to_page_grouper(raw_text: str) -> list[str]:
    """作業メモを、ページごとのテキストに分ける

    分割ルール
    1. `## ` で始まる行から、次の `## ` で始まる行の前までを 1 ページにする
    """
    pages: list[list[str]] = []
    for line in raw_text.splitlines():
        if line.startswith(HEADING):
            pages.append([line])
        elif pages and line.strip():
            pages[-1].append(line)
    return ["\n".join(page) for page in pages]


def _text_block(parent: ET.Element, text: str) -> None:
    paragraph = ET.SubElement(ET.SubElement(parent, "TextBlock"), "Paragraph")
    ET.SubElement(paragraph, "Str").text = text


def page_to_slideir_page(page_text: str, page_id: str) -> str:
    """1 ページ分のテキストを、SlideIR のページの XML にする

    変換ルール
    1. 1 行目の見出しを title にする
    2. `- ` で始まる行を箇条書きにする。箇条書きがあれば GeneralPage、なければ HeadingPage
    """
    lines = page_text.splitlines()
    title = lines[0].removeprefix(HEADING)
    bullets = [line.strip().removeprefix(BULLET) for line in lines[1:] if line.strip().startswith(BULLET)]

    page = ET.Element("GeneralPage" if bullets else "HeadingPage", {"id": page_id})
    ET.SubElement(ET.SubElement(page, "title"), "Str").text = title
    if bullets:
        cluster = ET.SubElement(ET.SubElement(page, "blocks"), "Cluster", {"marker": "true"})
        for bullet in bullets:
            _text_block(cluster, bullet)
    return ET.tostring(page, encoding="unicode")
