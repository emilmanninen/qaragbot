"""
Step 4: standalone generation + citations script.
Thin CLI wrapper around backend.app.generation.generator.generate_answer().

Run from the repo root:
    python -m backend.scripts.generate
"""

from backend.app.generation.generator import generate_answer

QUERY = "Kuinka paljon opintolainahyvitystä voin saada valmistumisen jälkeen?"
TOP_K = 5


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