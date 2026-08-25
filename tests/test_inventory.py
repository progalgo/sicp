import json
from pathlib import Path

from sicp_epub.inventory import make_inventory, write_inventory

HTML = """<!doctype html>
<html><body><h1 id=\"title\">Title</h1><a name=\"legacy\"></a>
<a href=\"other.html#part\">Next</a>
<img src=\"graphics/example.gif\"><table><tr><td>cell</td></tr></table>
</body></html>"""


def test_inventory_counts_source_constructs_and_assets(tmp_path: Path) -> None:
    book_root = tmp_path / "book"
    book_root.mkdir()
    (book_root / "book.html").write_text(HTML, encoding="utf-8")

    inventory = make_inventory(book_root)

    assert inventory["totals"] == {
        "documents": 1,
        "anchors": 2,
        "links": 1,
        "images": 1,
        "tables": 1,
        "assets": 1,
    }
    assert inventory["documents"][0]["elements"]["table"] == 1
    assert inventory["assets"][0]["path"] == "graphics/example.gif"


def test_write_inventory_creates_parent_and_json(tmp_path: Path) -> None:
    root = tmp_path / "book"
    root.mkdir()
    (root / "book.html").write_text("<html></html>", encoding="utf-8")
    output = tmp_path / "reports" / "inventory.json"

    write_inventory(output, make_inventory(root))

    assert json.loads(output.read_text(encoding="utf-8"))["schema"] == "sicp-source-inventory-1"
