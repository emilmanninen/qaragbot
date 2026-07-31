import os
import psycopg
import re
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from backend.app.generation.generator import generate_answer, QuotaExhaustedError, LLMProviderError
from backend.app.generation.condenser import condense_query

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

app = FastAPI()

DB_DSN = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@localhost:5432/{os.environ['POSTGRES_DB']}"
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
def query(request: QueryRequest) -> QueryResponse:
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

    citations = parse_citations(answer, sources)
    return QueryResponse(answer=answer, citations=citations)