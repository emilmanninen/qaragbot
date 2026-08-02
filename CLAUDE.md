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
- LLM provider: Anthropic (`claude-haiku-4-5-20251001`), switched from Gemini
  after exhausting its free-tier quota. `GeminiLLM` still supported behind
  `get_llm(name)`, just not the active provider.
- Embedding model: Voyage AI `voyage-4`, 1024 dims — not swappable, deliberate
  scope decision (see Hard constraints).
- Environment: Windows + WSL (Ubuntu)

## Hard constraints — don't relitigate without a stated reason

- No LangChain/LlamaIndex/RAGAS as defaults. Hand-rolled implementations only.
  Mention frameworks as "aware of, chose not to use" when relevant.
- No multi-user / auth. Single-user local tool.
- `chunking_strategy`, `embedding_model`, and LLM provider (gemini/anthropic) are
  server-side `.env` config, not request params or UI toggles. `get_llm(name)`
  and `get_chunker(name)` already support overrides for exactly this reason —
  don't add a UI toggle speculatively.
- Embedding-model swappability (`get_embedder(name)`) was considered and
  deliberately cut, not forgotten — Voyage-4 was chosen for a specific, verified
  reason (multilingual/Finnish strength), and a second swappable axis would add
  re-embedding cost and schema complexity (incompatible vector dimensions across
  models) without a concrete question to answer. Chunking-strategy swappability
  (`get_chunker(name)`) is the one axis actually built — see below.
- Sync handlers in FastAPI are deliberate (threadpool is sufficient at this scale),
  not a gap to "fix" to async.
- `generate_answer` is deliberately history-blind (Option A) — only the condensed
  question + retrieved chunks go into generation, no raw conversation history.
  This is revisitable (an additive `raw_history=None` param would extend it) but
  not a bug to silently "fix."

## Current backend contract (Steps 0–6 + multi-turn complete)

`POST /query`

Request: `{ question: string, history?: Message[] }` — `history` is optional;
omitted or empty means the question is treated as standalone (no condensation
LLM call made). When present, `condense_query(history, question)` runs before
retrieval to produce a standalone query.

Response (success): `{ answer: string, citations: Record<string, Citation> }`
where `Citation = { source_url: string, snippet: string }`, keyed by citation
number as a string, containing **only** citation numbers actually referenced in
the answer text (not all retrieved chunks). Citations are per-turn — the
generator does not see or cite chunks from earlier turns.

Response (error):
- `429` from LLM provider → `503 { error: "quota_exhausted", provider: string, message: string }`
- other provider errors → `502 { error: "llm_provider_error", message: string }`
- Normalized exception classes (`QuotaExhaustedError`, `LLMProviderError`) isolate
  provider SDK types from `main.py` — don't catch raw Gemini/Anthropic SDK
  exceptions directly in route handlers.

Answer text contains inline `[1]`, `[2]` style citation markers matched against
the `citations` dict keys — these are not markdown links, they need manual
parsing on the frontend, not a markdown-link renderer.

## Retrieval layer (`backend/app/retrieval/retriever.py`)

- `embed_query(query) -> vector` and `search_by_vector(query_vec_literal,
  chunking_strategy, k=5) -> rows` are separate functions — split during Step 9
  so the eval harness can embed a question once and query multiple chunking
  strategies against the same vector, instead of re-embedding per strategy.
- `retrieve(query, k=5, chunking_strategy=CHUNKING_STRATEGY)` is a thin wrapper
  calling both in sequence. Existing call sites (`generator.py`,
  `scripts/retrieve.py`) are unaffected — `chunking_strategy` defaults to the
  same module constant as before the split, so `retrieve(query)` behaves
  identically to pre-Step-9 code.
