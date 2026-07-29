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
"""

import os
from abc import ABC, abstractmethod


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
        from google.genai import types
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
            ),
        )
        return response.text


class AnthropicLLM(LLMClient):
    def __init__(self, model: str = "claude-sonnet-4-6"):
        import anthropic
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
        self.model = model

    def generate(self, prompt: str, system_instruction: str, temperature: float = 0.1) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=temperature,
            system=system_instruction,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


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