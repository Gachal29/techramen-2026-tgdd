"""「正しい形だが、意図と違う」かもしれないページの目安

入力（作業メモ）と出力（SlideIR のページ）だけから機械的にわかることを、注意として返す。
注意は目安で、考慮漏れの判定ではない
"""

import re
import xml.etree.ElementTree as ET
from collections import Counter

# 文字列の中に残っていたら、記法が解釈されていない疑いがあるもの
_LEFTOVER = [
    (re.compile(r"^\s*#{1,6}(\s|$)"), "#"),
    (re.compile(r"^\s*[-*+]\s"), "箇条書きの記号"),
    (re.compile(r"^\s*\d+\.\s"), "番号"),
    (re.compile(r"\*\*|__"), "**"),
    (re.compile(r"(?<!\*)\*[^*\s][^*]*\*(?!\*)"), "*"),
    (re.compile(r"~~"), "~~"),
    (re.compile(r"`"), "`"),
    (re.compile(r"!\[|\]\("), "リンク・図の記号"),
]
# 比べるときに無視する文字（記法の記号と空白）
_IGNORED = set("#*`~[]()!-+>|_ \t\r\n　")
_NUMBERING = re.compile(r"^\s*\d+\.\s", re.MULTILINE)
_ATTRIBUTES = ("src", "href", "url", "alt", "name")


def page_strings(page: ET.Element) -> list[str]:
    """ページに現れる文字列（<Str>・<Code> の中身と、URL・代替テキストなどの属性）"""
    strings: list[str] = []
    for node in page.iter():
        if node.tag in ("Str", "Code", "notes", "option") and node.text:
            strings.append(node.text)
        strings.extend(node.get(name, "") for name in _ATTRIBUTES if node.get(name))
    return strings


def _letters(text: str) -> Counter[str]:
    return Counter(character for character in text if character not in _IGNORED)


def coverage(source: str, page: ET.Element) -> tuple[int, int]:
    """(スライドに現れた原文の文字数, 原文の文字数)。記号と空白、番号付きリストの番号は数えない"""
    wanted = _letters(_NUMBERING.sub("", source))
    got = _letters("".join(page_strings(page)))
    return sum(min(count, got[character]) for character, count in wanted.items()), sum(wanted.values())


def page_notes(source: str, page: ET.Element) -> list[str]:
    notes: list[str] = []
    leftovers: list[str] = []
    for node in page.iter():
        if node.tag == "Str" and node.text:
            for pattern, name in _LEFTOVER:
                if pattern.search(node.text) and name not in leftovers:
                    leftovers.append(name)
    if leftovers:
        notes.append("未解釈の記号: " + "・".join(leftovers))

    shown, total = coverage(source, page)
    if total and shown < total:
        notes.append(f"原文の抜け: 再現率 {shown * 100 // total}%")

    extra = _letters("".join(page_strings(page))) - _letters(source)
    if extra:
        sample = "".join(sorted(extra))[:10]
        notes.append(f"原文にない文字: {sample}")
    return notes


def orphan_lines(memo: str, page_texts: list[str]) -> list[str]:
    """作業メモの行のうち、どのページにも入らなかった行（空行を除く）"""
    used = Counter(line.strip() for text in page_texts for line in text.splitlines() if line.strip())
    orphans: list[str] = []
    for line in memo.splitlines():
        key = line.strip()
        if not key:
            continue
        if used[key] > 0:
            used[key] -= 1
        else:
            orphans.append(line)
    return orphans
