"""Parse legacy SICP HTML into a source-aware IR document."""

from __future__ import annotations

import argparse
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import lxml.etree
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

IR_NAMESPACE = "https://progalgo.github.io/sicp/ir/1"
NS = f"{{{IR_NAMESPACE}}}"

ANCHOR_KINDS = {
    "%_chap_": "chapter",
    "%_fig_": "figure",
    "%_idx_": "index-term",
    "%_sec_": "section",
    "%_thm_": "exercise",
    "%_toc_": "toc",
    "call_footnote_": "footnote-reference",
    "footnote_": "footnote",
}


def _element(
    name: str,
    *,
    xml_id: str,
    source_ref: str | None = None,
    legacy_id: str | None = None,
    default_namespace: bool = False,
) -> lxml.etree._Element:
    """Create an IR element with required identity and optional provenance."""

    namespace_map = {None: IR_NAMESPACE} if default_namespace else None
    element = lxml.etree.Element(f"{NS}{name}", {"{http://www.w3.org/XML/1998/namespace}id": xml_id}, nsmap=namespace_map)
    if source_ref:
        element.set("source-ref", source_ref)
    if legacy_id:
        element.set("legacy-id", legacy_id)
    return element


def _source_ref(document: Path, root: Path, element: Tag) -> str:
    """Return a source document reference for an HTML element."""

    anchor = element.get("id") or element.get("name")
    relative = document.relative_to(root).as_posix()
    return f"{relative}#{anchor}" if isinstance(anchor, str) else relative


def _is_navigation(node: Tag) -> bool:
    """Return whether an HTML node belongs to the site's navigation chrome."""

    return node.get("class") == ["navigation"]


def _append_text(parent: lxml.etree._Element, text: str) -> None:
    """Append mixed-content text after the parent's current last child."""

    if len(parent):
        parent[-1].tail = (parent[-1].tail or "") + text
    else:
        parent.text = (parent.text or "") + text


def _anchor_base_id(legacy_id: str) -> str:
    """Return a readable, stable IR ID for a legacy source anchor."""

    kind = "anchor"
    value = legacy_id
    for prefix, candidate_kind in ANCHOR_KINDS.items():
        if legacy_id.startswith(prefix):
            kind = candidate_kind
            value = legacy_id.removeprefix(prefix)
            break
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.").lower() or "unnamed"
    return f"source-{kind}-{value}"


def _unique_anchor_id(legacy_id: str, used_ids: set[str]) -> str:
    """Return a deterministic unique ID derived from a legacy anchor."""

    base_id = _anchor_base_id(legacy_id)
    candidate = base_id
    suffix = 2
    while candidate in used_ids:
        candidate = f"{base_id}-{suffix}"
        suffix += 1
    used_ids.add(candidate)
    return candidate


def _append_anchor(
    parent: lxml.etree._Element,
    source_map: lxml.etree._Element,
    node: Tag,
    document: Path,
    root: Path,
    counter: list[int],
    anchor_targets: dict[str, str],
    used_anchor_ids: set[str],
) -> None:
    """Append a legacy anchor and its source-map entry."""

    legacy_id = node.get("name")
    if not isinstance(legacy_id, str):
        return
    target_id = _unique_anchor_id(legacy_id, used_anchor_ids)
    anchor_targets.setdefault(legacy_id, target_id)
    counter[0] += 1
    lxml.etree.SubElement(source_map, f"{NS}map-entry", source=_source_ref(document, root, node), target=target_id, kind="anchor")
    parent.append(_element("anchor", xml_id=target_id, source_ref=_source_ref(document, root, node), legacy_id=legacy_id))


