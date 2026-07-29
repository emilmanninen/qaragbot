"""
Engine + session factory for Postgres.

Reads DATABASE_URL from the environment rather than hardcoding connection
details. No config.py exists yet (that's a Step 5-ish concern per the repo
structure), so for now just read the env var directly here — same "don't
build the config layer before you need it" reasoning as the documents/ path
discussion earlier.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# loads variables from a .env file at the repo root into os.environ, if one
# exists. Safe to call even if .env is missing (e.g. in prod, where real env
# vars are set another way) — load_dotenv() just no-ops in that case.
load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/ragdocqa"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_session() -> Session:
    return SessionLocal()