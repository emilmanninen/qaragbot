"""
Step 3: standalone retrieval sanity-check script.

Hardcoded query -> embed (input_type="query") -> pgvector cosine similarity
search against `chunks` -> print top-k chunks + sources.

No FastAPI yet. No vector index yet (312 rows -> exact sequential scan is
correct and fast; an ANN index would introduce recall loss into the very
thing Step 8-9 needs as ground truth).

Run the same way as ingest.py, from the repo root:
    python -m backend.scripts.retrieve

Filters on chunking_strategy/embedding_model even though there's currently
only one of each in the table: once Step 9 adds more strategies to the same
table (per the schema's forward-compatible columns), an unfiltered query
would silently mix distances from different chunking strategies and
embedding spaces into one ranking — meaningless, since a voyage-4 distance
isn't comparable to a different model's distance. Filtering now costs
nothing and avoids that failure mode later.
"""

from sqlalchemy import text

from backend.app.db.session import engine
from backend.app.embeddings.embedder import MODEL_NAME, embed_texts

CHUNKING_STRATEGY = "fixed_v1"  # matches the default in Chunk.chunking_strategy

# Known-answer sanity check — pick something you can verify by reading the source doc yourself.
QUERY = "Mikä on vuosituloraja vuonna 2025, jos nostan opintotukea 9 kuukautta?"
TOP_K = 5


def embed_query(query: str) -> list[float]:
    """input_type='query' must match the asymmetric embedding scheme from Step 2."""
    embeddings = embed_texts([query], input_type="query")
    return embeddings[0]


def vector_literal(embedding: list[float]) -> str:
    """pgvector needs a string like '[0.123,0.456,...]' to CAST(... AS vector)."""
    return "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"


def retrieve(query: str, k: int = TOP_K):
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


def main():
    rows = retrieve(QUERY, TOP_K)
    print(f"Query: {QUERY}\n")
    for i, row in enumerate(rows, start=1):
        chunk_text, title, source_url, distance = row
        snippet = chunk_text.strip().replace("\n", " ")
        if len(snippet) > 300:
            snippet = snippet[:300] + "..."
        print(f"[{i}] distance={distance:.4f}  source={title} ({source_url})")
        print(f"    {snippet}\n")


if __name__ == "__main__":
    main()