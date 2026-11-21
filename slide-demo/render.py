"""SlideIR のページ（XML の要素）を HTML にする

文字列はすべてエスケープする。リンクと画像の URL は http・https だけを通す
"""

import re
import xml.etree.ElementTree as ET
from html import escape

_SAFE_URL = re.compile(r"https?://", re.IGNORECASE)
_DECORATIONS = {"Strong": "strong", "Em": "em", "Strike": "s", "Underline": "u", "Highlight": "mark"}
_FIGURE_NAMES = {"VideoFigure": "動画", "AudioFigure": "音声", "ChartFigure": "グラフ", "DiagramFigure": "図解"}


def _safe(url: str | None) -> str | None:
    return url if url and _SAFE_URL.match(url) else None


def inlines(parent: ET.Element) -> str:
    parts: list[str] = []
    for node in parent:
        if node.tag == "Str":
            parts.append(escape(node.text or ""))
        elif node.tag == "Code":
            parts.append(f"<code>{escape(node.text or '')}</code>")
        elif node.tag == "Break":
            parts.append("<br>")
        elif node.tag in _DECORATIONS:
            tag = _DECORATIONS[node.tag]
            parts.append(f"<{tag}>{inlines(node)}</{tag}>")
        elif node.tag == "Anchor":
            url = _safe(node.get("href"))
            body = inlines(node)
            parts.append(f'<a href="{escape(url)}" target="_blank" rel="noopener">{body}</a>' if url else body)
        else:  # 知らないインラインは、中身を装飾なしで出す
            parts.append(inlines(node))
    return "".join(parts)


def figure(node: ET.Element) -> str:
    alt = escape(node.get("alt") or "")
    if node.tag == "ImageFigure":
        url = _safe(node.get("src"))
        if not url:
            return f'<div class="placeholder">画像を表示できません{": " + alt if alt else ""}</div>'
        image = f'<img src="{escape(url)}" alt="{alt}">'
        link = _safe(node.get("href"))
        return f'<a href="{escape(link)}" target="_blank" rel="noopener">{image}</a>' if link else image
    if node.tag in ("EmbedFigure", "FileFigure"):
        url = _safe(node.get("url") or node.get("src"))
        label = escape(node.get("name") or node.get("alt") or url or "ファイル")
        return f'<a class="file" href="{escape(url)}" target="_blank" rel="noopener">{label}</a>' if url else label
    name = _FIGURE_NAMES.get(node.tag, "図")
    return f'<div class="placeholder">{name}{": " + alt if alt else ""}</div>'


def block(node: ET.Element) -> str:
    if node.tag == "TextBlock":
        return "".join(f"<p>{inlines(paragraph)}</p>" for paragraph in node)
    if node.tag == "Cluster":
        if node.get("marker") != "true":
            return f'<div class="cluster">{blocks(node)}</div>'
        tag = "ol" if node.get("ordered") == "true" else "ul"
        items = "".join(
            f'<li class="nested">{block(child)}</li>' if child.tag == "Cluster" else f"<li>{block(child)}</li>"
            for child in node
        )
        return f"<{tag}>{items}</{tag}>"
    if node.tag == "Table":
        rows = ""
        for row in node:
            cells = ""
            for cell in row:
                tag = "th" if cell.get("header") == "true" else "td"
                cells += f"<{tag}>{blocks(cell)}</{tag}>"
            rows += f"<tr>{cells}</tr>"
        return f"<table>{rows}</table>"
    if node.tag.endswith("Figure"):
        return f'<div class="figure">{figure(node)}</div>'
    return ""


def blocks(parent: ET.Element) -> str:
    return "".join(block(child) for child in parent)


def page(element: ET.Element) -> str:
    """ページ 1 つの HTML（<section>）"""
    kind = element.tag.removesuffix("Page").lower()
    title = element.find("title")
    subtitle = element.find("subtitle")
    body = element.find("blocks")
    parts: list[str] = []
    if title is not None:
        parts.append(f"<h1>{inlines(title)}</h1>")
    if subtitle is not None:
        parts.append(f'<p class="subtitle">{inlines(subtitle)}</p>')
    if body is not None:
        parts.append(f'<div class="body">{blocks(body)}</div>')
    if element.tag == "FigurePage":
        parts.extend(f'<div class="figure">{figure(child)}</div>' for child in element if child.tag.endswith("Figure"))
    return f'<section class="page {kind}">{"".join(parts)}</section>'


def fallback(heading: str, reason: str, source: str) -> str:
    """変換できなかったページの代わりのスライド。原文をそのまま載せる"""
    return (
        '<section class="page fallback">'
        f'<div class="fallback-head"><strong>{escape(heading)}</strong><span>{escape(reason)}</span></div>'
        f"<pre>{escape(source)}</pre></section>"
    )