def _append_inline(
    parent: lxml.etree._Element,
    source_map: lxml.etree._Element,
    node: object,
    document: Path,
    root: Path,
    counter: list[int],
    anchor_targets: dict[str, str],
    used_anchor_ids: set[str],
) -> None:
    """Convert supported inline HTML nodes while preserving their source text."""

    if isinstance(node, NavigableString):
        _append_text(parent, str(node))
        return
    if not isinstance(node, Tag):
        return
    if _is_navigation(node):
        return
    if node.name == "a" and node.get("name"):
        _append_anchor(parent, source_map, node, document, root, counter, anchor_targets, used_anchor_ids)
        if not node.get("href"):
            for child in node.children:
                _append_inline(parent, source_map, child, document, root, counter, anchor_targets, used_anchor_ids)
            return
    if node.name == "tt" and parent.tag == f"{NS}code":
        for child in node.children:
            _append_inline(parent, source_map, child, document, root, counter, anchor_targets, used_anchor_ids)
        return
    counter[0] += 1
    source_ref = _source_ref(document, root, node)
    if node.name in {"em", "i"}:
        target = _element("em", xml_id=f"inline-{counter[0]}", source_ref=source_ref)
    elif node.name in {"strong", "b"}:
        target = _element("strong", xml_id=f"inline-{counter[0]}", source_ref=source_ref)
    elif node.name == "tt":
        target = _element("code", xml_id=f"inline-{counter[0]}", source_ref=source_ref)
    elif node.name == "a" and node.get("href"):
        target = _element("xref", xml_id=f"xref-{counter[0]}", source_ref=source_ref)
        target.set("href", str(node["href"]))
        target.text = node.get_text()
        parent.append(target)
        return
    elif node.name == "img" and node.get("src"):
        target = _element("image", xml_id=f"image-{counter[0]}", source_ref=source_ref)
        target.set("href", str(node["src"]))
        media_type = mimetypes.guess_type(str(node["src"]))[0]
        if media_type:
            target.set("media-type", media_type)
        parent.append(target)
        return
    else:
        for child in node.children:
            _append_inline(parent, source_map, child, document, root, counter, anchor_targets, used_anchor_ids)
        return
    parent.append(target)
    for child in node.children:
        _append_inline(target, source_map, child, document, root, counter, anchor_targets, used_anchor_ids)


def _paragraph(
    document: Path,
    root: Path,
    source_map: lxml.etree._Element,
    paragraph: Tag,
    counter: list[int],
    anchor_targets: dict[str, str],
    used_anchor_ids: set[str],
) -> lxml.etree._Element:
    """Convert one HTML paragraph into an IR paragraph."""

    counter[0] += 1
    target = _element("p", xml_id=f"p-{counter[0]}", source_ref=_source_ref(document, root, paragraph))
    for child in paragraph.children:
        _append_inline(target, source_map, child, document, root, counter, anchor_targets, used_anchor_ids)
    return target


def _list_block(
    document: Path,
    root: Path,
    source_map: lxml.etree._Element,
    node: Tag,
    counter: list[int],
    anchor_targets: dict[str, str],
    used_anchor_ids: set[str],
) -> lxml.etree._Element:
    """Convert an HTML list and its items."""

    counter[0] += 1
    target = _element("list", xml_id=f"list-{counter[0]}", source_ref=_source_ref(document, root, node))
    target.set("type", "ordered" if node.name == "ol" else "unordered")
    for anchor in node.find_all("a", attrs={"name": True}, recursive=False):
        _append_anchor(target, source_map, anchor, document, root, counter, anchor_targets, used_anchor_ids)
    for source_item in node.find_all("li", recursive=False):
        counter[0] += 1
        item = _element("item", xml_id=f"item-{counter[0]}", source_ref=_source_ref(document, root, source_item))
        for child in source_item.children:
            _append_inline(item, source_map, child, document, root, counter, anchor_targets, used_anchor_ids)
        target.append(item)
    return target


def _quotation_block(
    document: Path,
    root: Path,
    source_map: lxml.etree._Element,
    node: Tag,
    counter: list[int],
    anchor_targets: dict[str, str],
    used_anchor_ids: set[str],
) -> lxml.etree._Element:
    """Convert an HTML blockquote to an IR quotation."""

    counter[0] += 1
    target = _element("quotation", xml_id=f"quotation-{counter[0]}", source_ref=_source_ref(document, root, node))
    paragraphs = node.find_all("p", recursive=False)
    if paragraphs:
        for paragraph in paragraphs:
            target.append(_paragraph(document, root, source_map, paragraph, counter, anchor_targets, used_anchor_ids))
    else:
        target.append(_paragraph(document, root, source_map, node, counter, anchor_targets, used_anchor_ids))
    return target


