"""
Semantic chunking: split text at embedding-similarity boundaries rather than
fixed character counts.

Design decisions (defend these in interviews):

1. Tables are extracted and protected BEFORE semantic splitting runs. Semantic
   boundary detection operates on sentence embeddings — it has no concept of
   "this is a table row," so left unprotected it would happily place a chunk
   boundary mid-table, exactly the failure mode this strategy is meant to
   avoid on the tulojen_vaikutus/opintotukiaika hard cases. Tables are pulled
   out, replaced with a placeholder token, and reinserted whole after boundary
   detection completes.

2. Boundaries are windowed (each sentence embedded together with its
   immediate neighbor before/after), not single-sentence. Single-sentence
   embeddings are noisy for this purpose — short sentences in particular
   produce unstable distances. Windowing trades a little boundary precision
   for materially more stable breakpoints.

3. Breakpoints are percentile-based (relative to each document's own distance
   distribution), not a fixed global cosine threshold. A fixed threshold
   assumes every document has the same "typical" sentence-to-sentence
   semantic distance, which doesn't hold across docs of different length,
   register, or table-density. Percentile-based means: "this is a bigger
   topic jump than N% of this document's other sentence transitions" — a
   claim that's actually explainable, vs. a magic number pulled from nowhere.

4. Segments below min_chars are merged into their neighbor; segments above
   max_chars are split (never mid-sentence, never mid-table — table integrity
   wins over the size cap, so a genuinely huge table can still exceed
   max_chars as its own segment). Without this, boundary detection alone can
   produce wildly uneven chunk sizes on documents with long stretches of
   similar-register text (seen firsthand: opintotukiaika_korkeakoulussa.md
   produced chunks over 4000 chars with percentile=90 and no size ceiling).

5. This is real added ingestion cost, worth stating plainly: every sentence
   in the corpus gets embedded once just to decide boundaries, on top of the
   embeddings stored for retrieval. For 312 chunks / 16 docs this is small
   and cheap via Voyage, but it's a genuine tradeoff vs. fixed-size and
   structure-aware chunking, which need zero extra embedding calls to decide
   where to split.

Known limitation: boundary detection can still land inside a logically single
unit that isn't a table (e.g. a worked example split across two chunks, seen
in opintotukiaika_korkeakoulussa.md). Table-protection doesn't cover this —
would need example-block protection too if it turns out to matter empirically
at eval time. Deliberately not solved here; revisit only if Step 9's eval
surfaces it as a real recall problem.
"""

import re
from dataclasses import dataclass

import numpy as np

from .chunking import Chunk
from .loaders import LoadedDocument

TABLE_PLACEHOLDER = "\x00TABLE_{}\x00"

# naive but adequate sentence splitter: split on '. ', '! ', '? ' followed by
# a capital letter or end of string. Deliberately not handling every Finnish
# abbreviation edge case — false splits here cost a slightly noisier boundary
# signal, not a correctness bug, since sentences just feed distance
# computation, not the final chunk boundaries themselves.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÅ])")

# a markdown table block: consecutive lines that look like '| ... | ... |'
_TABLE_BLOCK_RE = re.compile(r"(?:^\|.*\|[ \t]*$\n?)+", re.MULTILINE)


def extract_tables(text: str) -> tuple[str, list[str]]:
    """
    Replace each markdown table block with a placeholder token.
    Returns (text_with_placeholders, list_of_table_blocks) so callers can
    reinsert the originals verbatim after semantic splitting.
    """
    tables: list[str] = []

    def _replace(match: re.Match) -> str:
        tables.append(match.group(0))
        return TABLE_PLACEHOLDER.format(len(tables) - 1) + "\n"

    protected = _TABLE_BLOCK_RE.sub(_replace, text)
    return protected, tables


def _reinsert_tables(text: str, tables: list[str]) -> str:
    for i, table in enumerate(tables):
        text = text.replace(TABLE_PLACEHOLDER.format(i), table.rstrip("\n"))
    return text


def split_sentences(text: str) -> list[str]:
    """Split protected text into sentences, dropping empty fragments."""
    raw = _SENTENCE_SPLIT_RE.split(text)
    return [s.strip() for s in raw if s.strip()]


@dataclass
class _Segment:
    sentences: list[str]

    @property
    def text(self) -> str:
        return " ".join(self.sentences)


def _windowed_texts(sentences: list[str]) -> list[str]:
    """Each sentence combined with its immediate neighbors, for embedding."""
    windows = []
    for i, s in enumerate(sentences):
        lo = max(0, i - 1)
        hi = min(len(sentences), i + 2)
        windows.append(" ".join(sentences[lo:hi]))
    return windows


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return 1.0 - float(np.dot(a, b) / denom)


