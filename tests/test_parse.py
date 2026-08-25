from pathlib import Path

import rnc2rng
from lxml.etree import RelaxNG, fromstring, parse

from sicp_epub.parse import parse_document

SCHEMA_PATH = Path("schema/sicp-ir.rnc")


def load_schema() -> RelaxNG:
    with SCHEMA_PATH.open(encoding="utf-8") as source:
        compact_schema = rnc2rng.load(source)
    return RelaxNG(fromstring(rnc2rng.dumps(compact_schema).encode("utf-8")))


def test_parser_emits_schema_valid_ir(tmp_path: Path) -> None:
    root = tmp_path / "book"
    root.mkdir()
    document = root / "example.html"
    document.write_text(
        """<html><head><title>Example</title></head><body>
        <p><div class=\"navigation\">[Go to first, previous, next page]</div></p>
        <a name=\"%_sec_1.1\"></a><h2>Section</h2>
        <h3>First subsection</h3><p>First body.</p>
        <h3>Second subsection</h3>
        <p>A <a name=\"%_idx_1\"></a><tt><a name=\"%_idx_code\"></a><tt>procedure</tt></tt>, <tt><i>441</i></tt>, an <a href=\"#%_idx_2\">internal link</a>, and <a href=\"other.html#target\">external link</a>.</p>
        <ul><li>First</li><li>Second</li></ul>
        <blockquote>Quoted text</blockquote>
        <table><tr><th>Head</th><td>Cell</td></tr></table>
        <div><a name=\"%_idx_2\"></a>Layout content</div>
        </body></html>""",
        encoding="utf-8",
    )

    ir = parse_document(document, root)

    output = tmp_path / "ir.xml"
    ir.getroottree().write(output, encoding="UTF-8", xml_declaration=True)
    serialized = output.read_text(encoding="utf-8")
    schema = load_schema()
    assert schema.validate(parse(str(output))), schema.error_log
    assert '<book xmlns="https://progalgo.github.io/sicp/ir/1"' in serialized
    assert "ns0:" not in serialized
    assert "Go to first" not in "".join(ir.itertext())
    assert len(ir.xpath("//*[local-name()='section']")) == 3
    subsections = ir.xpath("//*[local-name()='section']/*[local-name()='section']")
    assert len(subsections) == 2
    assert not subsections[0].xpath("./*[local-name()='section']")
    assert len(subsections[1].xpath("./*[local-name()='p']")) == 1
    paragraph_text = "".join(subsections[1].xpath("./*[local-name()='p']")[0].itertext())
    assert paragraph_text == "A procedure, 441, an internal link, and external link."
    assert len(ir.xpath("//*[local-name()='anchor']")) == 4
    assert len(ir.xpath("//*[local-name()='map-entry']")) == 4
    assert not ir.xpath("//*[local-name()='page-break']")
    anchors = {anchor.get("legacy-id"): anchor.get("{http://www.w3.org/XML/1998/namespace}id") for anchor in ir.xpath("//*[local-name()='anchor']")}
    assert anchors == {
        "%_sec_1.1": "source-section-1.1",
        "%_idx_1": "source-index-term-1",
        "%_idx_code": "source-index-term-code",
        "%_idx_2": "source-index-term-2",
    }
    xrefs = ir.xpath("//*[local-name()='xref']")
    assert xrefs[0].get("target") == "source-index-term-2"
    assert xrefs[1].get("target") == "source-anchor-target"
    assert len(ir.xpath("//*[local-name()='list']/*[local-name()='item']")) == 2
    assert "Quoted text" in "".join(ir.xpath("//*[local-name()='quotation']")[0].itertext())
    assert len(ir.xpath("//*[local-name()='table']/*[local-name()='tr']")) == 1
    assert ir.xpath("//*[local-name()='source-layout']")[0].get("source-element") == "div"
    assert not ir.xpath("//*[local-name()='unclassified']")
