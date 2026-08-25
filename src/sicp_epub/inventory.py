"""Inventory the source HTML corpus before IR design."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import TypedDict

from bs4 import BeautifulSoup


class DocumentInventory(TypedDict):
    """Inventory data for one HTML source document."""

    path: str
    bytes: int
    anchors: list[str]
    links: int
    images: int
    tables: int
    elements: dict[str, int]
    classes: dict[str, int]


class AssetInventory(TypedDict):
    """Inventory data for one referenced source asset."""

    path: str
    references: int
    documents: list[str]


class SourceInventory(TypedDict):
    """Deterministic inventory of the source book tree."""

    schema: str
    root: str
    documents: list[DocumentInventory]
    assets: list[AssetInventory]
    totals: dict[str, int]


def _html_documents(root: Path) -> list[Path]:
    """Return HTML documents beneath ``root`` in stable path order."""

    return sorted(path for path in root.rglob("*.html") if path.is_file())


def _document_inventory(path: Path, root: Path) -> tuple[DocumentInventory, Counter[str]]:
    """Parse one HTML document and return its counts and referenced assets."""

    relative_path = path.relative_to(root).as_posix()
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    elements = Counter(element.name for element in soup.find_all())
    classes: Counter[str] = Counter()
    for element in soup.find_all(class_=True):
        class_values = element.get("class")
        if isinstance(class_values, list):
            classes.update(str(class_value) for class_value in class_values)

    assets: Counter[str] = Counter()
    for image in soup.find_all("img", src=True):
        source = image.get("src")
        if isinstance(source, str):
            assets[source] += 1

    anchors = [
        value
        for element in soup.find_all()
        for attribute in ("id", "name")
        if isinstance(value := element.get(attribute), str)
    ]
    return (
        {
            "path": relative_path,
            "bytes": path.stat().st_size,
            "anchors": anchors,
            "links": len(soup.find_all("a", href=True)),
            "images": len(soup.find_all("img", src=True)),
            "tables": len(soup.find_all("table")),
            "elements": dict(sorted(elements.items())),
            "classes": dict(sorted(classes.items())),
        },
        assets,
    )


def make_inventory(root: Path) -> SourceInventory:
    """Build a deterministic inventory of HTML documents and referenced assets."""

    documents: list[DocumentInventory] = []
    asset_references: dict[str, Counter[str]] = {}
    for path in _html_documents(root):
        document, assets = _document_inventory(path, root)
        documents.append(document)
        for asset in assets:
            asset_references.setdefault(asset, Counter())[document["path"]] += assets[asset]

    asset_inventory: list[AssetInventory] = [
        {
            "path": asset,
            "references": sum(document_counts.values()),
            "documents": sorted(document_counts),
        }
        for asset, document_counts in sorted(asset_references.items())
    ]
    totals = {
        "documents": len(documents),
        "anchors": sum(len(document["anchors"]) for document in documents),
        "links": sum(document["links"] for document in documents),
        "images": sum(document["images"] for document in documents),
        "tables": sum(document["tables"] for document in documents),
        "assets": len(asset_inventory),
    }
    return {
        "schema": "sicp-source-inventory-1",
        "root": root.as_posix(),
        "documents": documents,
        "assets": asset_inventory,
        "totals": totals,
    }


def write_inventory(path: Path, inventory: SourceInventory) -> None:
    """Write an inventory report, creating its parent directory if needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(".source") / "sicp" / "full-text" / "book")
    parser.add_argument("--output", type=Path, default=Path("provenance") / "inventory.json")
    args = parser.parse_args()
    write_inventory(args.output, make_inventory(args.root))
    print(args.output)
