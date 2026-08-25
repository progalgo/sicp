from pathlib import Path

import rnc2rng
from lxml.etree import RelaxNG, fromstring, parse

SCHEMA_PATH = Path("schema/sicp-ir.rnc")
FIXTURE_PATH = Path("tests/fixtures/minimal-ir.xml")


def load_schema() -> RelaxNG:
    with SCHEMA_PATH.open(encoding="utf-8") as source:
        compact_schema = rnc2rng.load(source)
    generated_schema = rnc2rng.dumps(compact_schema)
    return RelaxNG(fromstring(generated_schema.encode("utf-8")))


def test_minimal_ir_fixture_validates() -> None:
    schema = load_schema()
    document = parse(str(FIXTURE_PATH))

    assert schema.validate(document), schema.error_log


def test_schema_rejects_wrong_root() -> None:
    schema = load_schema()
    document = parse(str(FIXTURE_PATH))
    document.getroot().tag = "invalid"

    assert not schema.validate(document)


def test_schema_rejects_repl_entry_without_input() -> None:
    schema = load_schema()
    document = parse(str(FIXTURE_PATH))
    namespace = "{https://progalgo.github.io/sicp/ir/1}"
    repl_entry = document.find(f".//{namespace}repl-entry")

    assert repl_entry is not None
    input_element = repl_entry.find(f"{namespace}input")
    assert input_element is not None
    repl_entry.remove(input_element)

    assert not schema.validate(document)
