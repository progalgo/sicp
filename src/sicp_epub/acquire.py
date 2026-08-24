"""Acquire and fingerprint the official SICP source archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

SOURCE_URL = "https://mitp-content-server.mit.edu/books/content/sectbyfn/books_pres_0/6515/sicp.zip"


class FileManifest(TypedDict):
    """Hash and size metadata for one extracted source file."""

    path: str
    size: int
    sha256: str


class Manifest(TypedDict):
    """Provenance metadata for one acquired source archive."""

    schema: str
    source_url: str
    retrieved_at: str
    response_headers: dict[str, str]
    archive: dict[str, str | int]
    extraction: dict[str, str]
    files: list[FileManifest]


def extract_archive(archive_path: Path, extract_dir: Path) -> None:
    """Extract an archive after rejecting traversal paths and symbolic links."""

    def _safe_member_path(root: Path, member: zipfile.ZipInfo) -> Path:
        """Resolve an archive member beneath ``root`` or reject unsafe paths."""

        relative = Path(member.filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe archive member path: {member.filename}")

        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError(f"unsafe archive member path: {member.filename}")

        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)

        return target

    def _is_symlink(member: zipfile.ZipInfo) -> bool:
        """Return whether an archive member has a Unix symbolic-link mode."""

        return stat.S_ISLNK(member.external_attr >> 16)

    if extract_dir.exists():
        shutil.rmtree(extract_dir)

    extract_dir.mkdir(parents=True)

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = _safe_member_path(extract_dir, member)

            if member.is_dir():
                continue

            if _is_symlink(member):
                raise ValueError(f"symbolic links are not allowed: {member.filename}")

            target.parent.mkdir(parents=True, exist_ok=True)

            with archive.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)


def make_manifest(
    *,
    archive_path: Path,
    extract_dir: Path,
    url: str,
    retrieved_at: str,
    response_headers: dict[str, str],
) -> Manifest:
    """Build archive, extraction, retrieval, and per-file provenance metadata."""

    def _file_digest(path: Path) -> str:
        """Return a file's SHA-256 digest using streaming I/O."""

        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    
    def _file_manifest(root: Path) -> list[FileManifest]:
        """Return sorted hashes and sizes for all files beneath ``root``."""

        return [
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _file_digest(path),
            }
            for path in sorted(path for path in root.rglob("*") if path.is_file())
        ]

    return {
        "schema": "sicp-source-provenance-1",
        "source_url": url,
        "retrieved_at": retrieved_at,
        "response_headers": response_headers,
        "archive": {
            "path": archive_path.as_posix(),
            "size": archive_path.stat().st_size,
            "sha256": _file_digest(archive_path),
        },
        "extraction": {
            "path": extract_dir.as_posix(),
            "required_path": "full-text/book/book.html",
        },
        "files": _file_manifest(extract_dir),
    }


def write_manifest(manifest_path: Path, manifest: Manifest) -> None:
    """Write a provenance manifest, creating its parent directory if needed."""

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def acquire(
    *,
    url: str = SOURCE_URL,
    archive_path: Path,
    extract_dir: Path,
    manifest_path: Path,
) -> None:
    """Download, safely extract, validate, and fingerprint a source archive."""

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC).isoformat()
    request = urllib.request.Request(url, headers={"User-Agent": "sicp-epub-source-acquirer/0.1"})

    with urllib.request.urlopen(request) as response, archive_path.open("wb") as archive:
        shutil.copyfileobj(response, archive)
        response_headers = {key: value for key, value in response.headers.items()}

    extract_archive(archive_path, extract_dir)

    required_path = extract_dir / "full-text" / "book" / "book.html"
    if not required_path.is_file():
        raise ValueError(f"source archive is missing {required_path.as_posix()}")

    manifest = make_manifest(
        archive_path=archive_path,
        extract_dir=extract_dir,
        url=url,
        retrieved_at=retrieved_at,
        response_headers=response_headers,
    )
    write_manifest(manifest_path, manifest)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--url", default=SOURCE_URL)
    parser.add_argument("--archive", type=Path, default=Path(".source") / "sicp.zip")
    parser.add_argument("--extract", type=Path, default=Path(".source") / "sicp")
    parser.add_argument("--manifest", type=Path, default=Path("provenance") / "source.json")

    args = parser.parse_args()

    acquire(url=args.url, archive_path=args.archive, extract_dir=args.extract, manifest_path=args.manifest)

    print(args.manifest)
