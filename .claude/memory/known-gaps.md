---
name: known-gaps
description: Verified gaps and doc/code drift not documented in CLAUDE.md — condense_query's missing timeout guard, a dead config.py, and a stale README setup step.
metadata:
  type: project
---

Snapshot as of 2026-08-17 (HEAD 45fb4c1). Re-check if `condenser.py`, `generator.py`,
`db/session.py`, or `README.md`'s Setup section change.

- **`condense_query()` bypasses the app-level LLM timeout.** `generator.py`'s module
  docstring says `generate_with_timeout()` "applies uniformly regardless of which
  provider is active" — true for `generate_answer()`, but `condenser.py:56` calls
  `llm.generate()` directly, not `generate_with_timeout()`. A hung condensation call
  (any multi-turn request, since `condense_query` only runs when `history` is
  non-empty) has no app-level hard timeout — the exact failure mode
  `generate_with_timeout()` was built to guard against is unprotected on this path.
  Provider-error normalization (`QuotaExhaustedError`/`LLMProviderError`) still works
  here since that happens inside `generate()` itself — only the timeout wrapper is
  skipped.

- **`backend/app/config.py` is empty and has been since the Step 0 skeleton commit**
  (`0707d54`, never touched since). Not dead by accident: `db/session.py`'s docstring
  explains config was deliberately deferred ("No config.py exists yet... same 'don't
  build the config layer before you need it' reasoning"). Every module reads its own
  env vars directly (`os.environ.get(...)` in `retriever.py`, `chunker.py`,
  `generator.py`, `session.py`) instead of a shared config module. Worth knowing before
  assuming `config.py` holds anything, or before adding a new env var there by habit.

- **README's Setup section references a `.env.example` that doesn't exist** in the
  repo (`cp .env.example .env` — no such file present). The three "still open"
  questions listed at the bottom of README's Setup section are partially resolved by
  the code: `GEMINI_API_KEY` is the confirmed env var name (read implicitly by
  `google-genai`'s `Client()`, present in `.env`), and there's no DB migration step —
  `backend/scripts/ingest.py:44` calls `Base.metadata.create_all(engine)` itself
  before inserting rows (no Alembic anywhere in the repo).

Related: [[overview]].
