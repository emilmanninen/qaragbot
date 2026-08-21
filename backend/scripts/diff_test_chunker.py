"""
Diff-test: confirm FixedSizeChunker (get_chunker("fixed_v1")) produces
byte-identical output to the pre-refactor chunk_document() call, without
touching embeddings or the DB.

Strategy is passed explicitly rather than via get_chunker()'s no-arg
.env-driven default -- that default became structure_v1 in Step 10, and
comparing THAT against the raw fixed_v1 chunk_document() would always
mismatch on chunk count regardless of whether the fixed_v1 refactor itself
is correct. This script's job is narrower: is the fixed_v1 wrapper class
behavior-preserving, independent of whatever strategy happens to be active.
"""

from pathlib import Path

from backend.app.ingestion.chunker import get_chunker
from backend.app.ingestion.chunking import chunk_document
from backend.app.ingestion.loaders import load_documents

docs = load_documents(Path("documents"))

chunker = get_chunker("fixed_v1")
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