import os
import re
import time
from collections import defaultdict
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.embeddings.embedder import EmbeddingProviderError
from backend.app.generation.condenser import condense_query
from backend.app.generation.generator import (
    LLMProviderError,
    QuotaExhaustedError,
    generate_answer,
)

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

app = FastAPI()

DB_DSN = os.environ.get(
    "DATABASE_URL", "postgresql://raguser:1234@localhost:5432/ragdocqa"
)

@app.get("/health")
def health_check():
    try:
        with psycopg.connect(DB_DSN, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
    except psycopg.OperationalError as e:
        raise HTTPException(status_code=503, detail=f"Database unreachable: {e}")
    return {"status": "ok", "db": "connected"}

class Turn(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    history: list[Turn] = Field(default_factory=list)

class Citation(BaseModel):
    source_url: str
    snippet: str

class QueryResponse(BaseModel):
    answer: str
    citations: dict[str, Citation]

# Hard cap on question length, checked before any retrieval/LLM work runs --
# guards against someone pasting in a huge blob and burning embedding/LLM
# tokens on it, not a meaningful UX limit (no legitimate question is anywhere
# near this long).
MAX_QUESTION_LENGTH = 500

# Minimal in-memory per-IP rate limiter, demo-scale only: a plain dict that
# lives for the process lifetime, resets on restart, and isn't shared across
# instances -- fine for a single-service Render deploy, not a real limiter.
# No external dependency (e.g. slowapi) since the requirement is simple
# enough to hand-roll and this project already avoids adding frameworks for
# things it can do itself (see CLAUDE.md's LangChain stance).
RATE_LIMIT_MAX_REQUESTS = 15
RATE_LIMIT_WINDOW_SECONDS = 60

_request_log: dict[str, list[float]] = defaultdict(list)

def check_rate_limit(client_ip: str) -> None:
    """Sliding-window limiter: drop timestamps older than the window, then
    check how many requests from this IP remain inside it."""
    now = time.monotonic()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = _request_log[client_ip]
    while timestamps and timestamps[0] < window_start:
        timestamps.pop(0)

    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "message": f"Rate limit exceeded ({RATE_LIMIT_MAX_REQUESTS} requests per "
                           f"{RATE_LIMIT_WINDOW_SECONDS}s). Try again shortly.",
            },
        )
    timestamps.append(now)

# Global daily query cap, separate from the per-IP limiter above -- that one
# throttles burst rate, this one caps total spend. Sized to stretch a fixed
# $5 Anthropic budget (see CLAUDE.md's Stack section) rather than to stop
# abuse. Same demo-scale caveats: in-memory, resets on process restart, not
# shared across instances, and "day" just means whatever UTC calendar date it
# is when a request lands -- not a rolling 24h window.
DAILY_QUERY_LIMIT = 40

_daily_query_count = 0
_daily_query_date: str | None = None

def check_daily_limit() -> None:
    """Reset the counter on a UTC date change, then enforce the cap. Called
    only once a request is actually about to reach the LLM -- rate-limited or
    question-too-long requests never cost anything, so they shouldn't eat
    into the budget."""
    global _daily_query_count, _daily_query_date
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if _daily_query_date != today:
        _daily_query_date = today
        _daily_query_count = 0

    if _daily_query_count >= DAILY_QUERY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_limit_reached",
                "message": f"Daily query limit ({DAILY_QUERY_LIMIT}) reached. Try again tomorrow.",
            },
        )
    _daily_query_count += 1

def parse_citations(answer: str, sources: list[dict]) -> dict[str, Citation]:
    cited_numbers = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}

    citations = {}
    for num in cited_numbers:
        idx = num - 1  # citation [1] corresponds to sources[0]
        if 0 <= idx < len(sources):
            source = sources[idx]
            citations[str(num)] = Citation(
                source_url=source["source_url"],
                snippet=source["title"],  # see note below on what to use here
            )
        else:
            # model cited a number that doesn't correspond to any retrieved chunk
            # — a real signal worth knowing about, not silently swallowing
            print(f"Warning: model cited [{num}] but only {len(sources)} sources were retrieved")

    return citations

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, req: Request) -> QueryResponse:
    client_ip = req.client.host if req.client else "unknown"
    check_rate_limit(client_ip)

    if len(request.question) > MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "question_too_long",
                "message": f"Question exceeds the {MAX_QUESTION_LENGTH}-character limit.",
            },
        )

    check_daily_limit()

    try:
        history_dicts = [turn.model_dump() for turn in request.history]
        standalone_question = condense_query(history_dicts, request.question)
        answer, sources = generate_answer(standalone_question)
    except QuotaExhaustedError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "quota_exhausted",
                "provider": e.provider,
                "message": f"{e.provider}'s quota has been used up. Try again later, or switch LLM_PROVIDER in .env.",
            },
        )
    except LLMProviderError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "llm_provider_error",
                "provider": e.provider,
                "message": str(e),
            },
        )
    except EmbeddingProviderError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "embedding_provider_error",
                "provider": "voyage",
                "message": str(e),
            },
        )

    citations = parse_citations(answer, sources)
    return QueryResponse(answer=answer, citations=citations)