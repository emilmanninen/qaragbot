"""
Step 3: standalone retrieval sanity-check script.
Thin CLI wrapper around backend.app.retrieval.retriever.retrieve().

Run from the repo root:
    python -m backend.scripts.retrieve "your question here"
    python -m backend.scripts.retrieve "your question here" --k 10
"""

import argparse
from backend.app.retrieval.retriever import retrieve

DEFAULT_QUERY = "Kuinka paljon opintorahaa voi saada korkeakouluopiskelijana?"
DEFAULT_TOP_K = 5


def main():
    parser = argparse.ArgumentParser(description="Retrieve top-k chunks for a query.")
    parser.add_argument(
        "query",
        nargs="?",
        default=DEFAULT_QUERY,
        help="Question to embed and search. Defaults to the original sanity-check question if omitted.",
    )
    parser.add_argument(
        "--k", type=int, default=DEFAULT_TOP_K, help="Number of chunks to retrieve (default 5)."
    )
    args = parser.parse_args()

    rows = retrieve(args.query, args.k)
    print(f"Query: {args.query}\n")
    for i, row in enumerate(rows, start=1):
        chunk_text, title, source_url, distance = row
        snippet = chunk_text.strip().replace("\n", " ")
        if len(snippet) > 300:
            snippet = snippet[:300] + "..."
        print(f"[{i}] distance={distance:.4f}  source={title} ({source_url})")
        print(f"    {snippet}\n")


if __name__ == "__main__":
    main()