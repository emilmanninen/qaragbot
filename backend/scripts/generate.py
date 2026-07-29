"""
Step 4: standalone generation + citations script.

Retrieved chunks -> [1][2]-tagged prompt -> LLM call -> print cited answer.
No FastAPI yet (Step 5). No structured JSON parsing of citations yet either
-- that's Step 5's job, once there's an actual API contract that needs
{answer, citations} as real JSON. For now we just print the raw answer with
inline [n] markers plus a source lookup table, so you can eyeball whether
the model's citations point at real, relevant chunks.

Run the same way as ingest.py / retrieve.py, from the repo root:
    python -m backend.scripts.generate

Requires GEMINI_API_KEY in your .env (get one at https://aistudio.google.com)
by default. Set LLM_PROVIDER=anthropic in .env (plus ANTHROPIC_API_KEY) to
switch providers with no code change -- see backend/app/generation/generator.py.
"""

from backend.app.generation.generator import get_llm
from backend.scripts.retrieve import retrieve, QUERY, TOP_K

SYSTEM_INSTRUCTION = """\
You answer questions using ONLY the numbered source excerpts provided below.
Do not use any outside knowledge, even if you know the answer independently.

Rules:
- Cite every factual claim using the bracket number(s) of the source(s) it came from, e.g. [1] or [1][2].
- If the provided excerpts do not contain enough information to answer, say so clearly in Finnish
  (e.g. "En löytänyt tähän vastausta annetuista lähteistä.") rather than guessing.
- Answer in Finnish, regardless of what language the question was asked in.
- Excerpts may start or end mid-sentence (they are fixed-length chunks) -- use the content anyway,
  don't comment on the truncation itself.
"""


def build_prompt(query: str, chunks) -> tuple[str, list[dict]]:
    """
    Returns (prompt_text, sources) where sources[i] corresponds to citation [i+1]
    so you can print a lookup table after generation.
    """
    sources = []
    context_blocks = []
    for i, row in enumerate(chunks, start=1):
        chunk_text, title, source_url, distance = row
        sources.append({"title": title, "source_url": source_url, "distance": distance})
        context_blocks.append(f"[{i}] (source: {title})\n{chunk_text.strip()}")

    context = "\n\n".join(context_blocks)
    prompt = f"{context}\n\n---\n\nKysymys: {query}"
    return prompt, sources


def generate_answer(query: str, k: int = TOP_K):
    chunks = retrieve(query, k)
    prompt, sources = build_prompt(query, chunks)

    llm = get_llm()  # LLM_PROVIDER in .env picks gemini vs anthropic; no code change to switch
    answer = llm.generate(prompt, SYSTEM_INSTRUCTION, temperature=0.1)

    return answer, sources


def main():
    answer, sources = generate_answer(QUERY, TOP_K)

    print(f"Query: {QUERY}\n")
    print("Answer:")
    print(answer)
    print("\nSources referenced:")
    for i, s in enumerate(sources, start=1):
        print(f"  [{i}] {s['title']} (distance={s['distance']:.4f}) - {s['source_url']}")


if __name__ == "__main__":
    main()