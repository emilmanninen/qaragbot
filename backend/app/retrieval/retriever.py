"""
Retrieval logic: embed a query, run pgvector cosine similarity search.

Used by scripts/retrieve.py (CLI sanity check), the generation layer
(generator.py, via generate_answer), and eventually run_eval.py (Step 9).
"""

from sqlalchemy import text

from backend.app.db.session import engine
from backend.app.embeddings.embedder import MODEL_NAME, embed_texts

CHUNKING_STRATEGY = "fixed_v1"  # matches the default in Chunk.chunking_strategy


def embed_query(query: str) -> list[float]:
    """input_type='query' must match the asymmetric embedding scheme from Step 2."""
    embeddings = embed_texts([query], input_type="query")
    return embeddings[0]


def vector_literal(embedding: list[float]) -> str:
    """pgvector needs a string like '[0.123,0.456,...]' to CAST(... AS vector)."""
    return "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"


def retrieve(query: str, k: int = 5):
    query_vec_literal = vector_literal(embed_query(query))

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
                "strategy": CHUNKING_STRATEGY,
                "model": MODEL_NAME,
                "k": k,
            },
        )
        return result.fetchall()