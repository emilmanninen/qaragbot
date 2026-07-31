"""
Chunker interface — Step 7 swappability layer.

Mirrors get_llm()'s pattern: strategy-specific config lives at construction
time (not passed per-call), selected via CHUNKING_STRATEGY in .env.
"""

from abc import ABC, abstractmethod

from .loaders import LoadedDocument
from .chunking import Chunk, chunk_document  # existing fixed-size logic, untouched


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


def get_chunker(name: str | None = None) -> Chunker:
    import os

    name = name or os.environ.get("CHUNKING_STRATEGY", "fixed_v1")

    if name == "fixed_v1":
        chunk_size = int(os.environ.get("FIXED_CHUNK_SIZE", 500))
        overlap = int(os.environ.get("FIXED_CHUNK_OVERLAP", 50))
        return FixedSizeChunker(chunk_size=chunk_size, overlap=overlap)

    raise ValueError(f"Unknown chunking strategy: {name}")