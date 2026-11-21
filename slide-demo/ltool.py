""".ltool（SlideIR のドキュメント）を書く・読む

.ltool は、ページプールのみの SlideIR のドキュメント（XML・UTF-8）。
page_to_slideir_page() が返す名前空間なしの断片に、ここで名前空間を付ける
"""

import copy
import xml.etree.ElementTree as ET

NAMESPACE = "https://docs.ltool.io/ns/slide-ir"
VERSION = "0.1"
_PREFIX = f"{{{NAMESPACE}}}"

ET.register_namespace("", NAMESPACE)


def _rename(element: ET.Element, add: bool) -> None:
    for node in element.iter():
        node.tag = _PREFIX + node.tag if add else node.tag.removeprefix(_PREFIX)


def build_document(page_fragments: list[str]) -> str:
    """ページの XML の断片（正しいものだけを渡す）を、渡した順に PagePool に入れたドキュメントにする"""
    root = ET.Element("SlideIR", {"version": VERSION})
    pool = ET.SubElement(root, "PagePool")
    for fragment in page_fragments:
        pool.append(ET.fromstring(fragment.strip()))
    _rename(root, add=True)
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def read_pages(document: str) -> dict[str, ET.Element]:
    """ドキュメントのページを、id → 要素（名前空間を外したもの）で返す"""
    root = ET.fromstring(document.encode("utf-8"))
    if root.tag != f"{_PREFIX}SlideIR":
        raise ValueError("SlideIR のドキュメントではない")
    pages: dict[str, ET.Element] = {}
    for page in root.findall(f"{_PREFIX}PagePool/*"):
        page = copy.deepcopy(page)
        _rename(page, add=False)
        pages[page.get("id", "")] = page
    return pages