def _table_block(
    document: Path,
    root: Path,
    source_map: lxml.etree._Element,
    node: Tag,
    counter: list[int],
    anchor_targets: dict[str, str],
    used_anchor_ids: set[str],
) -> lxml.etree._Element:
    """Convert a source table while preserving cell order and inline content."""

    counter[0] += 1
    target = _element("table", xml_id=f"table-{counter[0]}", source_ref=_source_ref(document, root, node))
    for source_row in node.find_all("tr"):
        counter[0] += 1
        row = _element("tr", xml_id=f"tr-{counter[0]}", source_ref=_source_ref(document, root, source_row))
        for source_cell in source_row.find_all(["th", "td"], recursive=False):
            counter[0] += 1
            cell = _element(source_cell.name, xml_id=f"{source_cell.name}-{counter[0]}", source_ref=_source_ref(document, root, source_cell))
            for child in source_cell.children:
                _append_inline(cell, source_map, child, document, root, counter, anchor_targets, used_anchor_ids)
            row.append(cell)
        if len(row):
            target.append(row)
    return target


def _note_block(
    document: Path,
    root: Path,
    source_map: lxml.etree._Element,
    node: Tag,
    counter: list[int],
    anchor_targets: dict[str, str],
    used_anchor_ids: set[str],
) -> lxml.etree._Element:
    """Convert a source footnote container into a note block."""

    counter[0] += 1
    target = _element("note", xml_id=f"note-{counter[0]}", source_ref=_source_ref(document, root, node))
    target.set("type", "footnotes")
    for child in node.find_all(recursive=False):
        if child.name == "p":
            converted = _paragraph(document, root, source_map, child, counter, anchor_targets, used_anchor_ids)
            if "".join(converted.itertext()).strip() or len(converted):
                target.append(converted)
        else:
            target.append(_source_layout(document, root, source_map, child, counter, anchor_targets, used_anchor_ids))
    if not len(target):
        target.append(_paragraph(document, root, source_map, node, counter, anchor_targets, used_anchor_ids))
    return target


def _source_layout(
    document: Path,
    root: Path,
    source_map: lxml.etree._Element,
    node: Tag,
    counter: list[int],
    anchor_targets: dict[str, str],
    used_anchor_ids: set[str],
) -> lxml.etree._Element:
    """Preserve a presentation-only source container without assigning semantics."""

    counter[0] += 1
    target = _element("source-layout", xml_id=f"source-layout-{counter[0]}", source_ref=_source_ref(document, root, node))
    target.set("source-element", node.name)
    if node.name == "a" and node.get("name"):
        _append_anchor(target, source_map, node, document, root, counter, anchor_targets, used_anchor_ids)
    for anchor in node.find_all("a", attrs={"name": True}):
        _append_anchor(target, source_map, anchor, document, root, counter, anchor_targets, used_anchor_ids)
    for image in node.find_all("img"):
        _append_inline(target, source_map, image, document, root, counter, anchor_targets, used_anchor_ids)
    raw = lxml.etree.SubElement(target, f"{NS}raw")
    raw.text = node.get_text(" ", strip=False)
    return target


def _resolve_xrefs(book: lxml.etree._Element, anchor_targets: dict[str, str]) -> None:
    """Resolve source href fragments to stable IR target IDs."""

    for xref in book.iter(f"{NS}xref"):
        href = xref.get("href")
        if not href:
            continue
        fragment = unquote(urlsplit(href).fragment)
        if fragment:
            xref.set("target", anchor_targets.get(fragment, _anchor_base_id(fragment)))