- `CHUNKING_STRATEGY` module constant now reads `os.environ.get("CHUNKING_STRATEGY",
  "fixed_v1")`, mirroring `get_chunker()`'s pattern in `chunker.py`. **Bug found
  and fixed**: it used to be a hardcoded `"fixed_v1"` literal, completely
  ignoring `.env` — so setting `CHUNKING_STRATEGY=structure_v1` in `.env`
  silently had no effect on retrieval (ingestion via `get_chunker()` respected
  it correctly; only the retrieval path didn't). Active strategy is now
  `structure_v1`, matching `.env` and confirmed against a live `/query` call
  and a direct import check.

## Frontend (Step 6 complete, fully verified end-to-end)

Built with Claude Code, working end-to-end against the real backend in both
English and Finnish:

- `chat-input`, `message-list`, `message-bubble`, `citation-badge`,
  `error-banner`, `loading-indicator` — all built and verified.
  `message-list` also always renders a static Finnish welcome bubble ("Hei!
  Voit kysyä minulta Kelan korkeakouluajan tuista, kuten opintorahasta ja
  opintolainasta.") pinned above the conversation — a local constant, not
  part of `messages` state, so it's never sent to the backend as fake history
  and stays visible through the whole conversation (deliberate, aesthetic —
  not just an empty-state placeholder).
- The chat itself is wrapped in a bordered, rounded `bg-card` panel
  (`page.tsx`'s `<main>`) with a shadow, floating over the page's plain
  `bg-background` — reads as an "interface" sitting on the page rather than
  filling the whole viewport edge-to-edge.
- `nav-bar.tsx` (client component, `usePathname` for active-route
  highlighting) renders in `layout.tsx` above `{children}`, so it's shared
  across routes without a per-page remount. Two routes: `/` (chat) and
  `/about` (`app/about/page.tsx`) — a static page mirroring the chat panel's
  bordered/rounded/shadow styling for visual consistency. Content: a short
  project description, a link to
  `https://github.com/emilmanninen/qaragbot`, and a bordered notice box
  flagging that the live demo may fail because it runs on Gemini's free
  tier (20 requests/day cap) rather than a paid one — relevant once the
  "Live hosting" roadmap item (Gemini-only provider restriction, see above)
  ships.
- **Chat state survives navigating to `/about` and back.** The App Router
  unmounts a route segment's component on navigation, which would otherwise
  wipe `messages`/`status` (they used to live in `app/page.tsx`). Fixed by
  moving that state and all the chat UI into `components/chat-view.tsx`,
  rendered from `components/app-shell.tsx` — a client component sitting in
  `layout.tsx` *outside* the routed `{children}` tree, so it's never
  unmounted by route changes. `app-shell.tsx` reads `usePathname()` and
  toggles `ChatView` vs. `{children}` with a CSS `hidden` class rather than
  conditional rendering — both stay mounted, only visibility changes.
  `app/page.tsx` (the `/` route) is now intentionally an empty stub — real
  chat content is rendered by the shell, not the route.
  `loading-indicator` renders as a three-dot bounce inside a bubble styled
  like an assistant reply (matches `message-bubble`'s muted/rounded look),
  appended by `message-list` when `page.tsx`'s `status === "loading"` — it
  occupies the spot the next assistant bubble will land in, not a separate
  banner. Verified end-to-end with a real backend call (Playwright): dots
  visible mid-request, gone once the answer bubble replaces them, no console
  errors.
- `citation-badge` is shadcn Badge + Popover (**not** HoverCard, no hover on
  touch), composed via base-ui's `render` prop chained two levels deep
  (`PopoverTrigger` renders as `Badge`, `Badge` renders as a real `<button>`) —
  needed for base-ui's native-button a11y requirement, not decorative.
- `message-bubble` parses `[1]`/`[2]` markers out of answer text via regex and
  swaps matched ones for `citation-badge`; an unmatched number (cited but not in
  the `citations` dict) falls back to literal text rather than erroring.
- `chat-input`: Enter submits (`form.requestSubmit()`), Shift+Enter inserts a
  newline — don't rewire this to a submit-on-blur or button-only pattern without
  reason, it matches standard chat-UI expectations.
- `error-banner` branches on the `error` field (`quota_exhausted` vs
  `llm_provider_error`), not just displaying `message` generically.
- State is `messages: Message[]`, append-only from the start — `page.tsx`'s
  `handleSubmit` sends the accumulated list as `history` on every turn. This
  was built in from day one, before multi-turn condensation existed backend-
  side, specifically to avoid a later rewrite.
- `frontend/next.config.ts` proxies `/api/*` → `http://localhost:8000/*`
  (`rewrites()`). This exists because `main.py` has no `CORSMiddleware` — the
  proxy sidesteps CORS entirely rather than adding it backend-side. Frontend
  code calls `/api/query`, never `http://localhost:8000/query` directly.
- Backend must be started via `backend/run.sh`, not a bare `uvicorn` command —
  it sets `--timeout-keep-alive 75` (uvicorn's 5s default caused intermittent
  ECONNRESET on the proxy↔backend connection after idling between chat turns).
- **Not yet resolved**: markdown-rendering decision. Model outputs `**bold**`/
  bullets without explicit prompting despite the "plain prose" scope decision —
  unresolved whether to render markdown client-side or strip it in generation.

## Multi-turn conversation (done)

- `condense_query(history, question) -> string` in
  `backend/app/generation/condenser.py`. Empty history returns the question
  unchanged with no LLM call. Non-empty history rewrites the question as
  standalone before it reaches `retrieve()`.
- Tested against 5 adversarial cases (vague follow-up, already-standalone,
  multi-hop reference, topic shift, ambiguous antecedent) via
  `backend/scripts/test_condenser.py` before any endpoint/frontend wiring.
- Known soft spot: the condenser's ambiguity-resolution rule (single-resolve to
  most recently mentioned candidate) isn't strictly followed — it sometimes
  merges multiple candidates into one query instead. Checked empirically, not
  currently treated as a bug (the merged query has scored as well or better on
  this corpus). Don't "fix" this without re-testing against the adversarial set.

## Chunking strategy swappability (Step 7, done)

Three strategies behind `get_chunker(name)`, config'd via `CHUNKING_STRATEGY`
in `.env`, all ingested into the same `chunks` table tagged by
`chunking_strategy`:

- `fixed_v1` — naive fixed-size + overlap, 313 rows. Baseline.
- `semantic_v1` — embedding-boundary chunking, 199 rows. Costs ~2x embedding
  calls at ingestion (every sentence embedded once to decide boundaries).
- `structure_v1` — markdown header-based chunking, 220 rows. Zero embedding
  calls to decide boundaries, fully deterministic.

Each was validated against 3 known hard-case docs (near-duplicate income tables,
cohort-cutoff tables, nested exception conditions) — see `claudeprojectfile.md` for
full per-doc findings and bugs found/fixed during this work (a `chunk_text()`
whitespace-snap bug affecting all strategies that fall back to it, and a
missing-separator bug in `structure_v1`'s section-merge step).

`get_chunker(name)` stays in the codebase regardless of which strategy becomes
the eventual `.env` default — same posture as `get_llm()` keeping the unused
`GeminiLLM` implementation around.

## Eval harness (Steps 8–9, done)

- `eval/eval_set.json` — 38 questions, ground truth = `source_url` (not chunk ID
  or page — Kela docs have no pages). 29 neutral, 4 adversarial, 5 out-of-corpus.
  `_meta.known_ground_truth_limitation.ids` flags 3 questions
  (q030/q032/q033) that can only test doc-level retrieval, not intra-document
  chunk discrimination, because two docs hold multiple cohort/year variants
  under one shared `source_url`.
- `eval/run_eval.py` — retrieval-only, no LLM calls. Embeds each question once,
  queries all 3 chunking strategies against the same vector via
  `search_by_vector()`, computes Recall@1/3/5/10 from one ordered top-10 result
  sliced per k rather than re-queried. Out-of-corpus rows excluded from the
  aggregate but still retrieved for diagnostic inspection (checking for
  false-positive lexical-proximity hits).
- **Key finding: Recall@3/5/10 converge to ~1.00 across all 3 strategies at this
  corpus size (16 docs, 33 scored questions) and aren't a useful comparison
  signal.** Recall@1 is where strategies differ: `fixed_v1` 0.88,
  `semantic_v1`/`structure_v1` 0.94. Every miss behind these numbers was traced
  to a specific mechanism (1 mislabeled ground truth fixed via widening
  `match_type` to `"any"`; 1 ambiguous question phrasing, flagged not fixed;
  2 genuine chunking-strategy differences — see `claudeprojectfile.md`'s "Eval
  harness results (Step 9)" section for the full per-question trace).
- **Don't treat Recall@1 differences as necessarily production-relevant**:
  `retrieve()`'s default `k=5`, and Recall@5 is 1.00 across all 3 strategies —
  the generator sees 5 chunks regardless of which one ranks first among them.

## Roadmap (not yet built — don't implement early)

- **Step 10 (partially done)**: `.env` `CHUNKING_STRATEGY` production-default
  decision is made — `structure_v1` (also surfaced and fixed a retrieval-layer
  bug where this setting was silently ignored, see Retrieval layer section
  above). Still open: README table using Recall@1 as the headline metric (not
  Recall@3/5/10, which are uninformative here), with an honest note about the
  k=5 production-relevance caveat above.
- **Frontend polish pass**: markdown-rendering decision (see above).
  `loading-indicator` is done — see Frontend section above.
- **Live hosting (stretch goal)**: Vercel + Supabase-Neon/Render free tiers,
  rate limiting, Gemini-only provider restriction for cost control — do not
  deploy without both the provider restriction and rate limiting in place.
- **Generation-quality eval** (faithfulness, LLM-as-judge): explicitly out of
  current scope, not just unbuilt. Two known generation-layer limitations exist
  from manual spot-checks (`eval/generation_spotchecks.md`) — parameterized
  table lookups can cause an unnecessary refusal, and refusal confidence
  differs by language on the same ambiguous question — neither is covered by
  Recall@k and neither has a systematic eval yet.

## Working style

- Explain fundamentals and tradeoffs behind suggestions, don't just hand over
  finished code — I want to defend decisions in interviews.
- Walk through debugging reasoning step by step, don't jump to the answer.
- Be direct about what's wrong or suboptimal.
- Verify against raw data (actual retrieved chunks, actual output) before
  trusting a plausible-sounding explanation or an aggregate metric — demonstrated
  twice this project: a boundary-check script that was itself buggy, and a
  uniform Recall@k "miss" across all 3 chunking strategies that turned out to be
  a mislabeled eval question, not a retrieval bug.
- I'm self-taught (~1 year in), no formal CS background, job hunting for junior
  frontend/backend/fullstack roles in Finland.