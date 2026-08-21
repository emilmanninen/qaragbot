# rag-docqa knowledge base
Project-scoped technical/operational knowledge, verified against the actual code —
supplements CLAUDE.md's already-extensive design rationale rather than repeating it.

- [Overview & where things are](overview.md) — what this project is, stack, repo layout; entry point.
- [Known gaps & doc drift](known-gaps.md) — history of doc/code drift found and fixed (condense_query's timeout guard, missing .env.example); no open gaps currently.
- [CI & branch protection](ci.md) — what the GitHub Actions workflow actually runs/enforces, verified branch-protection state, and the ruff rule selection.
