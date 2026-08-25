"""Build source-pattern and GIF-category evidence for IR design."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import TypedDict
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
from PIL import Image


class PatternCoverage(TypedDict):
    """Observed HTML pattern and its provisional IR disposition."""

    pattern: str
    count: int
    evidence: list[str]
    provisional_mapping: str
    status: str


class GifCategory(TypedDict):
    """Evidence for one provisional GIF asset category."""

    category: str
    files: int
    references: int
    dimensions: list[str]
    evidence: list[str]
    proposed_target: str
    status: str


class CoverageReport(TypedDict):
    """Source coverage matrix for review before IR schema design."""

    schema: str
    root: str
    patterns: list[PatternCoverage]
    gif_categories: list[GifCategory]


_PATTERN_MAPPINGS = {
    "a": "xref-or-anchor; inspect href/name context",
    "blockquote": "quotation",
    "caption": "figure-or-table-caption; inspect parent context",
    "h1": "heading",
    "h2": "heading",
    "h3": "heading",
    "h4": "heading",
    "img": "asset-bearing image; classify from context",
    "li": "list-item",
    "p": "paragraph-or-special-block; inspect class/context",
    "table": "source-layout pending semantic classification",
    "tt": "inline-or-block code; inspect parent/context",
    "ul": "unordered-list or source-layout; inspect context",
}


def _html_documents(root: Path) -> list[Path]:
    """Return HTML documents beneath ``root`` in stable path order."""

    return sorted(path for path in root.rglob("*.html") if path.is_file())


def _asset_path(source: str) -> str | None:
    """Return a local, decoded asset path from an image source value."""

    parsed = urlparse(source)
    if parsed.scheme or parsed.netloc:
        return None
    return unquote(parsed.path).lstrip("/")


def _gif_category(path: str) -> str:
    """Return a provisional category based only on the source filename family."""

    filename = Path(path).name
    if filename.startswith("book-Z-G-D-"):
        return "book-inline-generated-gif"
    if filename.startswith("book-Z-G-"):
        return "book-generated-gif"
    if "-Z-G-" in filename:
        return "chapter-generated-gif"
    return "other-gif"


def make_coverage(root: Path) -> CoverageReport:
    """Build provisional HTML-pattern and GIF-category coverage evidence."""

    pattern_counts: Counter[str] = Counter()
    pattern_evidence: dict[str, set[str]] = {}
    gif_references: Counter[str] = Counter()
    for document in _html_documents(root):
        soup = BeautifulSoup(document.read_bytes(), "html.parser")
        relative_document = document.relative_to(root).as_posix()
        for element in soup.find_all():
            if element.name:
                pattern_counts[element.name] += 1
                pattern_evidence.setdefault(element.name, set()).add(relative_document)
        for image in soup.find_all("img", src=True):
            source = image.get("src")
            if isinstance(source, str):
                asset = _asset_path(source)
                if asset and asset.lower().endswith(".gif"):
                    gif_references[asset] += 1

    patterns: list[PatternCoverage] = [
        {
            "pattern": pattern,
            "count": count,
            "evidence": sorted(pattern_evidence[pattern])[:5],
            "provisional_mapping": _PATTERN_MAPPINGS.get(pattern, "unclassified; inspect source context"),
            "status": "needs-review",
        }
        for pattern, count in sorted(pattern_counts.items())
    ]
    gif_groups: dict[str, list[str]] = {}
    for asset in gif_references:
        gif_groups.setdefault(_gif_category(asset), []).append(asset)

    gif_categories: list[GifCategory] = []
    for category, assets in sorted(gif_groups.items()):
        dimensions: set[str] = set()
        evidence: set[str] = set()
        for asset in sorted(assets):
            asset_path = root / asset
            if asset_path.is_file():
                with Image.open(asset_path) as image:
                    dimensions.add(f"{image.width}x{image.height}")
            evidence.add(asset)
        gif_categories.append(
            {
                "category": category,
                "files": len(assets),
                "references": sum(gif_references[asset] for asset in assets),
                "dimensions": sorted(dimensions),
                "evidence": sorted(evidence)[:10],
                "proposed_target": "retain original GIF in v1; determine SVG/MathML/other target after review",
                "status": "needs-review",
            }
        )

    return {
        "schema": "sicp-source-coverage-1",
        "root": root.as_posix(),
        "patterns": patterns,
        "gif_categories": gif_categories,
    }


def write_coverage(path: Path, report: CoverageReport) -> None:
    """Write a coverage report, creating its parent directory if needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(".source") / "sicp" / "full-text" / "book")
    parser.add_argument("--output", type=Path, default=Path("provenance") / "coverage.json")
    args = parser.parse_args()
    write_coverage(args.output, make_coverage(args.root))
    print(args.output)
