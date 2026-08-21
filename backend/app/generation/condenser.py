"""
backend/app/generation/condenser.py

Rewrites a follow-up question into a standalone question using conversation
history, so retrieval has enough semantic signal to work with. Runs BEFORE
retrieval. Does not see chunks, does not produce an answer, does not get citations.
"""

# Note: condense_query() doesn't catch/re-raise QuotaExhaustedError or
# LLMProviderError itself -- they propagate unmodified from llm.generate()
# below without needing to be named here. Only get_llm is actually used.
from backend.app.generation.generator import get_llm

CONDENSE_SYSTEM_INSTRUCTION = """You are rewriting a user's follow-up question so it can stand alone, without needing the earlier conversation to make sense.

Rules:
- Output ONLY the rewritten question. No preamble, no explanation, no answer to the question itself.
- If the question is already standalone and doesn't depend on the conversation, output it unchanged (or with only trivial cleanup — do not paraphrase or "improve" it).
- Resolve pronouns, implicit topics, and references (e.g. "it", "that", "what about X") using ONLY information explicitly present in the conversation below. Never invent or assume details that were not actually stated.
- If a reference could point to more than one thing in the conversation, resolve it to the most recently mentioned candidate.
- Keep the rewritten question as close as possible in length and content to the original — add only what's needed to remove ambiguity, nothing more."""


def format_history(history: list[dict]) -> str:
    """
    history: list of {"role": "user" | "assistant", "content": str}
    Renders as a plain transcript for the prompt.
    """
    if not history:
        return "(no prior conversation)"
    lines = []
    for turn in history:
        role = turn["role"].capitalize()
        lines.append(f"{role}: {turn['content']}")
    return "\n".join(lines)


def build_condense_prompt(history: list[dict], question: str) -> str:
    return (
        f"Conversation so far:\n{format_history(history)}\n\n"
        f"New question to rewrite:\n{question}\n\n"
        f"Rewritten standalone question:"
    )


def condense_query(history: list[dict], question: str) -> str:
    """
    Takes conversation history + a new question, returns a standalone
    rewritten question. Raises QuotaExhaustedError / LLMProviderError,
    same as generate_answer — caller (main.py) already handles these.
    """
    if not history:
        # Nothing to condense against — first turn is already standalone.
        return question

    llm = get_llm()
    prompt = build_condense_prompt(history, question)

    condensed = llm.generate(
        system_instruction=CONDENSE_SYSTEM_INSTRUCTION,
        prompt=prompt,
    )

    return condensed.strip()