---
name: rate-limiting
description: The two-layer request guard in main.py (per-IP burst limit + global daily cap) and its budget-protection rationale.
metadata:
  type: project
---

Snapshot as of 2026-08-21 (HEAD 24b923a). Re-check if RATE_LIMIT_MAX_REQUESTS,
DAILY_QUERY_LIMIT, or check_daily_limit()'s call site in main.py change.

`main.py` runs two independent in-memory guards on `POST /query`, added for
different reasons:

- **Per-IP sliding window** (`check_rate_limit`, `RATE_LIMIT_MAX_REQUESTS = 15`,
  60s) — throttles burst rate. Predates the daily cap; original limit was 20,
  tightened to 15.
- **Global daily cap** (`check_daily_limit`, `DAILY_QUERY_LIMIT = 40`) — caps
  total spend, not burst rate. Added specifically to protect a fixed-size paid
  LLM budget (see the comment above `DAILY_QUERY_LIMIT` in main.py) — the
  per-IP limiter alone doesn't bound total cost across many IPs or a full day
  of traffic. Called only once a request is past the question-length check and
  about to reach the LLM, so rejected requests don't consume the budget.

**Known gap, not yet fixed**: the daily counter is a plain in-process Python
variable, reset whenever the process restarts. CLAUDE.md's "Live hosting"
section documents that Render's free tier sleeps the backend after inactivity
and spins up a fresh process on the next request — so under low, spaced-out
traffic, "40/day" is actually "40 per process lifetime": several cold starts
in one calendar day would each reset the counter, allowing more than 40 actual
paid LLM calls despite the cap. Neither file states this consequence on its
own; it only follows from reading both together. Not treated as a bug to fix
silently — the actual hard spend backstop is an Anthropic Console spend limit
(external, not app code), which is unaffected by this gap.

Both limiters share the same demo-scale caveats: in-memory, not shared across
instances, no persistence. The daily cap additionally treats "day" as a UTC
calendar date, not a rolling 24h window.

Related: [[known-gaps]], [[overview]].
