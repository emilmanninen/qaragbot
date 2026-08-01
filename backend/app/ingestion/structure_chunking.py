"""
Structure-aware chunking: split primarily on markdown headers (## and ###),
protecting tables the same way semantic_chunking.py does. No embeddings
involved in deciding boundaries — the document's own authoring structure IS
the signal, not a proxy for it.

Design decisions (defend these in interviews):

1. Boundaries are ## and ### headers only. # is just the per-doc title (one
   per file, not a real section split). #### and deeper are typically
   worked-example sub-headers ("#### Esimerkki: ...") — folding these into
   their parent section, rather than treating them as their own boundary,
   is a deliberate choice: it keeps a rule and its own worked example
   together, and directly avoids the asumislisa finding from semantic
   chunking, where a rule got separated from its own qualifying condition
   because the two sentences were lexically dissimilar despite living under
   the same header.

2. Tables are extracted/protected using the exact same extract_tables /
   _reinsert_tables mechanism as semantic_chunking.py (imported directly,
   not reimplemented) — table integrity is a corpus-level property this
   project cares about, not something specific to one chunking strategy.

3. Oversized sections (between two headers, longer than max_chars) fall
   back to the existing fixed-size chunk_text() as a sub-routine. This
   reuse is safe even with tables present: by the time chunk_text() runs,
   each table has already been replaced by a single short placeholder
   token, so a character-count-based split can never land inside a table's
   real content — there isn't any table content left in the text at that
   point, just an opaque marker.

4. Undersized sections get merged into the following section, same pattern
   as semantic chunking's min_chars pass. A short section under a deep
   sub-header (e.g. a one-line "#### Esimerkki" stub before the next real
   header) shouldn't stand alone as its own chunk.

5. Zero embedding calls to decide boundaries — the cheapest and only fully
   deterministic strategy of the three: same input always produces the
   same output, no threshold to tune, free and instant to re-run.
"""

import re

from .chunking import Chunk, chunk_text
from .loaders import LoadedDocument
from .semantic_chunking import extract_tables, _reinsert_tables

# matches a line that is a level-2 or level-3 markdown header (## or ###,
# not #### or deeper, not a single #)
_HEADER_RE = re.compile(r"^(#{2,3})\s+.*$", re.MULTILINE)


def split_by_headers(text: str) -> list[str]:
    """
    Split text into sections at ## / ### header boundaries. Each section
    (except possibly the first) starts with its own header line.
    """
    matches = list(_HEADER_RE.finditer(text))
    if not matches:
        return [text] if text.strip() else []

    sections = []
    # anything before the first header (e.g. the doc's # title + intro)
    if matches[0].start() > 0:
        sections.append(text[: matches[0].start()])

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(text[start:end])

    return [s for s in sections if s.strip()]


def _merge_small_sections(sections: list[str], min_chars: int) -> list[str]:
    """Merge sections below min_chars into the following section."""
    if not sections:
        return sections
    merged: list[str] = []
    carry = ""
    for sec in sections:
        combined = (carry + "\n\n" + sec) if carry else sec
        if len(combined) < min_chars:
            carry = combined
            continue
        merged.append(combined)
        carry = ""
    if carry:
        if merged:
            merged[-1] = merged[-1] + "\n\n" + carry
        else:
            merged.append(carry)
    return merged


def _split_large_sections(
    sections: list[str], max_chars: int, overlap: int = 50
) -> list[str]:
    """
    Sections over max_chars get handed to the existing fixed-size splitter.
    Safe around tables: by this point tables are already reduced to short
    placeholder tokens, so chunk_text() has no table content left to cut
    through.
    """
    result: list[str] = []
    for sec in sections:
        if len(sec) <= max_chars:
            result.append(sec)
            continue
        sub_chunks = chunk_text(sec, chunk_size=max_chars, overlap=overlap)
        result.extend(s for s, _, _ in sub_chunks)
    return result


def chunk_document_structural(
    doc: LoadedDocument,
    min_chars: int = 200,
    max_chars: int = 1200,
) -> list[Chunk]:
    protected_text, tables = extract_tables(doc.text)

    sections = split_by_headers(protected_text)
    sections = _merge_small_sections(sections, min_chars=min_chars)
    sections = _split_large_sections(sections, max_chars=max_chars)
    sections = _merge_small_sections(sections, min_chars=min_chars)

    chunks = []
    cursor = 0
    for i, sec in enumerate(sections):
        raw_text = _reinsert_tables(sec, tables).strip()
        if not raw_text:
            continue
        start_char = doc.text.find(raw_text[:50], cursor) if raw_text else cursor
        start_char = max(start_char, cursor)
        end_char = start_char + len(raw_text)
        chunks.append(
            Chunk(
                doc_id=doc.doc_id,
                chunk_index=i,
                text=raw_text,
                start_char=start_char,
                end_char=end_char,
                source_url=doc.source_url,
                title=doc.title,
            )
        )
        cursor = end_char

    return chunks


if __name__ == "__main__":
    # manual inspection entry point — no embeddings involved, free and
    # instant to re-run, e.g.:
    #   python -m backend.app.ingestion.structure_chunking documents/opintuki_asumislisa.md
    import sys
    from pathlib import Path

    from .loaders import load_document

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "documents/opintuki_asumislisa.md"
    )
    doc = load_document(path)
    chunks = chunk_document_structural(doc)

    print(f"{doc.doc_id}: {len(chunks)} chunks\n")
    for c in chunks:
        print(f"--- chunk {c.chunk_index} ({c.start_char}:{c.end_char}) ---")
        print(c.text)
        print()