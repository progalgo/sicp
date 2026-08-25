import json
from pathlib import Path

from PIL import Image

from sicp_epub.coverage import make_coverage, write_coverage

HTML = """<!doctype html>
<html><body><h1>Chapter</h1><custom-block>Review me</custom-block>
<img src="diagram.gif"><blockquote>Quote</blockquote><table><tr><td>cell</td></tr></table>
</body></html>"""


def test_coverage_records_patterns_and_unknown_elements(tmp_path: Path) -> None:
    root = tmp_path / "book"
    root.mkdir()
    (root / "book.html").write_text(HTML, encoding="utf-8")
    Image.new("P", (12, 8)).save(root / "diagram.gif", format="GIF")

    report = make_coverage(root)

    patterns = {pattern["pattern"]: pattern for pattern in report["patterns"]}
    assert patterns["h1"]["provisional_mapping"] == "heading"
    assert patterns["custom-block"]["status"] == "needs-review"
    assert report["gif_categories"][0]["dimensions"] == ["12x8"]


def test_write_coverage_creates_parent_and_json(tmp_path: Path) -> None:
    root = tmp_path / "book"
    root.mkdir()
    (root / "book.html").write_text("<html></html>", encoding="utf-8")
    output = tmp_path / "reports" / "coverage.json"

    write_coverage(output, make_coverage(root))

    assert json.loads(output.read_text(encoding="utf-8"))["schema"] == "sicp-source-coverage-1"
