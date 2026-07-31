"""
Diff-test: confirm get_chunker() produces byte-identical output to the
pre-refactor chunk_document() call, without touching embeddings or the DB.
"""

from pathlib import Path

from backend.app.ingestion.chunker import get_chunker
from backend.app.ingestion.chunking import chunk_document
from backend.app.ingestion.loaders import load_documents

docs = load_documents(Path("documents"))

chunker = get_chunker()  # reads CHUNKING_STRATEGY from .env
new_chunks = [c for doc in docs for c in chunker.chunk(doc)]
old_chunks = [c for doc in docs for c in chunk_document(doc)]

assert len(new_chunks) == len(old_chunks), (
    f"count mismatch: {len(new_chunks)} vs {len(old_chunks)}"
)

for i, (new, old) in enumerate(zip(new_chunks, old_chunks)):
    assert new.text == old.text, f"chunk {i}: text mismatch"
    assert new.start_char == old.start_char, f"chunk {i}: start_char mismatch"
    assert new.end_char == old.end_char, f"chunk {i}: end_char mismatch"

print(f"✅ {len(new_chunks)} chunks identical — refactor is behavior-preserving")