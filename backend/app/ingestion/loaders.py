"""
Ingestion: load markdown docs with YAML front matter into (metadata, body) pairs.

Expected file shape:

    ---
    title: Opintoraha korkeakoulussa
    source_url: https://www.kela.fi/opintoraha-korkeakoulussa
    ---
    # Body markdown starts here...

Deliberately hand-rolled (not python-frontmatter): front-matter splitting isn't
a RAG design decision, it's boilerplate, and doing it by hand keeps there being
zero "magic" behavior to go read library source for later.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class LoadedDocument:
    doc_id: str        # filename stem, e.g. "opintoraha_korkeakoulussa"
    title: str
    source_url: str
    text: str           # body only, front matter stripped


def _split_front_matter(raw: str) -> tuple[dict, str]:
    """Split a file's leading '---' YAML block from its markdown body."""
    if not raw.startswith("---"):
        raise ValueError("File is missing the leading '---' front matter delimiter")

    # raw looks like: "---\n<yaml>\n---\n<body>"
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Malformed front matter: expected two '---' delimiters")

    _, front_matter_raw, body = parts
    metadata = yaml.safe_load(front_matter_raw) or {}
    return metadata, body.lstrip("\n")


def load_document(path: Path) -> LoadedDocument:
    """Load and parse a single markdown file."""
    raw = path.read_text(encoding="utf-8")
    metadata, body = _split_front_matter(raw)

    for required_key in ("title", "source_url"):
        if required_key not in metadata:
            raise ValueError(
                f"{path.name}: missing required front matter key '{required_key}'"
            )

    return LoadedDocument(
        doc_id=path.stem,
        title=metadata["title"],
        source_url=metadata["source_url"],
        text=body,
    )


def load_documents(folder: Path) -> list[LoadedDocument]:
    """Load every markdown file in a folder. Fails loudly if the folder is empty."""
    paths = sorted(folder.glob("*.md"))
    if not paths:
        raise FileNotFoundError(f"No markdown files found in {folder}")
    return [load_document(p) for p in paths]


if __name__ == "__main__":
    # quick manual sanity check — inspect one doc by eye
    import sys

    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("documents")
    docs = load_documents(folder)
    print(f"Loaded {len(docs)} documents\n")
    for d in docs[:1]:
        print(f"doc_id: {d.doc_id}")
        print(f"title: {d.title}")
        print(f"source_url: {d.source_url}")
        print(f"text (first 300 chars):\n{d.text[:300]}")