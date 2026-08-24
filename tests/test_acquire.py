import json
import zipfile
from pathlib import Path

import pytest

from sicp_epub.acquire import extract_archive, make_manifest, write_manifest


def make_archive(path: Path, member_name: str = "full-text/book/book.html") -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member_name, "<html></html>")
        archive.writestr("full-text/book/asset.gif", b"GIF89a")


def test_extract_archive_rejects_zip_slip(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    make_archive(archive_path, "../outside.txt")

    with pytest.raises(ValueError, match="unsafe archive member path"):
        extract_archive(archive_path, tmp_path / "extract")


def test_manifest_records_archive_and_extracted_file_hashes(tmp_path: Path) -> None:
    archive_path = tmp_path / "sicp.zip"
    extract_dir = tmp_path / "sicp"
    manifest_path = tmp_path / "source.json"
    make_archive(archive_path)
    extract_archive(archive_path, extract_dir)

    manifest = make_manifest(
        archive_path=archive_path,
        extract_dir=extract_dir,
        url="https://example.test/sicp.zip",
        retrieved_at="2026-08-25T00:00:00+00:00",
        response_headers={"Content-Length": "1"},
    )
    write_manifest(manifest_path, manifest)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_url"] == "https://example.test/sicp.zip"
    assert manifest["archive"]["path"] == archive_path.as_posix()
    assert manifest["extraction"]["path"] == extract_dir.as_posix()
    assert manifest["archive"]["size"] == archive_path.stat().st_size
    assert {entry["path"] for entry in manifest["files"]} == {
        "full-text/book/asset.gif",
        "full-text/book/book.html",
    }
