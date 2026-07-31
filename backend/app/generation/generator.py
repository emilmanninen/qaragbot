"""
LLM generation interface.

This is one piece of Step 7's "swap models behind a clean interface" work,
pulled forward ahead of the rest of that refactor -- specifically because
Gemini's free-tier daily quota is a real, current blocker, not a
hypothetical future one. Chunking/embedding swappability stays deferred to
Step 7 proper; there's no equivalent concrete pain forcing that yet.

Usage:
    from backend.app.generation.generator import get_llm

    llm = get_llm()  # reads LLM_PROVIDER from .env, defaults to "gemini"
    answer = llm.generate(prompt, system_instruction, temperature=0.1)

To switch providers: set LLM_PROVIDER=anthropic in .env (and make sure
ANTHROPIC_API_KEY is set, and `pip install anthropic` is done). No code
change needed for the switch itself -- that's the whole point of this file.

Note this does NOT solve the underlying cost problem if you pick a paid
provider -- Anthropic's API has no ongoing free tier, only a one-time ~$5
signup credit, so switching to it doesn't give you a second daily free
quota, just a different (paid, after credits) way to hit the same wall.

Provider-side errors (rate limits, auth failures, etc.) are normalized into
QuotaExhaustedError / LLMProviderError here, at the same layer that already
hides which provider is active -- so callers (main.py) never need to import
a provider-specific exception type just to handle failures.
"""

import os
from abc import ABC, abstractmethod
from backend.app.retrieval.retriever import retrieve


class QuotaExhaustedError(Exception):
    """Raised when the active LLM provider's rate/quota limit is hit."""
    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(message)


class LLMProviderError(Exception):
    """Raised for any other LLM provider-side failure."""
    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(message)


class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_instruction: str, temperature: float = 0.1) -> str:
        ...


class GeminiLLM(LLMClient):
    def __init__(self, model: str = "gemini-flash-latest"):
        from google import genai
        self.client = genai.Client()  # reads GEMINI_API_KEY from environment
        self.model = model

    def generate(self, prompt: str, system_instruction: str, temperature: float = 0.1) -> str:
        from google.genai import types, errors as genai_errors
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                ),
            )
            return response.text
        except genai_errors.APIError as e:
            if e.code == 429:
                raise QuotaExhaustedError("gemini", str(e)) from e
            raise LLMProviderError("gemini", str(e)) from e


class AnthropicLLM(LLMClient):
    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        import anthropic
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
        self.model = model

    def generate(self, prompt: str, system_instruction: str, temperature: float = 0.1) -> str:
        import anthropic
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=temperature,
                system=system_instruction,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except anthropic.RateLimitError as e:
            # Must be caught before the broader APIError below --
            # RateLimitError is a subclass of APIError, so the order matters.
            raise QuotaExhaustedError("anthropic", str(e)) from e
        except anthropic.APIError as e:
            raise LLMProviderError("anthropic", str(e)) from e


def get_llm(name: str | None = None) -> LLMClient:
    """
    name=None reads LLM_PROVIDER from the environment (default "gemini"),
    so the caller doesn't need to know or care which provider is active.
    """
    name = (name or os.getenv("LLM_PROVIDER", "gemini")).lower()

    if name == "gemini":
        return GeminiLLM()
    elif name == "anthropic":
        return AnthropicLLM()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {name!r} (expected 'gemini' or 'anthropic')")


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
- Respond in plain prose only. Do not use markdown formatting -- no bold text (**), no bullet
  points, no headers, no numbered lists. Write full sentences; if you need to convey multiple
  related facts, connect them with words like "lisäksi" or "toisaalta" rather than a list.
"""


def build_prompt(query: str, chunks) -> tuple[str, list[dict]]:
    """
    Returns (prompt_text, sources) where sources[i] corresponds to citation [i+1]
    so callers can build a lookup table after generation.
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


def generate_answer(query: str, k: int = 5):
    chunks = retrieve(query, k)
    prompt, sources = build_prompt(query, chunks)

    llm = get_llm()
    answer = llm.generate(prompt, SYSTEM_INSTRUCTION, temperature=0.1)

    return answer, sources