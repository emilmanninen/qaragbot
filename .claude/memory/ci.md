---
name: ci
description: What the GitHub Actions CI actually runs and enforces — job contents, branch protection state, and the ruff rule selection.
metadata:
  type: project
---

Snapshot as of 2026-08-21 (HEAD ddfa8ac). Re-check if `.github/workflows/ci.yml`,
`pyproject.toml`, or `main`'s branch protection settings change.

- **`main` is actually branch-protected**, not just described as such in `ci.yml`'s
  comments — verified via `gh api repos/:owner/:repo/branches/main/protection`, not
  inferable from the workflow file alone. Required status checks: `frontend` and
  `backend` (matching the two CI job names), `strict: true` (branch must be up to
  date with `main` before merge), `enforce_admins: true` (applies even to the repo
  owner — no bypass), no force-pushes or deletions allowed. In practice this means
  every change, including trivial ones, goes through a PR that CI must pass.
- **Two CI jobs**, on push/PR against `main` only — no deploy step (Vercel/Render
  auto-deploy from their own GitHub integration independently; this workflow's job
  is purely to gate what can reach `main` in the first place):
  - `frontend`: `npm ci`, `npm run lint`, then `npm run build` — the build step
    also runs TypeScript's type-checker, so one step catches build failures, type
    errors, and most import mistakes. No `BACKEND_URL` needed; `next.config.ts`'s
    rewrite only matters at request time, not build time.
  - `backend`: `pip install -r backend/requirements.txt`, `ruff check` via `uvx`
    (no venv pollution, no separate `requirements-dev.txt`), then
    `python -m backend.scripts.diff_test_chunker` as the only test actually run.
- **Deliberately not run in CI**: `backend/scripts/test_condenser.py` — it calls the
  live LLM per test case, and Gemini's free tier is a shared 20 requests/day cap
  with the live demo; running it on every push would compete with or exhaust that
  quota. Stays a manual check.
- **Ruff config** lives in root `pyproject.toml` (not a `requirements.txt`
  replacement — Render's deploy install command still depends on
  `requirements.txt` as-is). Rule selection is `["E4", "E7", "E9", "F", "I"]` —
  deliberately not the full pycodestyle `"E"` family, which would include E501
  (line length): this codebase's docstrings and adversarial test-case strings are
  intentionally long-form prose. `ruff format` is not enabled either — that would
  rewrite every file's whitespace in one commit, treated as out of scope for
  "add CI".
- **Bug found and fixed while adding CI**: `diff_test_chunker.py` used to call
  `get_chunker()` with no argument (the `.env`-driven default), which silently
  became `structure_v1` once Step 10 changed that default — so the script was
  comparing `structure_v1` (220 chunks) against the raw pre-refactor `fixed_v1`
  `chunk_document()` output (313 chunks) and always mismatching, regardless of
  whether the actual `fixed_v1` refactor was correct. Fixed to call
  `get_chunker("fixed_v1")` explicitly — the script's job is narrowly "is the
  `fixed_v1` wrapper behavior-preserving," independent of whichever strategy
  `.env` currently points at. Same class of silent-drift bug as the
  `CHUNKING_STRATEGY` retrieval-layer bug in [[overview]]'s linked history —
  worth knowing before assuming a script that reads `get_chunker()`'s default is
  testing the strategy you think it is.

Related: [[overview]], [[known-gaps]].
