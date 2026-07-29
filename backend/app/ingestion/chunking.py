"""
Chunking: fixed-size chunking with overlap, whitespace-snapped.

Deliberately naive baseline (Step 1) — no awareness of markdown structure
(headers, tables, paragraphs). This is intentional: it's the thing steps 8-10
compare recursive/semantic chunking against. The only concession made is
snapping chunk boundaries to whitespace so words don't get split mid-token —
that's not "structure awareness," it's just avoiding garbage that would tell
you nothing useful when inspecting output by eye.

Character-based, not token-based. Character count is an imperfect proxy for
what an embedding model actually sees (especially for Finnish, given long
compound words), but no embedding model has been chosen yet (Step 2) — so
tying chunk size to a specific tokenizer here would be premature coupling.
Known limitation, to revisit at Step 7 (swappability) once a model is picked.
"""

from dataclasses import dataclass

from .loaders import LoadedDocument


@dataclass
class Chunk:
    doc_id: str
    chunk_index: int
    text: str
    start_char: int
    end_char: int
    source_url: str
    title: str


def chunk_text(
    text: str, chunk_size: int = 500, overlap: int = 50
) -> list[tuple[str, int, int]]:
    """Split text into (chunk_str, start_char, end_char) tuples."""
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[tuple[str, int, int]] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # snap forward to the next whitespace so we don't cut a word in half
        if end < text_len:
            while end < text_len and not text[end].isspace():
                end += 1

        chunk_str = text[start:end].strip()
        if chunk_str:
            chunks.append((chunk_str, start, end))

        if end >= text_len:
            break

        start = end - overlap

    return chunks


def chunk_document(
    doc: LoadedDocument, chunk_size: int = 500, overlap: int = 50
) -> list[Chunk]:
    """Chunk a single loaded document, carrying its metadata onto each chunk."""
    raw_chunks = chunk_text(doc.text, chunk_size=chunk_size, overlap=overlap)
    return [
        Chunk(
            doc_id=doc.doc_id,
            chunk_index=i,
            text=chunk_str,
            start_char=start,
            end_char=end,
            source_url=doc.source_url,
            title=doc.title,
        )
        for i, (chunk_str, start, end) in enumerate(raw_chunks)
    ]


if __name__ == "__main__":
    # manual inspection entry point — point this at a known hard-case doc, e.g.:
    #   python chunking.py documents/opintotukiaika_korkeakoulussa.md
    import sys
    from pathlib import Path

    from .loaders import load_document

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "documents/opintotukiaika_korkeakoulussa.md"
    )
    doc = load_document(path)
    chunks = chunk_document(doc)

    print(f"{doc.doc_id}: {len(chunks)} chunks\n")
    for c in chunks:
        print(f"--- chunk {c.chunk_index} ({c.start_char}:{c.end_char}) ---")
        print(c.text)
        print()