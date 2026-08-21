# RAG Document Q&A Bot — Kela Opintotuki (Finnish Student Financial Aid)

A document Q&A chatbot over Kela's Finnish student financial aid (Opintotuki)
documentation, built with Retrieval-Augmented Generation (RAG). Answers cite
the specific source page they came from.

**Live demo:** https://qaragbot.vercel.app/

> ⚠️ Hosted on free tiers. The backend sleeps after inactivity — the first
> request can take ~30–60 seconds while it wakes up. The UI tells the user
> this up front; it isn't a bug.

## Why this project

Built as a portfolio project while job hunting for junior developer roles
in Finland (frontend/backend/fullstack). A few reasons for this specific
shape:

- **Personally relevant corpus** — Sosiaalituki is something I actually needed
  to understand myself.
- **Multilingual retrieval** — the corpus is Finnish, so this also tests
  whether embedding-based retrieval holds up on Finnish (agglutinative
  morphology, formal registry language) rather than just assuming it does.

My main goal was to understand how RAG systems actually work, end to end,
rather than get something working via a framework. That's why results below
are reported as measured, not rounded up to sound better.

## Architecture

```
Documents (16 Kela.fi pages, markdown)
      │
      ▼
Chunking (3 swappable strategies: fixed-size / semantic / structure-based)
      │
      ▼
Embedding (Voyage AI voyage-4, 1024-dim, multilingual)
      │
      ▼
PostgreSQL + pgvector (Neon, production)
      │
      ▼
Query Condensation (multi-turn history → standalone question)
      │
      ▼
Retrieval (cosine similarity, top-k)
      │
      ▼
Generation (chunks → cited answer)
      │
      ▼
FastAPI /query endpoint (Render, production)
      │
      ▼
Next.js + shadcn/ui chat interface (Vercel, production)
```

Each stage is a function with a defined input/output contract, isolated from
its neighbors. That paid off repeatedly during development — swapping the LLM
provider, adding query condensation, and adding chunking-strategy swappability
each required **zero changes** to the retrieval or route logic.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI (sync handlers) | Single-user local tool — no need for an async DB/HTTP rewrite at this scale |
| Vector store | PostgreSQL + pgvector | Local via Docker for dev, Neon in production |
| Embeddings | Voyage AI `voyage-4` (1024-dim) | Chosen specifically for multilingual/Finnish strength |
| LLM (dev) | Anthropic Claude (`claude-haiku-4-5`) | Faster iteration during development |
| LLM (production) | Gemini free tier | Cost control for the live demo — see "Production notes" |
| Chunking | Hand-rolled, 3 swappable strategies | No LangChain/LlamaIndex — writing retrieval + prompt assembly myself was the actual point of the project |
| Frontend | Next.js + shadcn/ui | |
| Hosting | Vercel (frontend) + Render (backend) + Neon (DB) | Free-tier deployment for the live demo |

## Eval results

**Setup:** 38 hand-written questions (29 neutral, 4 adversarial, 5
out-of-corpus), ground truth = `source_url` per question. 5 out-of-corpus
questions are excluded from the aggregate below — they test refusal
behavior, not retrieval, and there's no "correct chunk" to score against. That
leaves 33 scored questions over 16 source documents.

Retrieval-only eval (no LLM calls) run separately for each of the 3 chunking
strategies, same embeddings, same questions.

### Recall@k

| Strategy | Recall@1 | Recall@3 | Recall@5 | Recall@10 |
|---|---|---|---|---|
| `fixed_v1` (baseline, fixed-size chunks) | **0.88** | 1.00 | 1.00 | 1.00 |
| `semantic_v1` (embedding-boundary chunks) | **0.94** | 1.00 | 1.00 | 1.00 |
| `structure_v1` (markdown-header chunks) | **0.94** | 1.00 | 1.00 | 1.00 |

**Recall@3/5/10 aren't a useful comparison here** — at 16 documents and 33
questions, all three strategies converge to 1.00. That result says retrieval
isn't fundamentally broken at k≥3; it doesn't say anything about which
chunking strategy is better. I'm reporting it that way rather than letting it
look like three strategies "tied at 100%," because they didn't — they
saturated a metric that stops being sensitive at this corpus size.

**Recall@1 is the metric that actually differentiates the strategies.** It's
also the metric I traced individually, question by question, rather than
trusting the aggregate gap:

- Of the underlying Recall@1 misses, only **two** turned out to be genuine
  chunking-strategy effects. One was a **mislabeled ground-truth question**
  (fixed after inspection, confirmed by re-running the harness), and one was
  an **ambiguous question phrasing** with no clean answer in the corpus —
  neither is a retrieval defect.
- The two genuine differences are a **mirror image of each other**: one
  question is won by `structure_v1` because header-scoped chunking keeps a
  short, on-topic section tightly isolated from adjacent content; a different
  question is *lost* by `structure_v1` for the same reason — a brief
  cross-reference in another document gets isolated cleanly enough by header
  boundaries to outrank the actual source document. Same structural property,
  opposite outcome depending on the question. **No strategy dominates
  cleanly** — this isn't "structure_v1 is better," it's "structure_v1 makes a
  specific, explainable tradeoff."

**Production-relevance caveat, stated plainly:** the app's default retrieval
depth is `k=5`, and Recall@5 is 1.00 for all three strategies on this eval
set. So the Recall@1 gap above is real and traced, but it may not actually
change what a user receives from `/query` today — the generator already sees
5 chunks regardless of which one ranks first among them. Recall@1 is the
right metric for comparing retrieval *precision* between strategies;
Recall@5 is closer to the right metric for "does this affect what users
actually get."

