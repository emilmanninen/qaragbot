"""
Corrected check: find where each chunk's stored (already-stripped) text
actually starts in the source document, and verify the character
immediately before that position is whitespace or the doc's own start.
The previous version incorrectly checked the character before start_char
itself, which points at a whitespace character after the fix (since
chunk_text() strips leading whitespace before storing) — off by one
position from the real word boundary.
"""
from pathlib import Path

from backend.app.db.models import Chunk
from backend.app.db.session import get_session
from backend.app.ingestion.loaders import load_documents

docs_by_id = {d.doc_id: d for d in load_documents(Path("documents"))}

session = get_session()
try:
    rows = session.query(Chunk).filter_by(chunking_strategy="fixed_v1").order_by(
        Chunk.doc_id, Chunk.chunk_index
    ).all()

    real_breaks = []
    for r in rows:
        doc = docs_by_id.get(r.doc_id)
        if doc is None or not r.text:
            continue
        needle = r.text[:20]
        idx = doc.text.find(needle, max(0, r.start_char - 10))
        if idx == -1:
            real_breaks.append((r.doc_id, r.chunk_index, "NOT FOUND", r.text[:40]))
            continue
        if idx > 0 and not doc.text[idx - 1].isspace():
            real_breaks.append((r.doc_id, r.chunk_index, "MID-WORD", r.text[:40]))

    print(f"Checked {len(rows)} rows, {len(real_breaks)} genuine issues:\n")
    for doc_id, idx, kind, preview in real_breaks:
        print(f"  {doc_id} #{idx} [{kind}]: {preview!r}")
finally:
    session.close()