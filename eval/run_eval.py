"""
Step 9 — retrieval-only eval harness. No LLM calls.

For each scored question: embed once, then run one similarity search per
chunking strategy (LIMIT 10), and slice that single ordered result for
Recall@3/5/10 rather than re-querying per k.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from backend.app.db.session import engine
from backend.app.retrieval.retriever import embed_query, search_by_vector, vector_literal

STRATEGIES = ["fixed_v1", "semantic_v1", "structure_v1"]
K_VALUES = [1, 3, 5, 10]
EVAL_SET_PATH = Path(__file__).resolve().parent / "eval_set.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def get_db_strategies() -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT chunking_strategy FROM chunks"))
        return {r[0] for r in rows}


def hit(source_urls: list[str], match_type: str | None, retrieved_urls: list[str]) -> bool:
    if not source_urls:
        raise ValueError("hit() called with no ground truth — should be filtered upstream")
    mt = match_type or "single"
    if mt == "single":
        assert len(source_urls) == 1, f"match_type=single but {len(source_urls)} urls: {source_urls}"
        return source_urls[0] in retrieved_urls
    if mt == "any":
        return any(u in retrieved_urls for u in source_urls)
    if mt == "all":
        return all(u in retrieved_urls for u in source_urls)
    raise ValueError(f"unknown match_type: {mt!r}")


def score_question(q: dict, strategies: list[str]) -> dict:
    """Returns {strategy: {3: bool, 5: bool, 10: bool}} for a scored question,
    or {strategy: {"top_urls": [...]}} for an out-of-corpus diagnostic row."""
    query_vec_literal = vector_literal(embed_query(q["question"]))
    is_ooc = (q["source_urls"] == [])

    per_strategy = {}
    for strat in strategies:
        rows = search_by_vector(query_vec_literal, chunking_strategy=strat, k=max(K_VALUES))
        retrieved_urls = [r.source_url for r in rows]  # ordered by distance, len == max(K_VALUES)

        if is_ooc:
            per_strategy[strat] = {"top_urls": retrieved_urls}
        else:
            per_strategy[strat] = {
                k: hit(q["source_urls"], q.get("match_type"), retrieved_urls[:k])
                for k in K_VALUES
            }
    return per_strategy


def aggregate(per_question_results: list[dict], strategies: list[str]) -> dict:
    agg = {strat: {k: 0 for k in K_VALUES} for strat in strategies}
    n = len(per_question_results)
    for res in per_question_results:
        for strat in strategies:
            for k in K_VALUES:
                if res[strat][k]:
                    agg[strat][k] += 1
    return {
        strat: {f"recall@{k}": agg[strat][k] / n if n else None for k in K_VALUES}
        for strat in strategies
    }


def main():
    eval_set = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))
    questions = eval_set["questions"]  # adjust key name to match your actual file
    ground_truth_limited_ids = set(
        eval_set.get("_meta", {}).get("known_ground_truth_limitation", {}).get("ids", [])
    )

    db_strategies = get_db_strategies()
    assert db_strategies == set(STRATEGIES), (
        f"chunking_strategy mismatch: DB has {db_strategies}, harness expects {set(STRATEGIES)}"
    )

    scored, ooc, category_map = [], [], {}
    for q in questions:
        is_ooc = (q["source_urls"] == [])
        assert is_ooc == (q["category"] == "out_of_corpus"), (
            f"{q['id']}: category/source_urls mismatch"
        )
        per_strategy = score_question(q, STRATEGIES)
        if is_ooc:
            ooc.append({"id": q["id"], "question": q["question"], "per_strategy": per_strategy})
        else:
            scored.append({"id": q["id"], "question": q["question"],
                            "category": q["category"], "results": per_strategy})
            category_map.setdefault(q["category"], []).append(per_strategy)

    all_results = [q["results"] for q in scored]
    excl_gtl_results = [q["results"] for q in scored if q["id"] not in ground_truth_limited_ids]
    gtl_detail = [q for q in scored if q["id"] in ground_truth_limited_ids]

    output = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "k_values": K_VALUES,
        "counts": {
            "total": len(questions),
            "scored": len(scored),
            "out_of_corpus": len(ooc),
            "ground_truth_limited": len(gtl_detail),
        },
        "aggregate": aggregate(all_results, STRATEGIES),
        "aggregate_excluding_ground_truth_limited": aggregate(excl_gtl_results, STRATEGIES),
        "by_category": {
            cat: aggregate(results, STRATEGIES) for cat, results in category_map.items()
        },
        "ground_truth_limited_detail": gtl_detail,
        "out_of_corpus_diagnostic": ooc,
        "per_question": scored,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")

    print(f"\nRecall@k by strategy  ({len(scored)} scored, {len(ooc)} out-of-corpus excluded)\n")
    header = "strategy".ljust(14) + "".join(f"recall@{k}".rjust(12) for k in K_VALUES)
    print(header)
    for strat in STRATEGIES:
        row = output["aggregate"][strat]
        print(strat.ljust(14) + "".join(f"{row[f'recall@{k}']:.2f}".rjust(12) for k in K_VALUES))

    if gtl_detail:
        ids = ", ".join(q["id"] for q in gtl_detail)
        print(f"\n⚠ {ids} are doc-level-only checks (shared source_url across "
              f"cohort/year variants) — included above, see aggregate_excluding_ground_truth_limited "
              f"for the numbers without them.")

    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()