def find_breakpoints(
    sentences: list[str],
    embed_fn,
    percentile: float = 75.0,
) -> list[int]:
    """
    Returns sentence indices where a new chunk should START (i.e. a boundary
    exists between index-1 and index). embed_fn: list[str] -> list[vector].
    """
    if len(sentences) < 2:
        return []

    windows = _windowed_texts(sentences)
    vectors = [np.array(v) for v in embed_fn(windows)]

    distances = [
        _cosine_distance(vectors[i], vectors[i + 1])
        for i in range(len(vectors) - 1)
    ]
    threshold = float(np.percentile(distances, percentile))

    return [i + 1 for i, d in enumerate(distances) if d > threshold]


def _group_by_breakpoints(
    sentences: list[str], breakpoints: list[int]
) -> list[_Segment]:
    segments, start = [], 0
    for bp in breakpoints:
        segments.append(_Segment(sentences[start:bp]))
        start = bp
    segments.append(_Segment(sentences[start:]))
    return segments


def _merge_small_segments(
    segments: list[_Segment], min_chars: int = 200
) -> list[_Segment]:
    """Merge segments below min_chars into the following segment."""
    if not segments:
        return segments
    merged: list[_Segment] = []
    carry: list[str] = []
    for seg in segments:
        sentences = carry + seg.sentences
        if len(" ".join(sentences)) < min_chars:
            carry = sentences
            continue
        merged.append(_Segment(sentences))
        carry = []
    if carry:
        if merged:
            merged[-1] = _Segment(merged[-1].sentences + carry)
        else:
            merged.append(_Segment(carry))
    return merged


def _sentence_or_table_length(unit: str, tables: list[str]) -> int:
    """Length a sentence/placeholder would have after table reinsertion."""
    return len(_reinsert_tables(unit, tables))


def _split_large_segment(
    segment: _Segment, tables: list[str], max_chars: int
) -> list[_Segment]:
    """
    Pack a segment's sentences into sub-segments under max_chars, without ever
    splitting a single sentence or table placeholder. If one sentence/table
    alone exceeds max_chars (e.g. a genuinely huge table), it becomes its own
    oversized segment rather than being forced apart — table integrity wins
    over the size cap. Known limitation: no further table-splitting logic.
    """
    sub_segments: list[_Segment] = []
    current: list[str] = []
    current_len = 0

    for unit in segment.sentences:
        unit_len = _sentence_or_table_length(unit, tables)
        if current and current_len + unit_len + 1 > max_chars:
            sub_segments.append(_Segment(current))
            current = []
            current_len = 0
        current.append(unit)
        current_len += unit_len + 1

    if current:
        sub_segments.append(_Segment(current))

    return sub_segments


def chunk_document_semantic(
    doc: LoadedDocument,
    embed_fn,
    percentile: float = 75.0,
    min_chars: int = 200,
    max_chars: int = 1200,
) -> list[Chunk]:
    """
    Semantic chunking with table protection.
    embed_fn: list[str] -> list[vector] — pass a Voyage embedding call here,
    NOT the same Chunk-storage embedding step; this is boundary-detection-only
    and never touches the vectors that get stored in pgvector.
    """
    protected_text, tables = extract_tables(doc.text)
    sentences = split_sentences(protected_text)

    if not sentences:
        return []

    breakpoints = find_breakpoints(sentences, embed_fn, percentile=percentile)
    segments = _group_by_breakpoints(sentences, breakpoints)
    segments = _merge_small_segments(segments, min_chars=min_chars)

    split_segments: list[_Segment] = []
    for seg in segments:
        split_segments.extend(_split_large_segment(seg, tables, max_chars))
    segments = split_segments

    segments = _merge_small_segments(segments, min_chars=min_chars)

    chunks = []
    cursor = 0
    for i, seg in enumerate(segments):
        raw_text = _reinsert_tables(seg.text, tables)
        start_char = doc.text.find(raw_text[:50], cursor) if raw_text else cursor
        start_char = max(start_char, cursor)
        end_char = start_char + len(raw_text)
        chunks.append(
            Chunk(
                doc_id=doc.doc_id,
                chunk_index=i,
                text=raw_text,
                start_char=start_char,
                end_char=end_char,
                source_url=doc.source_url,
                title=doc.title,
            )
        )
        cursor = end_char

    return chunks


if __name__ == "__main__":
    # manual inspection entry point — point this at a known hard-case doc, e.g.:
    #   python -m backend.app.ingestion.semantic_chunking documents/opintotukiaika_korkeakoulussa.md
    import sys
    from pathlib import Path

    from backend.app.embeddings.embedder import embed_texts
    from .loaders import load_document

    def _embed_fn(texts: list[str]) -> list[list[float]]:
        # boundary-detection embeddings are neither stored ("document") nor
        # a search query ("query") — using "document" as the closer semantic
        # fit for representing content, not searching against it. Worth
        # flagging as an assumption, not a settled answer.
        return embed_texts(texts, input_type="document")

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "documents/opintotukiaika_korkeakoulussa.md"
    )
    doc = load_document(path)
    chunks = chunk_document_semantic(doc, embed_fn=_embed_fn)

    print(f"{doc.doc_id}: {len(chunks)} chunks\n")
    for c in chunks:
        print(f"--- chunk {c.chunk_index} ({c.start_char}:{c.end_char}) ---")
        print(c.text)
        print()