def parse_document(document: Path, root: Path) -> lxml.etree._Element:
    """Parse one HTML document into a source-aware IR book fragment."""

    soup = BeautifulSoup(document.read_bytes(), "lxml")
    book = _element("book", xml_id="book", default_namespace=True)
    metadata = lxml.etree.SubElement(book, f"{NS}metadata")
    lxml.etree.SubElement(metadata, f"{NS}title").text = soup.title.get_text(" ", strip=True) if soup.title else document.stem
    lxml.etree.SubElement(metadata, f"{NS}author").text = "Harold Abelson"
    corpus = lxml.etree.SubElement(book, f"{NS}source-corpus", url="", **{"archive-sha256": ""})
    lxml.etree.SubElement(corpus, f"{NS}source-document", path=document.relative_to(root).as_posix(), sha256="", size=str(document.stat().st_size))
    source_map = lxml.etree.SubElement(book, f"{NS}source-map")
    body = lxml.etree.SubElement(book, f"{NS}bodymatter")
    chapter = _element("chapter", xml_id="chapter-1", source_ref=document.relative_to(root).as_posix())
    heading = _element("heading", xml_id="heading-1", source_ref=document.relative_to(root).as_posix())
    heading.set("level", "1")
    heading.text = soup.title.get_text(" ", strip=True) if soup.title else document.stem
    chapter.append(heading)
    body.append(chapter)
    current_container = chapter
    section_stack: list[tuple[int, lxml.etree._Element]] = [(0, chapter)]
    counter = [1]
    anchor_targets: dict[str, str] = {}
    used_anchor_ids: set[str] = set()
    for node in soup.body.find_all(["a", "h1", "h2", "h3", "h4", "p", "blockquote", "ul", "ol", "table", "pre", "div"], recursive=False) if soup.body else []:
        if _is_navigation(node):
            continue
        if node.name == "a" and node.get("name"):
            _append_anchor(current_container, source_map, node, document, root, counter, anchor_targets, used_anchor_ids)
            continue
        if node.name in {"h1", "h2", "h3", "h4"}:
            counter[0] += 1
            level = int(node.name[1:])
            target = _element("heading", xml_id=f"heading-{counter[0]}", source_ref=_source_ref(document, root, node))
            target.set("level", str(level))
            target.text = node.get_text(" ", strip=True)
            section = _element("section", xml_id=f"section-{counter[0]}", source_ref=_source_ref(document, root, node))
            section.append(target)
            while section_stack[-1][0] >= level:
                section_stack.pop()
            section_stack[-1][1].append(section)
            section_stack.append((level, section))
            current_container = section
        elif node.name == "p":
            paragraph = _paragraph(document, root, source_map, node, counter, anchor_targets, used_anchor_ids)
            if "".join(paragraph.itertext()).strip() or len(paragraph):
                current_container.append(paragraph)
        elif node.name in {"ul", "ol"}:
            current_container.append(_list_block(document, root, source_map, node, counter, anchor_targets, used_anchor_ids))
        elif node.name == "blockquote":
            current_container.append(_quotation_block(document, root, source_map, node, counter, anchor_targets, used_anchor_ids))
        elif node.name == "table":
            current_container.append(_table_block(document, root, source_map, node, counter, anchor_targets, used_anchor_ids))
        elif node.name == "div" and node.get("class") == ["footnote"]:
            current_container.append(_note_block(document, root, source_map, node, counter, anchor_targets, used_anchor_ids))
        elif node.name == "a" and node.get("href"):
            counter[0] += 1
            paragraph = _element("p", xml_id=f"p-{counter[0]}", source_ref=_source_ref(document, root, node))
            _append_inline(paragraph, source_map, node, document, root, counter, anchor_targets, used_anchor_ids)
            current_container.append(paragraph)
        else:
            current_container.append(_source_layout(document, root, source_map, node, counter, anchor_targets, used_anchor_ids))
            _resolve_xrefs(book, anchor_targets)
    return book


def write_ir(path: Path, document: Path, root: Path) -> None:
    """Parse one source document and write its XML IR."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tree = lxml.etree.ElementTree(parse_document(document, root))
    tree.write(path, encoding="UTF-8", xml_declaration=True, pretty_print=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--root", type=Path, default=Path(".source") / "sicp" / "full-text" / "book")
    parser.add_argument("--output", type=Path, default=Path("build") / "ir" / "document.xml")
    args = parser.parse_args()
    write_ir(args.output, args.document, args.root)
    print(args.output)
