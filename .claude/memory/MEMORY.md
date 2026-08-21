# rag-docqa knowledge base
Project-scoped technical/operational knowledge, verified against the actual code —
supplements CLAUDE.md's already-extensive design rationale rather than repeating it.

- [Overview & where things are](overview.md) — what this project is, stack, repo layout; entry point.
- [Known gaps & doc drift](known-gaps.md) — history of doc/code drift; two items fixed, one open (CLAUDE.md's error contract missing daily_limit_reached).
- [Rate limiting](rate-limiting.md) — the per-IP + daily-cap request guards in main.py, and the process-restart gap in the daily cap's guarantee.
- [CI & branch protection](ci.md) — what the GitHub Actions workflow actually runs/enforces, verified branch-protection state, and the ruff rule selection.
