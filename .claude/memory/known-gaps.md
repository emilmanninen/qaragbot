---
name: known-gaps
description: Doc/code drift found and fixed in this project — condense_query's timeout guard and a missing .env.example. No open gaps as of this snapshot.
metadata:
  type: project
---

Snapshot as of 2026-08-21. Both items below are fixed; kept as a record of what
was found and how, plus a caution about trusting this file's own past state
without re-checking it against current code.

- **Fixed: `condense_query()` used to bypass the app-level LLM timeout.**
  `condenser.py` called `llm.generate()` directly instead of
  `llm.generate_with_timeout()`, so a hung condensation call (any multi-turn
  request, since `condense_query` only runs when `history` is non-empty) had
  no app-level hard timeout — the exact failure mode
  `generate_with_timeout()` was built to guard against (see `generator.py`'s
  module docstring) was unprotected on this one path. Changed to call
  `generate_with_timeout()`, matching `generate_answer()`'s existing path —
  same exception classes propagate, so `main.py`'s error handling needed no
  changes. Regression-tested in `backend/scripts/test_condenser.py`
  (`test_timeout_wrapper_actually_fires`,
  `test_condense_query_uses_timeout_guard` — the latter verified to fail
  against the pre-fix code, confirming it actually catches the bug).

- **Fixed: README's Setup section referenced a `.env.example` that didn't
  exist** in the repo (`cp .env.example .env` — no such file present, so
  following Setup as written failed on its first command). Created
  `.env.example` at the repo root covering every env var the code actually
  reads (checked via `os.environ`/`os.getenv` across `backend/`, plus
  `docker-compose.yml`'s `POSTGRES_*` vars and `frontend/next.config.ts`'s
  `BACKEND_URL`) — not just the abbreviated list README's Setup comment
  names, so the template is complete even where the README stays terse.

- **Self-correction, not a code issue:** this file previously also described
  README as having "three still open questions" at the bottom of Setup —
  that section was already removed by commit `f25898d` ("remove stale still
  open todo section from README") before this file's own claimed snapshot
  commit, so the note was stale from the moment it was written, not from
  later drift. Caught by re-reading the actual README rather than trusting
  this file's prior text. No action needed beyond this correction; flagged
  as a reminder to verify memory notes against current source, per
  CLAUDE.md's working-style section.

Related: [[overview]].