## Production default: `structure_v1`

`CHUNKING_STRATEGY=structure_v1` is the shipped default. Reasoning:

- Ties `semantic_v1` for the best Recall@1 (0.94 vs. `fixed_v1`'s 0.88).
- **Zero decision-time cost and fully deterministic** — `semantic_v1` embeds
  every sentence in the corpus once just to decide chunk boundaries, roughly
  doubling ingestion embedding cost for no Recall@5 benefit at this corpus
  size. `structure_v1` needs no threshold tuning and produces identical
  output on every re-run.
- Its one documented failure mode (header-based grouping can produce an
  oversized section that then gets fragmented by a size fallback) is
  real and documented, but **hasn't actually surfaced as a Recall@k miss** in
  this eval set — it's a theoretical risk I'm tracking, not an active problem.
- `fixed_v1` stays in the codebase as the baseline (and `semantic_v1` as the
  alternative) behind the same `get_chunker(name)` factory — swapping the
  default back is a one-line `.env` change, not a code change, if a larger
  corpus later makes the tradeoff look different.

## Known limitations (honest, not exhaustive)

This is a portfolio project, and it deliberately is **not** production-ready
for a domain like government benefits, where a wrong answer has real
financial consequences for the person reading it. Specifically:

- **Generation-quality eval is out of scope so far.** Everything above
  measures *retrieval* (did the right document get found), not *generation*
  (did the model's answer faithfully reflect it). Faithfulness / hallucination
  checking (e.g. LLM-as-judge, RAGAS) was scoped as a possible future
  extension, not built. A small set of manual spot-checks exists, but it's
  not a substitute for a real generation eval.
- **Vector similarity can't do date-range/cohort reasoning.** Questions keyed
  to a specific eligibility cohort or date range are a known weak point for
  pure embedding search — not fixable by chunking alone.
- **Parameterized table lookups can fail even when the right table is
  retrieved**, if the question doesn't supply the parameter the table is
  keyed on (e.g. number of support months).
- **Refusal behavior on ambiguous follow-ups isn't fully consistent** —
  observed to differ between English and Finnish on the same underlying
  question, in one tested case.
- Two chunking-strategy-specific edge cases (a rule getting separated from
  its own qualifying condition under `semantic_v1`; example-block
  fragmentation under `structure_v1`) are documented and were specifically
  targeted by adversarial eval questions, but aren't fully confirmed or ruled
  out by Recall@k alone — that metric checks "was the document found," not
  "was the complete rule intact in one chunk."

None of this is hidden in the codebase — every limitation above has a
reproduction path and a targeted test behind it (adversarial eval questions,
condenser test cases, or manual spot-checks). The point isn't "it works,"
it's "here's exactly where it doesn't yet, and how I know."

## Production notes

- **Gemini free tier only in production**, deliberately. No Anthropic
  credential exists in Render's environment, and a code-level guard
  (`ALLOW_PAID_LLM`) is also unset — two independent blocks against
  accidentally hitting a paid API from the live demo.
- **Rate limiting:** in-memory per-IP limiter (20 req/min, sliding window).
  Demo-scale by design — resets on restart, doesn't hold across multiple
  instances. Accepted limitation at this traffic level, not a bug.
- **No CORS configuration needed in production**, and that's a deliberate
  consequence of the routing design, not an oversight: the frontend never
  calls the backend directly from the browser. A Next.js rewrite
  (`/api/:path*` → the backend URL, set via a `BACKEND_URL` env var) proxies
  requests server-side, so the browser only ever talks to the frontend's own
  origin. CORS only applies to browser-to-server cross-origin calls, and
  there isn't one.

## Setup & running

### Prerequisites

- Python 3.x (venv)
- Node.js
- Docker (for local pgvector/Postgres)
- Anthropic API key (dev) and/or Gemini API key
- Voyage AI API key

### 1. Clone and configure

```bash
git clone <repo-url>
cd rag-docqa
cp .env.example .env
# fill in: DATABASE_URL, VOYAGE_API_KEY, LLM_PROVIDER (anthropic|gemini),
# provider API key, CHUNKING_STRATEGY=structure_v1
```

### 2. Start Postgres + pgvector

```bash
docker compose up -d
```

### 3. Backend

```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
python -m backend.scripts.ingest        # embeds & loads the corpus
uvicorn backend.app.main:app --reload    # run from repo root
```

### 4. Frontend

```bash
cd frontend
npm install
# optional — defaults to localhost:8000 if unset:
echo "BACKEND_URL=http://localhost:8000" > .env.local
npm run dev
```

### 5. (Optional) Run the eval harness

```bash
python -m eval.run_eval
```

**Still open — need your input to lock these in:**
1. Repo URL, and whether it's public yet.
2. Exact `.env` variable names, if any differ from what's used above —
   this session confirmed `DATABASE_URL` and `BACKEND_URL` specifically, but
   I haven't verified the Gemini API key's exact env var name.
3. Any DB migration step (e.g. Alembic) before `ingest.py`, or does ingest
   create tables itself?

## Project status

MVP, multi-turn conversation, chunking-strategy swappability, eval set, and
eval harness (Steps 0–9) are complete and verified. Frontend and backend are
both live in production (Vercel / Render / Neon). This README is Step 10 —
the last item before the project is considered done for portfolio purposes.
