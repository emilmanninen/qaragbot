# CLAUDE.md

This file gives Claude Code context for working in this repo. For full background,
architecture, and scope-decision rationale, see `claudeprojectfile.md` in the Obsidian
vault (`Funprojects/QaRagBotKela/`) — read it before making structural suggestions.

## What this is

A document Q&A chatbot using RAG, where answers cite sources back to specific
Kela.fi documents. Portfolio project for junior dev job applications in Finland.
Primary goal is defensibility in interviews, not just working code — every design
choice should have an articulable reason, including tradeoffs not picked.

## Stack

- Backend: FastAPI (Python), sync `def` handlers (deliberate — see below)
- DB/vector store: PostgreSQL + pgvector
- Frontend: Next.js + shadcn/ui
- LLM/embeddings: called directly via API, no LangChain/LlamaIndex
- Environment: Windows + WSL (Ubuntu)

## Hard constraints — don't relitigate without a stated reason

- No LangChain/LlamaIndex/RAGAS as defaults. Hand-rolled implementations only.
  Mention frameworks as "aware of, chose not to use" when relevant.
- No multi-user / auth. Single-user local tool.
- `chunking_strategy`, `embedding_model`, and LLM provider (gemini/anthropic) are
  server-side `.env` config, not request params or UI toggles. `get_llm(name)`
  already supports an override if a toggle is added later — don't add one
  speculatively.
- Sync handlers in FastAPI are deliberate (threadpool is sufficient at this scale),
  not a gap to "fix" to async.

## Current backend contract (Steps 0–5 complete)

`POST /query`

Request: `{ question: string }` — no `history` field yet (see Roadmap).

Response (success): `{ answer: string, citations: Record<string, Citation> }`
where `Citation = { source_url: string, snippet: string }`, keyed by citation
number as a string, containing **only** citation numbers actually referenced in
the answer text (not all retrieved chunks).

Response (error):
- `429` from LLM provider → `503 { error: "quota_exhausted", provider: "gemini", message: string }`
- other provider errors → `502 { error: "llm_provider_error", message: string }`

Answer text contains inline `[1]`, `[2]` style citation markers matched against
the `citations` dict keys — these are not markdown links, they need manual
parsing on the frontend, not a markdown-link renderer.

## Frontend (Step 6, in progress)

Building with Claude Code now. Conventions to follow:

- Component split: `chat-input`, `message-list`, `message-bubble`,
  `citation-badge` (shadcn Badge + Popover — **not** HoverCard, no hover on touch),
  `loading-indicator`, `error-banner` (error and loading are separate components,
  not branches of one component).
- State is a `messages: Message[]` list from the start (append, never replace),
  even though every turn is currently independent — this anticipates multi-turn
  history (see Roadmap) without a later rewrite.
- Error banner should branch on `error` field (`quota_exhausted` vs
  `llm_provider_error`), not just display `message` generically.

## Roadmap (not yet built — don't implement early)

- **Multi-turn conversation**: after the frontend works end-to-end on single-turn.
  Adds a `condense_query(history, question) -> string` step (its own LLM call,
  own module in `backend/app/generation/condenser.py`) run before retrieval.
  Citations stay per-turn — do not accumulate a cross-turn chunk pool.
- **Refactor for swappability** (`get_embedder(name)`, `get_llm(name)` behind
  clean interfaces) — Step 7, post-MVP.
- **Eval harness** (Recall@k, retrieval-only scope) — Steps 8–10, post-MVP.
  Ground truth granularity is source_url, not page (Kela docs have no pages).

## Working style

- Explain fundamentals and tradeoffs behind suggestions, don't just hand over
  finished code — I want to defend decisions in interviews.
- Walk through debugging reasoning step by step, don't jump to the answer.
- Be direct about what's wrong or suboptimal.
- I'm self-taught (~1 year in), no formal CS background, job hunting for junior
  frontend/backend/fullstack roles in Finland.
