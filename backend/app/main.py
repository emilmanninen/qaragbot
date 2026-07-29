import os
import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

# Loads variables from the .env file two directories up (rag-docqa/.env)
# so the same file that configures Docker Compose also configures the app.
load_dotenv(dotenv_path="../.env")

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