"""
Chunker interface — Step 7 swappability layer.

Mirrors get_llm()'s pattern: strategy-specific config lives at construction
time (not passed per-call), selected via CHUNKING_STRATEGY in .env.
"""

from abc import ABC, abstractmethod

from backend.app.embeddings.embedder import embed_texts

from .chunking import Chunk, chunk_document  # existing fixed-size logic, untouched
from .loaders import LoadedDocument
from .semantic_chunking import chunk_document_semantic  # untouched
from .structure_chunking import chunk_document_structural  # untouched


class Chunker(ABC):
    name: str

    @abstractmethod
    def chunk(self, doc: LoadedDocument) -> list[Chunk]: ...


class FixedSizeChunker(Chunker):
    """Wraps the existing naive fixed-size + overlap baseline. No behavior change."""

    name = "fixed_v1"

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, doc: LoadedDocument) -> list[Chunk]:
        return chunk_document(doc, chunk_size=self.chunk_size, overlap=self.overlap)


class SemanticChunker(Chunker):
    """
    Embedding-boundary-based chunking with table protection.

    embed_fn wired here (not passed per-call) so Chunker.chunk(doc) has the
    same signature across strategies - ingest.py doesn't need to know which
    concrete chunker it's holding. Boundary-detection embeddings use
    input_type="document" - see semantic_chunking.py's __main__ block for
    the reasoning (these are neither stored nor a search query, "document"
    is the closer semantic fit).
    """

    name = "semantic_v1"

    def __init__(
        self,
        percentile: float = 75.0,
        min_chars: int = 200,
        max_chars: int = 1200,
    ):
        self.percentile = percentile
        self.min_chars = min_chars
        self.max_chars = max_chars

    def _embed_fn(self, texts: list[str]) -> list[list[float]]:
        return embed_texts(texts, input_type="document")

    def chunk(self, doc: LoadedDocument) -> list[Chunk]:
        return chunk_document_semantic(
            doc,
            embed_fn=self._embed_fn,
            percentile=self.percentile,
            min_chars=self.min_chars,
            max_chars=self.max_chars,
        )


class StructureChunker(Chunker):
    """
    Header-based chunking (## / ###) with the same table protection as
    SemanticChunker. Zero embedding calls to decide boundaries - the
    cheapest and only fully deterministic strategy of the three.
    """

    name = "structure_v1"

    def __init__(self, min_chars: int = 200, max_chars: int = 1200):
        self.min_chars = min_chars
        self.max_chars = max_chars

    def chunk(self, doc: LoadedDocument) -> list[Chunk]:
        return chunk_document_structural(
            doc, min_chars=self.min_chars, max_chars=self.max_chars
        )


def get_chunker(name: str | None = None) -> Chunker:
    import os

    name = name or os.environ.get("CHUNKING_STRATEGY", "fixed_v1")

    if name == "fixed_v1":
        chunk_size = int(os.environ.get("FIXED_CHUNK_SIZE", 500))
        overlap = int(os.environ.get("FIXED_CHUNK_OVERLAP", 50))
        return FixedSizeChunker(chunk_size=chunk_size, overlap=overlap)

    if name == "semantic_v1":
        percentile = float(os.environ.get("SEMANTIC_PERCENTILE", 75.0))
        min_chars = int(os.environ.get("SEMANTIC_MIN_CHARS", 200))
        max_chars = int(os.environ.get("SEMANTIC_MAX_CHARS", 1200))
        return SemanticChunker(
            percentile=percentile, min_chars=min_chars, max_chars=max_chars
        )

    if name == "structure_v1":
        min_chars = int(os.environ.get("STRUCTURE_MIN_CHARS", 200))
        max_chars = int(os.environ.get("STRUCTURE_MAX_CHARS", 1200))
        return StructureChunker(min_chars=min_chars, max_chars=max_chars)

    raise ValueError(f"Unknown chunking strategy: {name}")