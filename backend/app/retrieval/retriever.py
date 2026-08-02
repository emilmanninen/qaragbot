"""
Retrieval logic: embed a query, run pgvector cosine similarity search.

Used by scripts/retrieve.py (CLI sanity check), the generation layer
(generator.py, via generate_answer), and run_eval.py (Step 9).
"""

import os

from sqlalchemy import text

from backend.app.db.session import engine
from backend.app.embeddings.embedder import MODEL_NAME, embed_texts

# Mirrors get_chunker()'s pattern (chunker.py) — same CHUNKING_STRATEGY .env
# var picks the chunking strategy at both ingestion and retrieval time.
CHUNKING_STRATEGY = os.environ.get("CHUNKING_STRATEGY", "fixed_v1")


def embed_query(query: str) -> list[float]:
    """input_type='query' must match the asymmetric embedding scheme from Step 2."""
    embeddings = embed_texts([query], input_type="query")
    return embeddings[0]


def vector_literal(embedding: list[float]) -> str:
    """pgvector needs a string like '[0.123,0.456,...]' to CAST(... AS vector)."""
    return "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"


def search_by_vector(query_vec_literal: str, chunking_strategy: str, k: int = 5):
    """
    Runs the filtered similarity search against an already-embedded query vector.
    Split out from retrieve() so callers that need the same query vector against
    multiple chunking_strategy values (e.g. run_eval.py) don't re-embed per call.
    """
    sql = text("""
        SELECT
            text,
            title,
            source_url,
            embedding <=> CAST(:query_vec AS vector) AS distance
        FROM chunks
        WHERE chunking_strategy = :strategy
          AND embedding_model = :model
        ORDER BY distance ASC
        LIMIT :k
    """)

    with engine.connect() as conn:
        result = conn.execute(
            sql,
            {
                "query_vec": query_vec_literal,
                "strategy": chunking_strategy,
                "model": MODEL_NAME,
                "k": k,
            },
        )
        return result.fetchall()


def retrieve(query: str, k: int = 5, chunking_strategy: str = CHUNKING_STRATEGY):
    """
    Embeds the query and runs a filtered similarity search in one call.
    Unchanged default behavior for existing call sites (generator.py,
    scripts/retrieve.py) — chunking_strategy defaults to the same module
    constant as before this function was split.
    """
    query_vec_literal = vector_literal(embed_query(query))
    return search_by_vector(query_vec_literal, chunking_strategy, k)