"""
Embedding: turn chunk text into vectors via the Voyage AI API.

Called directly (no LangChain/LlamaIndex embedding wrapper) so the batching
and input_type behavior stays visible and swappable — matches the project's
"writing the retrieval + prompt-assembly loop myself" stance.

input_type matters: Voyage prepends a different instruction prefix depending
on whether text is a "document" being stored or a "query" being searched
with. Getting this wrong (or leaving it as None) measurably hurts retrieval
quality. This module is called with input_type="document" during ingestion
(this step); the retriever (Step 3) will call it again with
input_type="query" for the user's question.
"""

from typing import Literal

import voyageai
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "voyage-4"
OUTPUT_DIMENSION = 1024

# Conservative batch size. Voyage's actual limit for voyage-4 is 1,000 texts
# and 320K total tokens per request — this project has nowhere near enough
# volume for that ceiling to matter, so a small fixed batch size keeps the
# code simple without needing real per-request token accounting.
BATCH_SIZE = 100

# Safety ceiling, not a real limit this project should ever approach. The
# 16-doc Kela corpus is roughly 40-50K tokens total; re-embedding it dozens
# of times while comparing chunking strategies (Steps 7-10) still stays well
# under six figures. 1M tokens is generous headroom for legitimate growth
# while still catching the realistic accident this guards against: a bug
# that points the script at the wrong folder, or a loop that re-embeds the
# same batch repeatedly. This check costs nothing extra to run since
# count_tokens is a local tokenizer call, not a billed embedding request.
MAX_TOKENS_PER_RUN = 1_000_000

_client: voyageai.Client | None = None


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        # picks up VOYAGE_API_KEY from the environment automatically
        _client = voyageai.Client()
    return _client


def _check_token_budget(texts: list[str]) -> None:
    """Abort before sending anything if the total token count looks like an accident."""
    client = _get_client()
    total_tokens = client.count_tokens(texts, model=MODEL_NAME)
    if total_tokens > MAX_TOKENS_PER_RUN:
        raise RuntimeError(
            f"Refusing to embed {total_tokens:,} tokens in one run "
            f"(safety ceiling is {MAX_TOKENS_PER_RUN:,}). "
            f"This is far more than the corpus should ever produce — "
            f"check you're not pointed at the wrong folder or re-embedding "
            f"in a loop before raising this ceiling."
        )


def embed_texts(
    texts: list[str], input_type: Literal["document", "query"]
) -> list[list[float]]:
    """Embed a list of texts, batching requests to keep individual calls small."""
    _check_token_budget(texts)

    client = _get_client()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        result = client.embed(
            texts=batch,
            model=MODEL_NAME,
            input_type=input_type,
            output_dimension=OUTPUT_DIMENSION,
        )
        all_embeddings.extend(result.embeddings)

    return all_embeddings