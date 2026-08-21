---
name: known-gaps
description: Verified gaps and doc/code drift not documented in CLAUDE.md — a stale README setup step. (condense_query's missing timeout guard, formerly listed here, was fixed — see below.)
metadata:
  type: project
---

Snapshot as of 2026-08-21 (HEAD 96054d4, plus an uncommitted local fix on top —
see below). Re-check if `condenser.py`, `generator.py`, or `README.md`'s Setup
section change.

- **Fixed: `condense_query()` used to bypass the app-level LLM timeout.**
  `condenser.py:59` called `llm.generate()` directly instead of
  `llm.generate_with_timeout()`, so a hung condensation call (any multi-turn
  request, since `condense_query` only runs when `history` is non-empty) had
  no app-level hard timeout — the exact failure mode
  `generate_with_timeout()` was built to guard against (see `generator.py`'s
  module docstring) was unprotected on this path. Changed to call
  `generate_with_timeout()`, matching `generate_answer()`'s existing path —
  same exception classes propagate, so `main.py`'s error handling needed no
  changes. Regression-tested in `backend/scripts/test_condenser.py`
  (`test_timeout_wrapper_actually_fires`,
  `test_condense_query_uses_timeout_guard` — the latter verified to fail
  against the pre-fix code, confirming it actually catches the bug).

- **README's Setup section references a `.env.example` that doesn't exist** in the
  repo (`cp .env.example .env` — no such file present). The three "still open"
  questions listed at the bottom of README's Setup section are partially resolved by
  the code: `GEMINI_API_KEY` is the confirmed env var name (read implicitly by
  `google-genai`'s `Client()`, present in `.env`), and there's no DB migration step —
  `backend/scripts/ingest.py:44` calls `Base.metadata.create_all(engine)` itself
  before inserting rows (no Alembic anywhere in the repo).

Related: [[overview]].
