"""
SQLAlchemy schema for stored chunks + their embeddings.

Uses the `pgvector` package's SQLAlchemy `Vector` column type — this is a thin
column-type shim over Postgres's pgvector extension, not a RAG framework, so
it doesn't conflict with the project's "no LangChain" principle. The actual
similarity search query is written as raw SQL elsewhere (retriever.py, Step 3)
so the distance operator (<=> vs <->) stays fully visible and explainable,
rather than hidden behind an ORM query method.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# voyage-4's default output dimension. If you ever swap embedding models
# (Step 7), this constant — and a migration to match the new model's
# dimension — is exactly the kind of change `embedding_model` (below) is
# meant to help you detect, since old and new vectors aren't comparable.
EMBEDDING_DIM = 1024


class Base(DeclarativeBase):
    pass


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint(
            "doc_id", "chunk_index", "chunking_strategy", name="uq_chunk_identity"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    doc_id: Mapped[str] = mapped_column(String, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)

    # denormalized from the parent document on purpose — at 16 docs, a join
    # buys nothing and costs a query. Revisit only if the corpus grows a lot.
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)

    # forward-compatible for Step 9 (compare strategies without re-embedding
    # everything) and Step 7 (swap embedding models) — cheap to add now,
    # a real migration to add later.
    chunking_strategy: Mapped[str] = mapped_column(
        String, nullable=False, default="fixed_v1"
    )
    embedding_model: Mapped[str] = mapped_column(
        String, nullable=False, default="voyage-4"
    )

    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)