"""
CLI: run the full ingestion pipeline (load -> chunk -> embed -> store) over
a folder of documents.

Usage:
    python -m backend.scripts.ingest documents/

This is the MVP's offline ingestion step (Step 2). No FastAPI involved yet —
that's Step 5. Re-running this script is safe: the unique constraint on
(doc_id, chunk_index, chunking_strategy) means a plain re-run will fail on
duplicate rows rather than silently double-inserting, which is a deliberate
choice — silent duplication would be a much harder bug to notice later than
a loud constraint violation now.
"""

import sys
from pathlib import Path

from backend.app.db.models import Base, Chunk
from backend.app.db.session import engine, get_session
from backend.app.embeddings.embedder import MODEL_NAME, embed_texts
from backend.app.ingestion.chunking import chunk_document
from backend.app.ingestion.loaders import load_documents


def run_ingestion(documents_dir: Path) -> None:
    print(f"Loading documents from {documents_dir}...")
    docs = load_documents(documents_dir)
    print(f"Loaded {len(docs)} documents")

    print("Chunking...")
    all_chunks = [chunk for doc in docs for chunk in chunk_document(doc)]
    print(f"Produced {len(all_chunks)} chunks total")

    print(f"Embedding {len(all_chunks)} chunks via {MODEL_NAME} (input_type=document)...")
    texts = [c.text for c in all_chunks]
    vectors = embed_texts(texts, input_type="document")

    print("Creating table (if not exists)...")
    Base.metadata.create_all(engine)

    print("Inserting rows...")
    session = get_session()
    try:
        rows = [
            Chunk(
                doc_id=c.doc_id,
                chunk_index=c.chunk_index,
                text=c.text,
                start_char=c.start_char,
                end_char=c.end_char,
                source_url=c.source_url,
                title=c.title,
                chunking_strategy="fixed_v1",
                embedding_model=MODEL_NAME,
                embedding=vector,
            )
            for c, vector in zip(all_chunks, vectors)
        ]
        session.add_all(rows)
        session.commit()
        print(f"Inserted {len(rows)} rows into chunks table.")
    finally:
        session.close()


if __name__ == "__main__":
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("documents")
    run_ingestion(folder)