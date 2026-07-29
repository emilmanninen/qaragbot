"""
Step 3: standalone retrieval sanity-check script.
Thin CLI wrapper around backend.app.retrieval.retriever.retrieve().

Run from the repo root:
    python -m backend.scripts.retrieve
"""

from backend.app.retrieval.retriever import retrieve

QUERY = "Kuinka paljon opintorahaa voi saada korkeakouluopiskelijana?"
TOP_K = 5


def main():
    rows = retrieve(QUERY, TOP_K)
    print(f"Query: {QUERY}\n")
    for i, row in enumerate(rows, start=1):
        chunk_text, title, source_url, distance = row
        snippet = chunk_text.strip().replace("\n", " ")
        if len(snippet) > 300:
            snippet = snippet[:300] + "..."
        print(f"[{i}] distance={distance:.4f}  source={title} ({source_url})")
        print(f"    {snippet}\n")


if __name__ == "__main__":
    main()