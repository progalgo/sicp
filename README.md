# SICP EPUB

A reproducible pipeline for deriving a semantic EPUB3 edition from the official MIT Press HTML distribution of *Structure and Interpretation of Computer Programs*.

## Status

The repository is currently at the bootstrap stage. No source archive, extracted source, intermediate representation, transformed HTML, or EPUB is checked into Git.

Implementation is intentionally staged. The source snapshot will be acquired and fingerprinted before any parser or schema is written. The source-faithfulness contract and the IR coverage matrix must be reviewed before the IR v1 schema is frozen.

## Source of record

The initial source of record is the official MIT Press archive:

`https://mitp-content-server.mit.edu/books/content/sectbyfn/books_pres_0/6515/sicp.zip`

The target edition is the book in the archive's `full-text/book/` tree. Companion-site assignments, instructor material, and other pages are outside the initial scope.

The MIT Press companion site identifies the book text as licensed under the [Creative Commons Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/). Any distribution of derived work must preserve the required attribution and share-alike terms. The project will record retrieval metadata and SHA-256 fingerprints for custody, but will not commit the downloaded archive or generated book artifacts.

## Design commitments

- Python is the implementation language and Pipenv manages dependencies.
- This project intentionally does not use `pyproject.toml`.
- Generated lock files are produced by Pipenv, never hand-authored.
- The source-faithful IR is authoritative for v1 and preserves source filenames, anchors, assets, order, and unresolved anomalies.
- The first EPUB uses original GIF assets unchanged. Each later GIF modernization category will be reviewed, tracked by a GitHub issue, and delivered by its own dedicated pull request.
- No source text, captions, alt text, mathematical transcription, vector artwork, or metadata is guessed by an LLM.
- Granular commits are created only after the corresponding stage passes its focused validation. After each such commit, work pauses for review.

## Development

Requires Python 3.14 and Pipenv.

```powershell
pipenv install --dev
pipenv run python -m src.sicp_epub
pipenv run pytest
```

The full acquisition, inventory, IR validation, audit, transformation, and EPUB commands will be documented here as each stage becomes executable. `epubcheck` will be an explicit external validation prerequisite when EPUB packaging is implemented.

## Repository layout

```text
Pipfile                 Pipenv dependency declarations
src/sicp_epub/          Python implementation
schema/                 Versioned IR schema (planned)
xslt/                   The two required XSLT transformations (planned)
tests/                  Focused automated tests
```
