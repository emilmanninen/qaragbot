---
name: overview
description: What this project is, stack, and where things live — entry point for the KB.
metadata:
  type: project
---

RAG document Q&A chatbot over 16 Finnish Kela.fi opintotuki pages, portfolio project
for Finnish junior-dev job hunting. Full architecture/design rationale lives in
`CLAUDE.md` at the repo root (already extensive — read it before this KB) and in the
Obsidian vault doc `claudeprojectfile.md` referenced there. This KB captures only what
CLAUDE.md doesn't: verified gaps and doc/code drift found by reading the actual code
(see [[known-gaps]]).

Repo layout:
- `backend/app/` — FastAPI app: `main.py` (routes/rate-limit), `generation/` (LLM
  abstraction + condensation), `retrieval/`, `embeddings/`, `ingestion/` (loaders + 3
  chunking strategies), `db/` (SQLAlchemy models/session).
- `backend/scripts/` — CLI entry points (`ingest.py`, `retrieve.py`, `generate.py`,
  eval/debug scripts).
- `frontend/src/` — Next.js app router (`app/`), chat UI (`components/`), shared types
  (`lib/types.ts`).
- `documents/` — the 16-doc Finnish corpus (markdown + YAML front matter).
- `eval/` — retrieval-only eval harness + results.

Related: [[known-gaps]].
