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
    answer = llm.generate_with_timeout(prompt, system_instruction, temperature=0.1)

To switch providers: set LLM_PROVIDER=anthropic in .env (and make sure
ANTHROPIC_API_KEY is set, and `pip install anthropic` is done). No code
change needed for the switch itself -- that's the whole point of this file.

Anthropic is additionally gated behind ALLOW_PAID_LLM=1 (see get_llm() below).
This exists for live hosting: Gemini has a real daily free tier, Anthropic
does not (one-time signup credit only, then billed). Deploy environments
should simply never set ALLOW_PAID_LLM, so a stray or misconfigured
LLM_PROVIDER=anthropic fails loudly at get_llm() instead of silently making
billed API calls. Set ALLOW_PAID_LLM=1 in your local .env if you want
LLM_PROVIDER=anthropic to work there.

Note this does NOT solve the underlying cost problem if you pick a paid
provider -- Anthropic's API has no ongoing free tier, only a one-time ~$5
signup credit, so switching to it doesn't give you a second daily free
quota, just a different (paid, after credits) way to hit the same wall.

Provider-side errors (rate limits, auth failures, etc.) are normalized into
QuotaExhaustedError / LLMProviderError here, at the same layer that already
hides which provider is active -- so callers (main.py) never need to import
a provider-specific exception type just to handle failures.

Timeout handling (added after a real hang during local testing):
`google-genai`'s own `http_options={"timeout": ...}` is set below as a
first line of defense, but it is NOT fully trustworthy on its own -- there
are open, still-unresolved upstream issues (e.g.
googleapis/python-genai#911, #1893, and pydantic/pydantic-ai#4031) where
the SDK passes `timeout=None` to its underlying httpx client on certain
request paths, silently overriding the client-level timeout and letting a
request hang indefinitely. Because of that, `LLMClient.generate_with_timeout()`
below adds a second, application-level hard timeout around *any* provider's
`generate()` call, not just Gemini's -- belt and suspenders, since we
shouldn't assume a provider SDK's own timeout config is reliable just
because it exists. `generate_answer()` calls `generate_with_timeout()`,
not `generate()` directly, so this applies uniformly regardless of which
provider is active.
"""

import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from backend.app.retrieval.retriever import retrieve

# How long we'll wait for any single LLM call before giving up and raising
# LLMProviderError, regardless of what the provider's own SDK timeout does.
DEFAULT_LLM_TIMEOUT_SECONDS = 30


class QuotaExhaustedError(Exception):
    """Raised when the active LLM provider's rate/quota limit is hit."""
    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(message)


class LLMProviderError(Exception):
    """Raised for any other LLM provider-side failure, including timeouts."""
    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(message)


class LLMClient(ABC):
    # Subclasses set this so timeout/error messages name the actual
    # provider instead of a generic class name.
    PROVIDER_NAME: str = "unknown"

    @abstractmethod
    def generate(self, prompt: str, system_instruction: str, temperature: float = 0.1) -> str:
        ...

    def generate_with_timeout(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.1,
        timeout: float = DEFAULT_LLM_TIMEOUT_SECONDS,
    ) -> str:
        """
        Runs generate() in a separate thread with a hard result timeout,
        so a hung provider call can't block a request indefinitely -- see
        the module docstring for why the provider SDK's own timeout can't
        be trusted alone.

        Tradeoff worth being able to say out loud: Python can't force-kill
        a thread. If the underlying call is genuinely stuck (not just
        slow), the orphaned thread keeps running in the background even
        after we give up waiting on it and raise. Acceptable for a
        single-worker demo -- this stops one hung call from freezing every
        other request -- but not a substitute for the provider actually
        fixing its timeout handling, and not something to lean on under
        real concurrent load without also capping how many of these
        orphaned threads can pile up.
        """
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.generate, prompt, system_instruction, temperature)
            try:
                return future.result(timeout=timeout)
            except FutureTimeoutError as e:
                raise LLMProviderError(
                    self.PROVIDER_NAME, f"Request timed out after {timeout}s"
                ) from e


class GeminiLLM(LLMClient):
    PROVIDER_NAME = "gemini"

    def __init__(self, model: str = "gemini-flash-latest"):
        from google import genai
        from google.genai import types
        self.client = genai.Client(
            # First line of defense -- see module docstring for why this
            # alone isn't sufficient on every code path in this SDK.
            http_options=types.HttpOptions(timeout=DEFAULT_LLM_TIMEOUT_SECONDS * 1000)
        )  # reads GEMINI_API_KEY from environment
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
    PROVIDER_NAME = "anthropic"

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

    Anthropic additionally requires ALLOW_PAID_LLM=1 in the environment --
    see module docstring for why.
    """
    name = (name or os.getenv("LLM_PROVIDER", "gemini")).lower()

    if name == "gemini":
        return GeminiLLM()
    elif name == "anthropic":
        if os.getenv("ALLOW_PAID_LLM", "").lower() not in ("1", "true", "yes"):
            raise ValueError(
                "LLM_PROVIDER=anthropic requires ALLOW_PAID_LLM=1 to be set -- "
                "Anthropic is a paid provider (no ongoing free tier) and is "
                "gated to prevent a misconfigured deploy environment from "
                "silently making billed API calls. Set ALLOW_PAID_LLM=1 in "
                "your local .env if you intend to use it."
            )
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
    answer = llm.generate_with_timeout(prompt, SYSTEM_INSTRUCTION, temperature=0.1)

    return answer, sources