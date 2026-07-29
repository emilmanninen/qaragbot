import os
import psycopg
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


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

class QueryRequest(BaseModel):
    question: str = Field(min_length=1)

class Citation(BaseModel):
    source_url: str
    snippet: str

class QueryResponse(BaseModel):
    answer: str
    citations: dict[str, Citation]

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    return QueryResponse(
        answer="placeholder",
        citations={}
    )