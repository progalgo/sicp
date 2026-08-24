# SICP EPUB Project Instructions

## Project purpose

This repository builds a reproducible EPUB3 edition of the book contained in the official MIT Press `full-text/book/` HTML corpus. The companion site's assignments, instructor material, and unrelated pages are out of scope unless explicitly added later.

## Source custody

- Treat `https://mitp-content-server.mit.edu/books/content/sectbyfn/books_pres_0/6515/sicp.zip` as the source of record.
- Acquire the archive with a reproducible Python command before parsing it.
- Keep the original archive and extracted snapshot outside Git. Record retrieval metadata, archive SHA-256, and per-file hashes in generated provenance output.
- Never silently repair, omit, or reorder source content. Preserve anomalies and report them.
- Do not predict source text, captions, alt text, mathematical notation, vector artwork, or metadata with an LLM. Use parsers and generation tools; require human review for editorial work.

## Intermediate representation

- Do not freeze or implement the IR schema until source inventory and coverage evidence support it.
- Author the schema in RELAX NG compact syntax; generate other schema forms with tools when needed.
- Use one logical book tree plus a separate source map. Do not use legacy HTML page boundaries as the semantic hierarchy.
- Preserve stable internal IDs, original anchors, source file references, source order, links, and asset identity.
- Make unmapped source constructs fail closed through explicit diagnostics or an `unclassified` representation; never drop them silently.
- Keep source-faithful IR separate from future editorial or modernization data.

## Images and modernization

- The first EPUB must package the original GIF files unchanged.
- Inventory and review all GIF categories before creating GitHub issues.
- Create one GitHub issue per reviewed conversion category. Close each issue only through its dedicated pull request.
- Preserve every original GIF as a source asset. Any SVG, MathML, or other replacement is a separate derived asset with provenance and review status.
- Use SVG only for conversions that preserve diagram or line-art content. Use MathML only after human mathematical transcription and review. Do not invent missing descriptions.

## Transformations and output

- Maintain exactly two content XSLT transformations: IR to canonical audit XML and IR to semantic HTML5.
- Python owns acquisition, parsing, comparison orchestration, reporting, and EPUB packaging.
- Prefer native HTML5 semantics such as `main`, `nav`, `section`, headings, `figure`, `figcaption`, `pre`, `code`, `blockquote`, lists, and `aside`.
- The initial EPUB uses one spine document per logical chapter and must not synthesize printed page numbers from HTML file boundaries. Retain source document and anchor provenance instead.
- Run the source audit before packaging. Validate the final EPUB with `epubcheck`.

## Development workflow

- Use Python with Pipenv. Do not add `pyproject.toml`.
- Do not hand-author `Pipfile.lock`; generate it with Pipenv.
- Prefer `pipenv run ...` commands documented in the README. Add a Makefile only when repeated orchestration justifies it.
- Keep changes small and focused. Do not reformat unrelated files or revert user changes.
- After each validated stage, create one focused Git commit, then pause for user review before continuing.
- Before committing, run the narrowest relevant tests, lint checks, provenance/audit checks, and whitespace validation available.
- Do not commit downloaded sources, generated IR, reports, HTML output, EPUBs, or other build artifacts unless explicitly requested.
